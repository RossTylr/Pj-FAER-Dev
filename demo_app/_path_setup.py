"""Ensure faer_dev is importable regardless of how Streamlit is launched.

Import this module before any faer_dev imports:
    import _path_setup  # noqa: F401
"""
import os
import sys

for _candidate in [
    os.path.join(os.path.abspath('.'), 'src'),
    os.path.join(os.path.dirname(__file__), '..', 'src'),
]:
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, os.path.abspath(_candidate))
        break
