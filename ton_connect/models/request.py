import typing as t

from pydantic import Field, TypeAdapter, field_serializer, field_validator

from ._types import A, BaseModel, OptionalChainId
from .payload import SendTransactionPayload, SignDataPayload

TParam = t.TypeVar("TParam")


class RpcRequestBase(BaseModel):
    """Base for all TonConnect RPC requests."""

    id: str | None = None
    """Request identifier, or ``None``."""
    method: str = ""
    """RPC method name."""

    def to_bytes(self, **kwargs: t.Any) -> bytes:
        """Serialize the request to UTF-8 JSON bytes."""
        return self.dump_json(**kwargs).encode()


class RpcRequestWithParams(RpcRequestBase, t.Generic[TParam]):
    """RPC request carrying a typed ``params`` list."""

    _params_adapter: t.ClassVar[TypeAdapter[t.Any]]

    params: list[TParam]
    """Typed parameter list."""

    @classmethod
    def _dump_param(cls, param: TParam) -> str:
        """Serialize a single param to a JSON string."""
        raw = cls._params_adapter.dump_json(param, by_alias=True, exclude_none=True)
        return raw.decode()

    @classmethod
    def _load_param(cls, raw: t.Any) -> TParam:
        """Deserialize a single param from JSON or dict."""
        if isinstance(raw, str):
            return t.cast("TParam", cls._params_adapter.validate_json(raw))
        return t.cast("TParam", cls._params_adapter.validate_python(raw))

    @field_validator("params", mode="before")
    @classmethod
    def _v_params(cls, v: t.Any) -> list[TParam]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("params must be a list")
        return [cls._load_param(item) for item in v]

    @field_serializer("params")
    def _s_params(self, v: list[TParam]) -> list[str]:
        return [self._dump_param(item) for item in v]


class TonAddressItem(BaseModel):
    """Connect request item for TON address."""

    name: t.Literal["ton_addr"] = "ton_addr"
    """Item type literal."""
    network: OptionalChainId = None
    """Target network, or ``None``."""


class TonProofItem(BaseModel):
    """Connect request item for TON Proof."""

    name: t.Literal["ton_proof"] = "ton_proof"
    """Item type literal."""
    payload: str
    """Challenge payload string."""


ConnectItem: t.TypeAlias = t.Annotated[
    TonAddressItem | TonProofItem,
    Field(discriminator="name"),
]


class ConnectRequest(BaseModel):
    """TonConnect connect request."""

    manifest_url: str = A("manifestUrl")
    """URL to ``tonconnect-manifest.json``."""
    items: list[ConnectItem]
    """Requested connect items."""


class DisconnectRpcRequest(RpcRequestBase):
    """RPC request to disconnect the wallet."""

    method: t.Literal["disconnect"] = "disconnect"
    """RPC method literal."""
    params: list[t.Any] = Field(default_factory=list, min_length=0, max_length=0)
    """Empty parameter list."""


class SendTransactionRpcRequest(RpcRequestWithParams[SendTransactionPayload]):
    """RPC request to send a transaction."""

    _params_adapter = TypeAdapter(SendTransactionPayload)

    method: t.Literal["sendTransaction"] = "sendTransaction"
    """RPC method literal."""
    params: list[SendTransactionPayload]
    """Transaction payloads."""


class SignDataRpcRequest(RpcRequestWithParams[SignDataPayload]):
    """RPC request to sign data."""

    _params_adapter = TypeAdapter(SignDataPayload)

    method: t.Literal["signData"] = "signData"
    """RPC method literal."""
    params: list[SignDataPayload]
    """Sign data payloads."""


RpcRequests: t.TypeAlias = t.Annotated[
    DisconnectRpcRequest | SendTransactionRpcRequest | SignDataRpcRequest,
    Field(discriminator="method"),
]

AppMessage: t.TypeAlias = ConnectRequest | RpcRequests
