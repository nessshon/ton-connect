import typing as t

from pydantic import Field, RootModel
from ton_core import Cell, MessageAny, normalize_hash

from ._types import (
    A,
    BaseModel,
    Binary64,
    ChainId,
    TonAddress,
    TonPublicKey,
    WalletStateInit,
)
from .device import Device
from .payload import SignDataPayload
from .proof import TonProofData


class EventBase(BaseModel):
    """Base for wallet events with a monotonic ID."""

    id: int | str | None = None
    """Monotonic event identifier."""


class TonAddressItemReply(BaseModel):
    """Wallet reply containing TON address and keys."""

    name: t.Literal["ton_addr"]
    """Item type literal."""
    address: TonAddress
    """Wallet address."""
    network: ChainId
    """Network identifier."""
    state_init: WalletStateInit = A("walletStateInit")
    """Wallet ``StateInit``."""
    public_key: TonPublicKey = A("publicKey")
    """Wallet public key."""


class TonProofItemReply(BaseModel):
    """Wallet reply containing TON Proof data."""

    name: t.Literal["ton_proof"]
    """Item type literal."""
    proof: TonProofData | None = None
    """Proof data, or ``None``."""


ConnectEventItemReply: t.TypeAlias = t.Annotated[
    TonAddressItemReply | TonProofItemReply,
    Field(discriminator="name"),
]


class ConnectEventPayload(BaseModel):
    """Payload of a successful connect event."""

    items: list[ConnectEventItemReply]
    """Connect reply items."""
    device: Device
    """Wallet device information."""


class DisconnectEventPayload(BaseModel):
    """Payload of a successful disconnect event."""

    data: dict[str, t.Any] = Field(default_factory=dict)
    """Additional data (typically empty)."""


class EventErrorPayload(BaseModel):
    """Payload of an event error."""

    code: int
    """Error code."""
    message: str
    """Error message."""


class ConnectEventSuccess(EventBase):
    """Successful wallet connect event."""

    event: t.Literal["connect"]
    """Event type literal."""
    payload: ConnectEventPayload
    """Connect event payload."""


class ConnectEventError(EventBase):
    """Failed wallet connect event."""

    event: t.Literal["connect_error"]
    """Event type literal."""
    payload: EventErrorPayload
    """Error payload."""


class DisconnectEventSuccess(EventBase):
    """Successful wallet disconnect event."""

    event: t.Literal["disconnect"]
    """Event type literal."""
    payload: dict[str, t.Any] = Field(default_factory=dict)
    """Additional data (typically empty)."""


class DisconnectEventError(EventBase):
    """Failed wallet disconnect event."""

    event: t.Literal["disconnect_error"]
    """Event type literal."""
    payload: EventErrorPayload
    """Error payload."""


ConnectEvent: t.TypeAlias = ConnectEventSuccess | ConnectEventError

DisconnectEvent: t.TypeAlias = DisconnectEventSuccess | DisconnectEventError

WalletEvent: t.TypeAlias = ConnectEvent | DisconnectEvent


class RpcBase(BaseModel):
    """Base for wallet RPC responses."""

    id: str
    """Request identifier string."""


class RpcRequestErrorPayload(BaseModel):
    """Error payload in an RPC response."""

    code: int
    """Error code."""
    message: str
    """Error message."""
    data: t.Any | None = None
    """Additional error data, or ``None``."""


class WalletResponseError(RpcBase):
    """Wallet RPC error response."""

    error: RpcRequestErrorPayload
    """Error payload."""


class SendTransactionResult(RootModel[str]):
    """Result of a ``sendTransaction`` RPC call."""

    @property
    def boc(self) -> str:
        """Base64-encoded BOC string."""
        return self.root

    def to_cell(self) -> Cell:
        """Deserialize the BOC to a ``Cell``.

        :return: Parsed ``Cell``.
        """
        return Cell.one_from_boc(self.root)

    @property
    def normalized_hash(self) -> str:
        """Normalized message hash for tracking."""
        msg = MessageAny.deserialize(self.to_cell().begin_parse())
        return normalize_hash(msg)


class RpcResponseSuccessBase(RpcBase):
    """Base for successful RPC responses."""


class SignDataResult(BaseModel):
    """Result of a ``signData`` RPC call."""

    signature: Binary64
    """Ed25519 signature (64 bytes)."""
    address: TonAddress
    """Signer wallet address."""
    timestamp: int
    """Signing unix timestamp."""
    domain: str
    """dApp domain."""
    payload: SignDataPayload
    """Signed data payload."""


class SendTransactionRpcResponseSuccess(RpcResponseSuccessBase):
    """Successful ``sendTransaction`` RPC response."""

    result: SendTransactionResult
    """Transaction result."""


class DisconnectRpcResponseSuccess(RpcResponseSuccessBase):
    """Successful ``disconnect`` RPC response."""

    result: dict[str, t.Any] = Field(default_factory=dict)
    """Additional data (typically empty)."""


class SignDataRpcResponseSuccess(RpcResponseSuccessBase):
    """Successful ``signData`` RPC response."""

    result: SignDataResult
    """Sign data result."""


WalletResponseSuccess: t.TypeAlias = (
    DisconnectRpcResponseSuccess | SendTransactionRpcResponseSuccess | SignDataRpcResponseSuccess
)

WalletResponse: t.TypeAlias = WalletResponseSuccess | WalletResponseError

WalletMessage: t.TypeAlias = WalletEvent | WalletResponse
