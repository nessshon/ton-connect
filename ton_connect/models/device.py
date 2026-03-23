import typing as t

from pydantic import Field, TypeAdapter, field_validator

from ._types import A, BaseModel
from .feature import FeatureType, FeatureTypes

_FEATURE_ADAPTER: TypeAdapter[FeatureType] = TypeAdapter(FeatureType)


class Device(BaseModel):
    """Wallet device information from the connect event."""

    platform: str
    """Device platform identifier."""
    app_name: str = A("appName")
    """Wallet application name."""
    app_version: str = A("appVersion")
    """Wallet application version."""
    max_protocol_version: int = A("maxProtocolVersion")
    """Maximum supported TonConnect protocol version."""
    features: FeatureTypes = Field(default_factory=list)
    """Declared wallet features."""

    @field_validator("features", mode="before")
    @classmethod
    def _v_features(cls, v: t.Any) -> FeatureTypes:
        return [_FEATURE_ADAPTER.validate_python(f) for f in v if isinstance(f, dict)]
