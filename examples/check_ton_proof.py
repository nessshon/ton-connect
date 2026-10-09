import aiohttp
from ton_core import Address, PublicKey

from ton_connect import VerifyTonProof
from ton_connect.models import TonProofPayloadDto

# Payload received from the frontend after wallet connection via TonConnect
# The wallet signs a message bound to its address, your app's domain, a timestamp,
# and the payload nonce — proving ownership of the declared address
#
# address:         raw wallet address (workchain:hash format)
# network:         "-239" for mainnet, "-3" for testnet
# publicKey:       wallet's Ed25519 public key (hex)
# walletStateInit: base64-encoded wallet StateInit — used to derive and verify the public key
#                  even if the contract is not yet deployed on-chain (uninit state)
# proof:
#   timestamp: Unix epoch (seconds) when the wallet signed — checked against valid_auth_time
#   domain:    app domain the wallet signed for — must be in allowed_domains
#   signature: Ed25519 signature over the assembled ton-proof-item-v2 message (base64)
#   payload:   nonce issued by your backend — ties the proof to your specific auth request
PAYLOAD = {
    "address": "0:83ae019a23a8162beaa5cb0ebdc56668b2eac6c6ba51808812915b206a152dc5",
    "network": "-239",
    "publicKey": "79c446597dbf81b9987e9059de95dc557bcd9e2c431a6db1677768783d0b99f7",
    "walletStateInit": "te6cckECFgEAArEAAgE0AgEAUYAAAAA///+IvOIjLL7fwNzMP0gs70ruKr3mzxYhjTbYs7u0PB6FzPugART/APSkE/S88sgLAwIBIAYEAQLyBQEeINcLH4IQc2lnbrry4Ip/EQIBSBAHAgEgCQgAGb5fD2omhAgKDrkPoCwCASANCgIBSAwLABGyYvtRNDXCgCAAF7Ml+1E0HHXIdcLH4AIBbg8OABmvHfaiaEAQ65DrhY/AABmtznaiaEAg65Drhf/AAtzQINdJwSCRW49jINcLHyCCEGV4dG69IYIQc2ludL2wkl8D4IIQZXh0brqOtIAg1yEB0HTXIfpAMPpE+Cj6RDBYvZFb4O1E0IEBQdch9AWDB/QOb6ExkTDhgEDXIXB/2zzgMSDXSYECgLmRMOBw4hIRAeaO8O2i7fshgwjXIgKDCNcjIIAg1yHTH9Mf0x/tRNDSANMfINMf0//XCgAK+QFAzPkQmiiUXwrbMeHywIffArNQB7Dy0IRRJbry4IVQNrry4Ib4I7vy0IgikvgA3gGkf8jKAMsfAc8Wye1UIJL4D95w2zzYEgP27aLt+wL0BCFukmwhjkwCIdc5MHCUIccAs44tAdcoIHYeQ2wg10nACPLgkyDXSsAC8uCTINcdBscSwgBSMLDy0InXTNc5MAGk6GwShAe78uCT10rAAPLgk+1V4tIAAcAAkVvg69csCBQgkXCWAdcsCBwS4lIQseMPINdKFRQTABCTW9sx4ddM0AByMNcsCCSOLSHy4JLSAO1E0NIAURO68tCPVFAwkTGcAYEBQNch1woA8uCO4sjKAFjPFsntVJPywI3iAJYB+kAB+kT4KPpEMFi68uCR7UTQgQFB1xj0BQSdf8jKAEAEgwf0U/Lgi44UA4MH9Fvy4Iwi1woAIW4Bs7Dy0JDiyFADzxYS9ADJ7VSiwRtT",
    "proof": {
        "timestamp": 1754535788,
        "domain": {
            "lengthBytes": 10,
            "value": "github.com",
        },
        "signature": "d8GGkzgRbyPCiAt4a2EN+xiNK6fLHo/ptQdDT3YQcUD4cg3TUnE2Airf37y+xRkEP/aiQq38ytS4Ho4ZDHM5CQ==",
        "payload": "f85774c9762007d20000000068941ae3",
    },
}


# Toncenter API for the network of the proof (mainnet)
# Used to read a wallet's current public key; use https://testnet.toncenter.com/api/v2 for testnet
TONCENTER_API = "https://toncenter.com/api/v2"


async def get_wallet_public_key(address: Address) -> PublicKey | None:
    """Read the wallet's current public key from the chain (``get_public_key`` get-method).

    Optional for verify(): without it the Telegram wallet is checked against the initial key
    from walletStateInit, which keeps accepting a key its owner has rotated out.
    Returns None if the wallet is not deployed yet or the API answers with an error; the initial key is then used.
    """
    body = {"address": address.to_str(), "method": "get_public_key", "stack": []}
    timeout = aiohttp.ClientTimeout(total=15)
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.post(f"{TONCENTER_API}/runGetMethod", json=body) as resp,
    ):
        if not resp.ok:
            return None
        result = (await resp.json())["result"]
    if result["exit_code"] != 0 or not result["stack"]:
        return None
    return PublicKey(result["stack"][0][1])


async def main() -> None:
    # Parse and validate the raw payload dict into a typed DTO
    payload = TonProofPayloadDto.model_validate(PAYLOAD)

    # Verify the TON Proof — raises BadSignatureError if any check fails:
    #   1. Public key is extracted from walletStateInit and matches publicKey field
    #   2. Address is derived from walletStateInit and matches address field
    #   3. Timestamp is within valid_auth_time window (prevents replay attacks)
    #   4. Domain is in allowed_domains (prevents cross-app reuse)
    #   5. Ed25519 signature over the ton-proof-item-v2 message is valid
    #
    # allowed_domains: list of domains your backend accepts — reject anything else
    # valid_auth_time: max age of the proof in seconds (15 min is typical)
    # get_wallet_public_key: optional, checks the Telegram wallet against its current key
    #
    # The sample proof above is old, so this run ends with "Signature expired";
    # pass a fresh proof from your frontend
    await VerifyTonProof(payload).verify(
        allowed_domains=["github.com"],
        valid_auth_time=15 * 60,  # 15 minutes
        get_wallet_public_key=get_wallet_public_key,
    )
    print("TonProof verified")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
