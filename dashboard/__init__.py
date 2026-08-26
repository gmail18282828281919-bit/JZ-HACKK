"""Dashboard web du bot Discord (API + pages statiques servies par le bot)."""

from .server import register_dashboard  # noqa: F401

__all__ = ["register_dashboard"]
