from __future__ import annotations

from .adapters.base import ToolAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        descriptor = adapter.discover()
        if descriptor.adapter_id in self._adapters:
            raise ValueError(f"Adapter already registered: {descriptor.adapter_id}")
        self._adapters[descriptor.adapter_id] = adapter

    def get(self, adapter_id: str) -> ToolAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(f"Unknown adapter: {adapter_id}") from exc

    def descriptors(self):
        return [adapter.discover() for adapter in self._adapters.values()]

    def adapters(self):
        return list(self._adapters.values())
