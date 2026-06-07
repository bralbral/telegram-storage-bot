from __future__ import annotations

from src.models.config import Config

__all__ = ["Config"]

# Re-export the Pydantic Config for backward compatibility
# The actual configuration is now in src/models/config.py
