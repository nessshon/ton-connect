from ._types import (
    A,
    BaseModel,
    Binary64,
    ChainId,
    TonAddress,
    TonPublicKey,
    WalletStateInit,
)
from .payload import SignDataPayload
from .proof import TonProofData


class SignDataPayloadDto(BaseModel):
    """Verified ``signData`` payload DTO for signature verification."""

    address: TonAddress
    """Wallet address."""
    network: ChainId
    """Network identifier."""
    public_key: TonPublicKey = A("publicKey")
    """Wallet public key."""
    wallet_state_init: WalletStateInit = A("walletStateInit")
    """Wallet ``StateInit``."""
    signature: Binary64
    """Ed25519 signature (64 bytes)."""
    timestamp: int
    """Signing unix timestamp."""
    domain: str
    """dApp domain."""
    payload: SignDataPayload
    """Signed data payload."""


class TonProofPayloadDto(BaseModel):
    """Verified ``ton_proof`` payload DTO for signature verification."""

    address: TonAddress
    """Wallet address."""
    network: ChainId
    """Network identifier."""
    public_key: TonPublicKey = A("publicKey")
    """Wallet public key."""
    wallet_state_init: WalletStateInit = A("walletStateInit")
    """Wallet ``StateInit``."""
    proof: TonProofData
    """TON Proof data."""
