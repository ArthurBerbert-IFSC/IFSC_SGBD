"""Backward compat shim: import everything from initial_panel_legacy.

File mantido apenas para evitar import breaks temporários. Use dashboard lateral.
"""
from .initial_panel_legacy import *  # type: ignore  # noqa: F401,F403
