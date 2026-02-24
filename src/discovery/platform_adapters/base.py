# src/discovery/platform_adapters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.models import DiscoveredURL


class BaseAdapter(ABC):
    @abstractmethod
    def discover(self, config: dict) -> list[DiscoveredURL]:
        """Discover product URLs using this adapter's strategy."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
