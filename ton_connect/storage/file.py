import asyncio
import json
import typing as t
from pathlib import Path

from .protocol import StorageProtocol


class FileStorage(StorageProtocol):
    """JSON file-backed key-value storage for TonConnect sessions."""

    def __init__(self, path: Path | str) -> None:
        """Initialize file storage with the given path."""
        self._path = Path(path)
        self._lock = asyncio.Lock()

    async def _read(self) -> dict[str, t.Any]:
        """Read the storage file, returning empty dict if missing."""
        if not self._path.exists():
            return {}

        def _load() -> dict[str, t.Any]:
            with self._path.open("r", encoding="utf-8") as f:
                return t.cast("dict[str, t.Any]", json.load(f))

        return await asyncio.to_thread(_load)

    async def _write(self, data: dict[str, t.Any]) -> None:
        """Write data to the storage file, creating parents as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        def _dump() -> None:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        await asyncio.to_thread(_dump)

    async def set_item(self, key: str, value: t.Any) -> None:
        """Store a value under *key*."""
        async with self._lock:
            data = await self._read()
            data[key] = value
            await self._write(data)

    async def get_item(self, key: str) -> t.Any | None:
        """Return the value for *key*, or ``None``."""
        async with self._lock:
            data = await self._read()
            return data.get(key)

    async def remove_item(self, key: str) -> None:
        """Remove *key* if present."""
        async with self._lock:
            data = await self._read()
            data.pop(key, None)
            await self._write(data)
