from __future__ import annotations

from ..exceptions import TonConnectError
from ._types import A, BaseModel
from .account import Account
from .device import Device
from .dto import TonProofPayloadDto
from .proof import TonProofData
from .response import (
    ConnectEventPayload,
    TonAddressItemReply,
    TonProofItemReply,
)


class Wallet(BaseModel):
    """Connected wallet state."""

    device: Device
    """Wallet device information."""
    account: Account
    """Wallet account data."""
    ton_proof: TonProofData | None = A("tonProof", default=None)
    """TON Proof data, or ``None``."""

    @property
    def ton_proof_dto(self) -> TonProofPayloadDto | None:
        """Build a ``TonProofPayloadDto`` from the stored proof, or ``None``."""
        if self.ton_proof is None:
            return None
        return TonProofPayloadDto(
            address=self.account.address,
            network=self.account.network,
            public_key=self.account.public_key,
            wallet_state_init=self.account.state_init,
            proof=self.ton_proof,
        )

    @classmethod
    def from_payload(cls, payload: ConnectEventPayload) -> Wallet:
        """Create a ``Wallet`` from a ``ConnectEventPayload``.

        :param payload: Successful connect event payload.
        :return: Wallet instance.
        :raises TonConnectError: If payload lacks a ``ton_addr`` item.
        """
        account: Account | None = None
        ton_proof: TonProofData | None = None

        for item in payload.items:
            if isinstance(item, TonAddressItemReply):
                account = Account.model_validate(item.model_dump(by_alias=True))
            elif isinstance(item, TonProofItemReply):
                ton_proof = item.proof

        if account is None:
            raise TonConnectError("ConnectEventPayload does not contain required `ton_addr` item")

        return cls(device=payload.device, account=account, ton_proof=ton_proof)
