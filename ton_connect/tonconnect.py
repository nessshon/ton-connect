from __future__ import annotations

import typing as t

from .connector import Connector, Event
from .exceptions import TonConnectError
from .models import (
    ActiveConnection,
    AppWallet,
    SendTransactionResult,
    SignDataResult,
    WalletMessage,
)
from .provider.storage import ProviderStorage

if t.TYPE_CHECKING:
    from .storage import StorageProtocol

_ConnectHandler: t.TypeAlias = t.Callable[
    [Connector, TonConnectError | None],
    t.Awaitable[None],
]
_DisconnectHandler: t.TypeAlias = t.Callable[
    [Connector, TonConnectError | None],
    t.Awaitable[None],
]
_TransactionHandler: t.TypeAlias = t.Callable[
    [Connector, int, SendTransactionResult | None, TonConnectError | None],
    t.Awaitable[None],
]
_SignDataHandler: t.TypeAlias = t.Callable[
    [Connector, int, SignDataResult | None, TonConnectError | None],
    t.Awaitable[None],
]
_MessageHandler: t.TypeAlias = t.Callable[
    [Connector, WalletMessage],
    t.Awaitable[None],
]
_ErrorHandler: t.TypeAlias = t.Callable[
    [Connector, TonConnectError],
    t.Awaitable[None],
]

_EventHandler: t.TypeAlias = (
    _ConnectHandler | _DisconnectHandler | _ErrorHandler | _TransactionHandler | _SignDataHandler | _MessageHandler
)
_EventHandlers: t.TypeAlias = dict[Event, _EventHandler]


class TonConnect:
    """High-level TonConnect manager for multiple connector sessions."""

    def __init__(
        self,
        storage: StorageProtocol,
        manifest_url: str,
        app_wallets: list[AppWallet],
        headers: dict[str, str] | None = None,
        **context: t.Any,
    ) -> None:
        """Initialize the TonConnect manager.

        :param manifest_url: URL to ``tonconnect-manifest.json``.
        :param storage: Key-value storage backend.
        :param app_wallets: Wallet descriptors used as bridge connection sources.
        :param headers: Extra HTTP headers, or ``None``.
        :param context: Arbitrary context values.
        """
        self.storage = storage
        self.manifest_url = manifest_url
        self.app_wallets = app_wallets
        self.headers = headers

        self._handlers: _EventHandlers = {}
        self._context: dict[str, t.Any] = context
        self._connectors: dict[str, Connector] = {}

    def __getitem__(self, key: str) -> t.Any:
        """Return a context value by key."""
        return self._context[key]

    def __setitem__(self, key: str, value: t.Any) -> None:
        """Set a context value by key."""
        self._context[key] = value

    @property
    def context(self) -> dict[str, t.Any]:
        """User context dict."""
        return self._context

    @t.overload
    def register(
        self,
        event: t.Literal[Event.CONNECT],
        handler: _ConnectHandler,
    ) -> _ConnectHandler: ...

    @t.overload
    def register(
        self,
        event: t.Literal[Event.DISCONNECT],
        handler: _DisconnectHandler,
    ) -> _DisconnectHandler: ...

    @t.overload
    def register(
        self,
        event: t.Literal[Event.TRANSACTION],
        handler: _TransactionHandler,
    ) -> _TransactionHandler: ...

    @t.overload
    def register(
        self,
        event: t.Literal[Event.SIGN_DATA],
        handler: _SignDataHandler,
    ) -> _SignDataHandler: ...

    @t.overload
    def register(
        self,
        event: t.Literal[Event.MESSAGE],
        handler: _MessageHandler,
    ) -> _MessageHandler: ...

    @t.overload
    def register(
        self,
        event: t.Literal[Event.ERROR],
        handler: _ErrorHandler,
    ) -> _ErrorHandler: ...

    def register(
        self,
        event: Event,
        handler: _EventHandler,
    ) -> _EventHandler:
        """Register an event handler.

        :param event: Event type.
        :param handler: Async handler callable.
        :return: The registered handler.
        """
        self._handlers[event] = handler
        return handler

    @t.overload
    def on(
        self,
        event: t.Literal[Event.CONNECT],
    ) -> t.Callable[[_ConnectHandler], _ConnectHandler]: ...

    @t.overload
    def on(
        self,
        event: t.Literal[Event.DISCONNECT],
    ) -> t.Callable[[_DisconnectHandler], _DisconnectHandler]: ...

    @t.overload
    def on(
        self,
        event: t.Literal[Event.TRANSACTION],
    ) -> t.Callable[[_TransactionHandler], _TransactionHandler]: ...

    @t.overload
    def on(
        self,
        event: t.Literal[Event.SIGN_DATA],
    ) -> t.Callable[[_SignDataHandler], _SignDataHandler]: ...

    @t.overload
    def on(
        self,
        event: t.Literal[Event.MESSAGE],
    ) -> t.Callable[[_MessageHandler], _MessageHandler]: ...

    @t.overload
    def on(
        self,
        event: t.Literal[Event.ERROR],
    ) -> t.Callable[[_ErrorHandler], _ErrorHandler]: ...

    def on(
        self,
        event: Event,
    ) -> t.Callable[..., t.Any]:
        """Register an event handler via decorator.

        :param event: Event type.
        """

        def decorator(handler: _EventHandler) -> _EventHandler:
            self._handlers[event] = handler
            return handler

        return decorator

    @property
    def connectors(self) -> dict[str, Connector]:
        """Active connectors by session key (read-only copy)."""
        return dict(self._connectors)

    def create_connector(
        self,
        session_key: str,
        **context: t.Any,
    ) -> Connector:
        """Create a new ``Connector`` for a session.

        :param session_key: Unique session key.
        :param context: Extra context values merged with the global context.
        :return: New connector instance.
        """
        provider_storage = ProviderStorage(
            storage=self.storage,
            session_key=session_key,
        )
        connector = Connector(
            storage=provider_storage,
            session_key=session_key,
            manifest_url=self.manifest_url,
            app_wallets=self.app_wallets,
            handlers=dict(self._handlers),
            headers=self.headers,
            context={**self._context, **context},
        )
        self._connectors[session_key] = connector
        return connector

    async def from_connection(
        self,
        connection: ActiveConnection,
        session_key: str,
        **context: t.Any,
    ) -> Connector:
        """Reconstruct a connector from a saved ``ActiveConnection``.

        :param connection: Stored active connection.
        :param session_key: Session key for the connector.
        :param context: Extra context values.
        :return: Restored connector.
        """
        connector = self.create_connector(session_key, **context)
        await connector.storage.store_connection(connection)
        await connector.restore()
        return connector

    async def close_all(self) -> None:
        """Close all active connectors."""
        for connector in self._connectors.values():
            await connector.close()
        self._connectors.clear()
