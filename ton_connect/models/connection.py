import time
import typing as t

from ._types import A, BaseModel
from .request import ConnectRequest
from .response import ConnectEventSuccess
from .session import BridgeProviderSession, SessionKeyPair


class ConnectionSource(BaseModel):
    """Bridge endpoint with universal link."""

    bridge_url: str = A("bridgeUrl")
    """Bridge base URL."""
    universal_link: str = A("universalLink")
    """Wallet universal link."""


ConnectionSources = list[ConnectionSource]


class PendingConnection(BaseModel):
    """Pending (not yet accepted) TonConnect connection."""

    connect_request: ConnectRequest = A("connectRequest")
    """Original connect request."""
    connection_sources: ConnectionSources = A("connectionSources")
    """Available bridge endpoints."""
    session_keypair: SessionKeyPair = A("sessionKeyPair")
    """Session X25519 key pair."""
    created_at: int | None = A("createdAt", default=None)
    """Creation unix timestamp, or ``None``."""

    def is_expired(self) -> bool:
        """Check whether the pending connection has expired (15 min TTL)."""
        if self.created_at is not None:
            now = int(time.time())
            return (now - self.created_at) > 15 * 60
        return True


class ActiveConnection(BaseModel):
    """Established TonConnect connection."""

    type: t.Literal["http"] = "http"
    """Connection type."""
    connect_event: ConnectEventSuccess = A("connectEvent")
    """Successful connect event."""
    session: BridgeProviderSession
    """Bridge provider session."""
    next_rpc_request_id: int = A("nextRpcRequestId", default=0)
    """Next RPC request sequence number."""
    last_wallet_event_id: int | str | None = A("lastWalletEventId", default=None)
    """Last wallet event ID, or ``None``."""
    last_event_id: str | None = A("lastEventId", default=None)
    """Last SSE event ID, or ``None``."""


Connection: t.TypeAlias = ActiveConnection | PendingConnection
