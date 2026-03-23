import typing as t

from pydantic import Field

from ._types import A, BaseModel


class SendTransactionFeature(BaseModel):
    """Wallet ``SendTransaction`` feature declaration."""

    name: t.Literal["SendTransaction"]
    """Feature name literal."""
    max_messages: int | None = A("maxMessages", default=None)
    """Maximum outgoing messages, or ``None``."""
    extra_currency_supported: bool = A("extraCurrencySupported", default=False)
    """Whether extra currencies are supported."""


class SignDataFeature(BaseModel):
    """Wallet ``SignData`` feature declaration."""

    name: t.Literal["SignData"]
    """Feature name literal."""
    types: list[t.Literal["binary", "cell", "text"]]
    """Supported payload types."""


FeatureType: t.TypeAlias = t.Annotated[
    SendTransactionFeature | SignDataFeature,
    Field(discriminator="name"),
]
FeatureTypes = list[FeatureType]
