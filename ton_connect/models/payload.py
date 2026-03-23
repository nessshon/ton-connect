import base64
import time
import typing as t

from pydantic import Field, field_serializer, field_validator
from ton_core import Cell, TextCommentBody

from ._types import (
    A,
    BaseModel,
    BocCell,
    OptionalBocCell,
    OptionalChainId,
    OptionalTonAddress,
    OptionalWalletStateInit,
    TonAddress,
)


class SendTransactionMessage(BaseModel):
    """Single outgoing message within a ``sendTransaction`` request."""

    address: TonAddress
    """Destination address."""
    amount: int
    """Transfer amount in nanotons."""
    state_init: OptionalWalletStateInit = A("stateInit", default=None)
    """Contract ``StateInit``, or ``None``."""
    payload: OptionalBocCell | str | None = None
    """Message body ``Cell``, or ``None``."""
    extra_currency: dict[int, str] | None = A("extraCurrency", default=None)
    """Extra currency map, or ``None``."""

    @field_validator("amount", mode="before")
    @classmethod
    def _v_amount(cls, v: t.Any) -> int:
        if isinstance(v, int):
            return v
        return int(v)

    @field_serializer("amount")
    def _s_amount(self, v: int) -> str:
        return str(v)

    @field_validator("payload", mode="before")
    @classmethod
    def _v_payload(cls, v: t.Any) -> Cell | None:
        if isinstance(v, str):
            return TextCommentBody(v).serialize()
        return t.cast("Cell | None", v)


class SendTransactionPayload(BaseModel):
    """Payload for a ``sendTransaction`` RPC request."""

    network: OptionalChainId = None
    """Target network, or ``None``."""
    from_address: OptionalTonAddress = A("from", default=None)
    """Sender address override, or ``None``."""
    valid_until: int = A("validUntil", default=None)
    """Expiry unix timestamp."""
    messages: list[SendTransactionMessage] = Field(default_factory=list)
    """Outgoing messages."""

    @field_validator("valid_until", mode="before")
    @classmethod
    def _v_valid_until(cls, v: t.Any) -> int:
        if v is None:
            return int(time.time()) + 5 * 60
        return int(v)


class BaseSignDataPayload(BaseModel):
    """Common fields for all ``signData`` payload types."""

    network: OptionalChainId = None
    """Target network, or ``None``."""
    from_address: OptionalTonAddress = A("from", default=None)
    """Wallet address, or ``None``."""


class SignDataPayloadText(BaseSignDataPayload):
    """Text payload for ``signData``."""

    type: t.Literal["text"] = "text"
    """Payload type literal."""
    text: str
    """UTF-8 text to sign."""


class SignDataPayloadBinary(BaseSignDataPayload):
    """Binary payload for ``signData``."""

    type: t.Literal["binary"] = "binary"
    """Payload type literal."""
    raw_bytes: bytes = A("bytes")
    """Raw bytes to sign."""

    @field_validator("raw_bytes", mode="before")
    @classmethod
    def _v_raw_bytes(cls, v: t.Any) -> bytes:
        if isinstance(v, bytes):
            return v
        s = str(v).strip()
        padded = s + "=" * (-len(s) % 4)
        return base64.b64decode(padded, validate=True)

    @field_serializer("raw_bytes")
    def _s_raw_bytes(self, v: bytes) -> str:
        return base64.b64encode(v).decode("ascii")


class SignDataPayloadCell(BaseSignDataPayload):
    """Cell payload for ``signData``."""

    type: t.Literal["cell"] = "cell"
    """Payload type literal."""
    tlb_schema: str = A("schema")
    """TL-B schema string."""
    cell: BocCell
    """Signing payload ``Cell``."""


SignDataPayload: t.TypeAlias = t.Annotated[
    SignDataPayloadBinary | SignDataPayloadCell | SignDataPayloadText,
    Field(discriminator="type"),
]
