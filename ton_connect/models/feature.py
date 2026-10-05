import typing as t

from pydantic import Field, field_validator

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

    @field_validator("types", mode="before")
    @classmethod
    def _v_types(cls, v: t.Any) -> t.Any:
        return [x for x in v if x in ("binary", "cell", "text")] if isinstance(v, list) else v


class SignMessageFeature(BaseModel):
    """Wallet ``SignMessage`` feature declaration."""

    name: t.Literal["SignMessage"]
    """Feature name literal."""
    max_messages: int | None = A("maxMessages", default=None)
    """Maximum messages to sign, or ``None``."""
    extra_currency_supported: bool = A("extraCurrencySupported", default=False)
    """Whether extra currencies are supported."""


class EmbeddedRequestFeature(BaseModel):
    """Wallet ``EmbeddedRequest`` feature declaration."""

    name: t.Literal["EmbeddedRequest"]
    """Feature name literal."""


FeatureType: t.TypeAlias = t.Annotated[
    SendTransactionFeature | SignDataFeature | SignMessageFeature | EmbeddedRequestFeature,
    Field(discriminator="name"),
]
FeatureTypes = list[FeatureType]

_FEATURE_NAMES = frozenset({"SendTransaction", "SignData", "SignMessage", "EmbeddedRequest"})


def known_features(v: t.Any) -> t.Any:
    """Keep only features this SDK models.

    Wallets add features over time; an unknown one must not break
    connect or the wallets catalogue. Legacy wallets list ``"SendTransaction"`` as a string.

    :param v: Raw ``features`` value.
    :return: Feature dicts with known names, or *v* unchanged if it is not a list.
    """
    if not isinstance(v, list):
        return v
    result = [f for f in v if isinstance(f, dict) and isinstance(f.get("name"), str) and f["name"] in _FEATURE_NAMES]
    if "SendTransaction" in v and not any(f["name"] == "SendTransaction" for f in result):
        result.append({"name": "SendTransaction"})
    return result
