import asyncio
import json
import os
import tempfile
import typing as t
from contextlib import suppress
from pathlib import Path

from .protocol import StorageProtocol


class FileStorage(StorageProtocol):
    """JSON file-backed key-value storage for TonConnect sessions."""

    def __init__(self, path: Path | str) -> None:
        """Initialize file storage with the given path."""
        self._path = Path(path)
        self._lock = asyncio.Lock()

    async def _read(self) -> dict[str, t.Any]:
        """Read the storage file, returning empty dict if missing or empty."""
        if not self._path.exists():
            return {}

        def _load() -> dict[str, t.Any]:
            text = self._path.read_text(encoding="utf-8")
            if not text.strip():
                return {}
            try:
                return t.cast("dict[str, t.Any]", json.loads(text))
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"{self._path} is not valid JSON, fix or delete it: {e.msg}", e.doc, e.pos
                ) from None

        return await asyncio.to_thread(_load)

    async def _write(self, data: dict[str, t.Any]) -> None:
        """Write data to the storage file, creating parents as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        def _dump_in_place() -> None:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        def _dump() -> None:
            target = self._path.resolve()
            try:
                fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
            except OSError:
                _dump_in_place()
                return
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                if target.exists():
                    st = target.stat()
                    os.chmod(name, st.st_mode)
                    with suppress(OSError):
                        os.chown(name, st.st_uid, st.st_gid)
                try:
                    os.replace(name, target)
                    return
                except OSError:
                    pass
            finally:
                with suppress(FileNotFoundError):
                    os.unlink(name)
            _dump_in_place()

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
