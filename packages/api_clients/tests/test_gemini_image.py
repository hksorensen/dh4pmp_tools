"""
Tests for Gemini image generation client.

Requires API key in gemini.yaml or GEMINI_API_KEY env var.
Skips if no API key is configured.

Run as script for a quick demo:
    python test_gemini_image.py
    python test_gemini_image.py output.png
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

try:
    from api_clients.gemini_image_client import (
        GeminiImageClient,
        GeminiImageFetcher,
        GeminiImageConfig,
        get_gemini_api_key,
    )
except ImportError:
    pytest.skip("api_clients not installed", allow_module_level=True)


GEMINI_API_KEY = get_gemini_api_key()


@pytest.mark.skipif(
    not GEMINI_API_KEY,
    reason="No Gemini API key (set GEMINI_API_KEY or create gemini.yaml)",
)
class TestGeminiImageClient:
    """Tests that hit the real API."""

    def test_generate_returns_bytes(self):
        """generate() returns image bytes."""
        assert GEMINI_API_KEY is not None
        config = GeminiImageConfig(api_key=GEMINI_API_KEY)
        client = GeminiImageClient(config)
        image_bytes = client.generate(
            "A simple red circle on white background"
        )
        assert image_bytes is not None
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 100
        # PNG magic bytes
        assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n" or image_bytes[:2] in (
            b"\xff\xd8",  # JPEG
        )

    def test_generate_to_file_saves(self):
        """generate_to_file() writes a valid image file."""
        assert GEMINI_API_KEY is not None
        fetcher = GeminiImageFetcher(api_key=GEMINI_API_KEY)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        try:
            result = fetcher.generate_to_file(
                "A small blue square", path
            )
            assert result == path
            assert path.exists()
            assert path.stat().st_size > 100
        finally:
            path.unlink(missing_ok=True)

    def test_generate_with_save_path(self):
        """generate(save_path=...) writes file."""
        assert GEMINI_API_KEY is not None
        fetcher = GeminiImageFetcher(api_key=GEMINI_API_KEY)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        try:
            image_bytes = fetcher.generate(
                "A green triangle",
                save_path=path,
            )
            assert image_bytes is not None
            assert path.exists()
            assert path.read_bytes() == image_bytes
        finally:
            path.unlink(missing_ok=True)


class TestGeminiImageConfig:
    """Unit tests (no API calls)."""

    def test_config_requires_api_key(self):
        """Client raises if api_key is empty."""
        config = GeminiImageConfig(api_key="")
        with pytest.raises(ValueError, match="API key"):
            GeminiImageClient(config)

    def test_fetcher_raises_when_no_config_found(self, tmp_path):
        """Fetcher raises if no api_key and no gemini.yaml in api_key_dir."""
        # Use tmp_path as api_key_dir (empty, no gemini.yaml)
        # Fetcher also checks Path(".")/gemini.yaml - run from tmp_path to avoid cwd
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(FileNotFoundError, match="API key not found"):
                GeminiImageFetcher(
                    api_key=None,
                    api_key_dir=str(tmp_path),
                )
        finally:
            os.chdir(orig_cwd)


def main() -> int:
    """
    Demo: generate an image and save to file.

    Usage:
        python test_gemini_image.py           # save to temp file
        python test_gemini_image.py out.png   # save to out.png
    """
    api_key = get_gemini_api_key()
    if not api_key:
        print(
            "No Gemini API key found. Set GEMINI_API_KEY or create gemini.yaml\n"
            "Get your key from: https://aistudio.google.com/apikey",
            file=sys.stderr,
        )
        return 1

    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if out_path is None:
        fd, out_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        out_path = Path(out_path)
        cleanup = True
    else:
        cleanup = False

    fetcher = GeminiImageFetcher(api_key=api_key)
    prompt = "A simple red circle on white background"
    print(f"Generating: {prompt!r}...")
    result = fetcher.generate_to_file(prompt, out_path)

    if result:
        print(f"Saved to {out_path}")
        if cleanup:
            print(f"(temp file - remove with: rm {out_path})")
        return 0
    else:
        print("Generation failed", file=sys.stderr)
        if cleanup and out_path.exists():
            out_path.unlink()
        return 1


if __name__ == "__main__":
    sys.exit(main())
