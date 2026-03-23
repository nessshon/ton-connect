from ._types import A, BaseModel, Binary64


class TonProofDomain(BaseModel):
    """Domain component of a TON Proof."""

    length_bytes: int = A("lengthBytes")
    """Domain string length in bytes."""
    value: str
    """Domain string."""


class TonProofData(BaseModel):
    """TON Proof data from the wallet."""

    timestamp: int
    """Proof unix timestamp."""
    domain: TonProofDomain
    """Signed domain."""
    signature: Binary64
    """Ed25519 signature (64 bytes)."""
    payload: str
    """Challenge payload string."""
