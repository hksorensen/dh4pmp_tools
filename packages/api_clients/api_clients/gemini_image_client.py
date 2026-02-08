"""
Gemini image generation client.

Standalone client for generating images via the Google AI Gemini API.
Uses REST API (requests) - no caching (generative outputs are non-deterministic).
"""

import base64
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Union

import requests
import yaml

from .base_client import APIConfig, TokenBucket, RateLimiter, parse_429_response

logger = logging.getLogger(__name__)


# Default endpoint for Google AI Studio (generativelanguage.googleapis.com)
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash-image"


def get_gemini_api_key(
    api_key_dir: str = "~/Documents/dh4pmp/api_keys",
    raise_if_missing: bool = False,
) -> Optional[str]:
    """
    Load Gemini API key from env vars or gemini.yaml config file.

    Checks in order: GEMINI_API_KEY, GOOGLE_API_KEY, then gemini.yaml files.

    Args:
        api_key_dir: Directory to look for gemini.yaml (default: ~/Documents/dh4pmp/api_keys).
        raise_if_missing: If True, raise FileNotFoundError when key not found.
                          If False, return None.

    Returns:
        API key string, or None if not found (when raise_if_missing=False).

    Raises:
        FileNotFoundError: When key not found and raise_if_missing=True.
    """
    # Env vars first
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key and isinstance(key, str):
        return key.strip()

    # Config files
    api_key_dir = Path(api_key_dir).expanduser()
    key_paths = [
        Path(".") / "gemini.yaml",
        api_key_dir / "gemini.yaml",
    ]
    for path in key_paths:
        if path.exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                if data:
                    key = (
                        data.get("api_key")
                        or data.get("GOOGLE_API_KEY")
                        or data.get("GEMINI_API_KEY")
                    )
                    if key and isinstance(key, str):
                        return key.strip()
            except Exception as e:
                logger.debug(f"Error loading {path}: {e}")

    if raise_if_missing:
        raise FileNotFoundError(
            f"Gemini API key not found. Set GEMINI_API_KEY env var, or create one of:\n"
            f"  - ./gemini.yaml\n"
            f"  - {api_key_dir}/gemini.yaml\n\n"
            f"With content: api_key: your_api_key_here\n"
            f"Get your API key from: https://aistudio.google.com/apikey"
        )
    return None


@dataclass
class GeminiImageConfig(APIConfig):
    """Configuration for Gemini image generation."""

    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL

    # Image generation is slower than text - conservative rate limits
    requests_per_second: float = 1.0
    burst_size: int = 3
    timeout: int = 120  # Image generation can take a while
    max_retries: int = 3

    def __post_init__(self):
        super().__post_init__()


class GeminiImageClient:
    """
    Client for Gemini image generation via REST API.

    Uses POST requests to generateContent endpoint. No caching.
    """

    def __init__(self, config: GeminiImageConfig):
        self.config = config
        self.rate_limiter = RateLimiter(config)
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self):
        """Setup session headers."""
        if not self.config.api_key:
            raise ValueError(
                "Gemini API key is required. Set it in config or load from gemini.yaml. "
                "Get your API key from: https://aistudio.google.com/apikey"
            )
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "x-goog-api-key": self.config.api_key,
            }
        )

    def _build_url(self) -> str:
        """Build the generateContent URL."""
        return f"{self.config.base_url}/models/{self.config.model}:generateContent"

    def _make_request(
        self, body: Dict[str, Any], retry_count: int = 0
    ) -> Optional[requests.Response]:
        """Make POST request with retry logic."""
        self.rate_limiter.wait_if_needed()
        url = self._build_url()

        try:
            response = self.session.post(
                url, json=body, timeout=self.config.timeout
            )

            if response.ok:
                return response

            if response.status_code == 429:
                wait_time = parse_429_response(
                    response, default_delay=self.config.max_retry_delay
                )
                time.sleep(wait_time)
                return self._retry_request(body, retry_count)

            if response.status_code in (500, 503):
                logger.warning(
                    f"Server error ({response.status_code}). "
                    f"Retry {retry_count + 1}/{self.config.max_retries}"
                )
                return self._retry_request(body, retry_count)

            if response.status_code == 400:
                logger.error(f"Bad request (400): {response.text[:500]}")
                return None

            if response.status_code == 401:
                logger.error("Authentication failed (401). Check API key.")
                raise RuntimeError("Invalid API key or unauthorized access")

            return self._retry_request(body, retry_count)

        except requests.Timeout:
            logger.warning(
                f"Request timeout. Retry {retry_count + 1}/{self.config.max_retries}"
            )
            return self._retry_request(body, retry_count)
        except requests.RequestException as e:
            logger.error(f"Request exception: {e}")
            return self._retry_request(body, retry_count)

    def _retry_request(
        self, body: Dict[str, Any], retry_count: int
    ) -> Optional[requests.Response]:
        """Retry with exponential backoff."""
        if retry_count >= self.config.max_retries:
            return None
        delay = min(
            self.config.initial_retry_delay
            * (self.config.retry_backoff_factor**retry_count),
            self.config.max_retry_delay,
        )
        logger.info(f"Retrying in {delay:.1f}s...")
        time.sleep(delay)
        return self._make_request(body, retry_count + 1)

    def generate(
        self,
        prompt: str,
        response_modalities: Optional[list] = None,
        **generation_config,
    ) -> Optional[bytes]:
        """
        Generate an image from a text prompt.

        Args:
            prompt: Text description of the image to generate.
            response_modalities: Default ["TEXT", "IMAGE"] for image output.
            **generation_config: Optional generation config (aspectRatio, imageSize, etc.).

        Returns:
            Image bytes (PNG/JPEG), or None on failure.
        """
        if response_modalities is None:
            response_modalities = ["TEXT", "IMAGE"]

        body: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": response_modalities,
                **generation_config,
            },
        }

        response = self._make_request(body)
        if response is None:
            return None

        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Invalid JSON response: {e}")
            return None

        # Extract image from response
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                error = data.get("error", {}).get("message", "No candidates")
                logger.error(f"API error: {error}")
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                inline_data = part.get("inlineData")
                if inline_data and "data" in inline_data:
                    b64 = inline_data["data"]
                    return base64.b64decode(b64)

            logger.warning("No image data in response (may be text-only or blocked)")
            return None

        except (KeyError, TypeError) as e:
            logger.error(f"Unexpected response format: {e}")
            return None


class GeminiImageFetcher:
    """
    Fetcher for Gemini-generated images.

    No caching. Loads API key from gemini.yaml if not provided.

    Usage:
        fetcher = GeminiImageFetcher()
        image_bytes = fetcher.generate("A simple red circle on white background")
        if image_bytes:
            with open("output.png", "wb") as f:
                f.write(image_bytes)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_key_dir: str = "~/Documents/dh4pmp/api_keys",
        model: str = DEFAULT_MODEL,
        **kwargs,
    ):
        if api_key is None:
            api_key = self._load_api_key(api_key_dir)

        config = GeminiImageConfig(
            api_key=api_key or "",
            model=kwargs.pop("model", model),
            **kwargs,
        )
        self.client = GeminiImageClient(config)
        logger.info("Initialized Gemini image fetcher (no caching)")

    def _load_api_key(self, api_key_dir: str) -> str:
        """Load API key via get_gemini_api_key (raises if not found)."""
        key = get_gemini_api_key(api_key_dir=api_key_dir, raise_if_missing=True)
        return key

    def generate(
        self,
        prompt: str,
        save_path: Optional[Union[str, Path]] = None,
        **kwargs,
    ) -> Optional[bytes]:
        """
        Generate an image from a prompt.

        Args:
            prompt: Text description of the image.
            save_path: If provided, write image bytes to this path.
            **kwargs: Passed to client.generate (response_modalities, etc.).

        Returns:
            Image bytes, or None on failure.
        """
        image_bytes = self.client.generate(prompt, **kwargs)
        if image_bytes is not None and save_path is not None:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(image_bytes)
            logger.info(f"Saved image to {path}")
        return image_bytes

    def generate_to_file(
        self, prompt: str, path: Union[str, Path], **kwargs
    ) -> Optional[Path]:
        """
        Generate an image and save to file.

        Returns:
            Path to saved file, or None on failure.
        """
        path = Path(path)
        if self.generate(prompt, save_path=path, **kwargs) is not None:
            return path
        return None
