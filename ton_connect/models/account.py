from ._types import (
    A,
    BaseModel,
    ChainId,
    TonAddress,
    TonPublicKey,
    WalletStateInit,
)


class Account(BaseModel):
    """Connected wallet account data."""

    address: TonAddress
    """Wallet address."""
    network: ChainId
    """Network identifier."""
    public_key: TonPublicKey = A("publicKey")
    """Wallet public key."""
    state_init: WalletStateInit = A("walletStateInit")
    """Wallet ``StateInit``."""
