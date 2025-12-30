"""
Utility functions for bibfetcher.
"""

from .latex import text_to_latex, text_to_latex_preserve_danish, latex_to_text, normalize_bibkey_chars, ucfirst
from .keys import (
    generate_bibkey,
    generate_bibkey_prefix,
    check_key_exists,
    get_existing_keys_from_index,
)
from .clipboard import (
    read_clipboard,
    write_clipboard,
    get_input_from_clipboard_or_arg,
)

__all__ = [
    'text_to_latex',
    'text_to_latex_preserve_danish',
    'latex_to_text',
    'normalize_bibkey_chars',
    'ucfirst',
    'generate_bibkey',
    'generate_bibkey_prefix',
    'check_key_exists',
    'get_existing_keys_from_index',
    'read_clipboard',
    'write_clipboard',
    'get_input_from_clipboard_or_arg',
]
