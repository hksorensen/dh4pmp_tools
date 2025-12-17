"""
Clipboard operations for reading input and writing BibTeX output.
"""

import pyperclip
from typing import Optional


def read_clipboard() -> str:
    """Read text from system clipboard.
    
    Returns:
        Clipboard contents as string
        
    Raises:
        RuntimeError: If clipboard access fails
    """
    try:
        content = pyperclip.paste()
        return content.strip() if content else ""
    except Exception as e:
        raise RuntimeError(f"Failed to read from clipboard: {e}")


def write_clipboard(text: str) -> None:
    """Write text to system clipboard.
    
    Args:
        text: Text to write to clipboard
        
    Raises:
        RuntimeError: If clipboard access fails
    """
    try:
        pyperclip.copy(text)
    except Exception as e:
        raise RuntimeError(f"Failed to write to clipboard: {e}")


def get_input_from_clipboard_or_arg(cli_arg: Optional[str] = None) -> str:
    """Get input from CLI argument or clipboard.
    
    Priority:
    1. CLI argument if provided
    2. Clipboard contents
    
    Args:
        cli_arg: Optional command-line argument
        
    Returns:
        Input string to process
        
    Raises:
        ValueError: If no input provided
        RuntimeError: If clipboard access fails
    """
    if cli_arg:
        return cli_arg.strip()
    
    # Try clipboard
    clipboard_content = read_clipboard()
    if clipboard_content:
        return clipboard_content
    
    raise ValueError("No input provided. Provide identifier as argument or copy to clipboard.")
