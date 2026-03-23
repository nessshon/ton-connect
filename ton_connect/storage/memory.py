import asyncio
import typing as t

from .protocol import StorageProtocol


class MemoryStorage(StorageProtocol):
    """In-memory key-value storage for TonConnect sessions."""

    def __init__(self) -> None:
        """Initialize empty in-memory storage."""
        self._data: dict[str, t.Any] = {}
        self._lock = asyncio.Lock()

    async def set_item(self, key: str, value: t.Any) -> None:
        """Store a value under *key*."""
        async with self._lock:
            self._data[key] = value

    async def get_item(self, key: str) -> t.Any | None:
        """Return the value for *key*, or ``None``."""
        async with self._lock:
            return self._data.get(key)

    async def remove_item(self, key: str) -> None:
        """Remove *key* if present."""
        async with self._lock:
            self._data.pop(key, None)
