import typing as t

from pydantic import Field

from ._types import A, BaseModel
from .feature import FeatureTypes


class JSBridgeType(BaseModel):
    """JS-bridge connection descriptor."""

    type: t.Literal["js"]
    """Bridge type literal."""
    key: str
    """JS-bridge injection key."""


class SSEBridgeType(BaseModel):
    """SSE-bridge connection descriptor."""

    type: t.Literal["sse"]
    """Bridge type literal."""
    url: str
    """SSE bridge URL."""


BridgeType: t.TypeAlias = t.Annotated[
    JSBridgeType | SSEBridgeType,
    Field(discriminator="type"),
]
BridgeTypes = list[BridgeType]


class AppWallet(BaseModel):
    """Wallet application descriptor from the wallets catalogue."""

    name: str
    """Display name."""
    image: str
    """Icon URL."""
    app_name: str
    """Machine-readable application name."""
    bridge: BridgeTypes
    """Supported bridge types."""
    tondns: str | None = None
    """TON DNS name, or ``None``."""
    about_url: str | None = None
    """About page URL, or ``None``."""
    universal_url: str | None = None
    """Universal link base, or ``None``."""
    deep_link: str | None = A("deepLink", default=None)
    """Deep link scheme, or ``None``."""
    platforms: list[str]
    """Supported platform identifiers."""
    features: FeatureTypes
    """Declared wallet features."""

    @property
    def bridge_url(self) -> str | None:
        """First SSE bridge URL, or ``None``."""
        for b in self.bridge:
            if b.type == "sse":
                return b.url
        return None


AppWallets = list[AppWallet]
