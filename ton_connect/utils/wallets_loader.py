import json
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from pydantic import TypeAdapter
from ton_core import load_json

from ..exceptions import FetchWalletsError
from ..models.app import AppWallet, AppWallets

_WALLETS_ADAPTER = TypeAdapter(AppWallets)

DEFAULT_WALLETS_LIST_SOURCE = "https://config.ton.org/wallets-v2.json"
"""Default URL for the wallets catalogue."""

DEFAULT_WALLETS_FALLBACK_FILE = "wallets-v2.json"
"""Default filename for the local wallets fallback."""


class AppWalletsLoader:
    """Wallets catalogue loader with memory cache, remote fetch, and file fallback."""

    def __init__(
        self,
        source: str | Path = DEFAULT_WALLETS_LIST_SOURCE,
        include_wallets: list[str] | None = None,
        exclude_wallets: list[str] | None = None,
        order_wallets: list[str] | None = None,
        require_sign_data: bool = False,
        fallback_path: Path | None = None,
        cache_ttl: float | None = None,
        timeout: float = 5.0,
    ) -> None:
        """Initialize the wallet catalogue loader.

        :param source: Remote URL or local path to wallets JSON.
        :param include_wallets: App names to include, or ``None`` for all.
        :param exclude_wallets: App names to exclude, or ``None``.
        :param order_wallets: Desired ordering of app names, or ``None``.
        :param require_sign_data: If ``True``, only include wallets that support
            the ``SignData`` feature.
        :param fallback_path: Local fallback file path, or ``None``.
        :param cache_ttl: Cache lifetime in seconds, or ``None`` for no expiry.
        :param timeout: HTTP fetch timeout in seconds.
        """
        self._source = source
        self._path = self._resolve_fallback_path(fallback_path)

        self._include = set(include_wallets) if include_wallets else None
        self._exclude = set(exclude_wallets) if exclude_wallets else None
        self._order = order_wallets
        self._require_sign_data = require_sign_data

        self._cache_ttl = cache_ttl
        self._timeout = timeout

        self._cache: list[AppWallet] | None = None
        self._cache_data: dict[str, AppWallet] = {}
        self._cached_at: float = 0.0

    def get_wallets(self) -> list[AppWallet]:
        """Return the wallets list, fetching and caching as needed.

        :return: Filtered and ordered wallet list.
        :raises FetchWalletsError: If wallets cannot be loaded.
        """
        if self._cache is not None and not self._expired():
            return self._cache

        raw = self._fetch_remote()
        if raw is None:
            raw = self._load_fallback()
        if raw is None:
            raise FetchWalletsError("Wallets catalog unavailable")

        wallets = self._process(raw)

        self._cache = wallets
        self._cache_data = {w.app_name: w for w in wallets}
        self._cached_at = time.time()

        return wallets

    def get_wallet(self, app_name: str) -> AppWallet | None:
        """Return a single wallet by app name, or ``None``.

        :param app_name: Wallet application name.
        :return: Wallet descriptor, or ``None``.
        """
        if self._cache is None or self._expired():
            self.get_wallets()
        return self._cache_data.get(app_name)

    def _process(self, raw: t.Any) -> list[AppWallet]:
        """Parse, filter, and sort raw wallet data."""
        wallets = self._parse(raw)
        wallets = self._filter(wallets)
        wallets = self._sort(wallets)
        return wallets  # noqa: RET504

    @staticmethod
    def _parse(raw: t.Any) -> list[AppWallet]:
        """Parse and validate raw JSON data.

        :param raw: Raw JSON-decoded data.
        :return: Wallets with a bridge URL.
        :raises FetchWalletsError: If data is invalid.
        """
        try:
            data = _WALLETS_ADAPTER.validate_python(raw)
        except Exception as e:
            raise FetchWalletsError(f"Invalid wallets data: {e}") from e

        return [w for w in data if w.bridge_url]

    def _filter(self, wallets: list[AppWallet]) -> list[AppWallet]:
        """Apply include/exclude/feature filters."""
        if self._include is not None:
            wallets = [w for w in wallets if w.app_name in self._include]
        if self._exclude is not None:
            wallets = [w for w in wallets if w.app_name not in self._exclude]
        if self._require_sign_data:
            wallets = [w for w in wallets if any(f.name == "SignData" for f in w.features)]

        return wallets

    def _sort(self, wallets: list[AppWallet]) -> list[AppWallet]:
        """Sort wallets by the configured order."""
        if not self._order:
            return wallets

        order_map: dict[str, int] = {name: i for i, name in enumerate(self._order)}
        default = len(order_map)

        wallets.sort(key=lambda w: order_map.get(w.app_name, default))
        return wallets

    def _fetch_remote(self) -> t.Any | None:
        """Fetch wallets JSON from the remote source, or ``None`` on failure."""
        try:
            raw = load_json(str(self._source), timeout=self._timeout)
            self._save_fallback(raw)
            return raw
        except Exception:
            return None

    def _load_fallback(self) -> t.Any | None:
        """Load wallets from the local fallback file, or ``None``."""
        if self._path is None:
            return None
        try:
            return json.loads(self._path.read_text())
        except Exception:
            return None

    def _save_fallback(self, raw: t.Any) -> None:
        """Save fetched data to the fallback file."""
        if self._path is None:
            return
        with suppress(Exception):
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(raw))

    def _expired(self) -> bool:
        """Check whether the cache has expired."""
        if self._cache_ttl is None:
            return False
        return (time.time() - self._cached_at) > self._cache_ttl

    @staticmethod
    def _resolve_fallback_path(path: Path | None) -> Path | None:
        """Resolve fallback path, appending default filename if directory.

        :param path: User-provided path, or ``None``.
        :return: Resolved file path, or ``None``.
        """
        if path is None:
            return None
        path = Path(path)
        if path.is_dir():
            return path / DEFAULT_WALLETS_FALLBACK_FILE
        return path
