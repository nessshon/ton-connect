import aiohttp
from nacl.exceptions import BadSignatureError
from ton_core import Address, NetworkGlobalID, PublicKey

from ton_connect import (
    AppWalletsLoader,
    FileStorage,
    TonConnect,
    VerifyTonProof,
    create_ton_proof_payload,
    verify_ton_proof_payload,
)
from ton_connect.models import TonProofPayloadDto

# URL to your tonconnect-manifest.json (must be publicly accessible)
# The wallet fetches this to display your app's name and icon
MANIFEST_URL = "https://raw.githubusercontent.com/nessshon/ton-connect/main/assets/tonconnect-manifest.json"

# Unique session key — identifies this connection in storage
# In production use a per-user identifier (e.g. Telegram user_id)
SESSION_KEY = "user-123"

# Secret key for HMAC-signing the TonProof challenge payload
# Keep this on your backend — proves the proof was issued by you, not a third party
TON_PROOF_SECRET = "your-secret-key"

# Domain your app is served from — included in the signed message
# Must match the domain in your tonconnect-manifest.json
APP_DOMAIN = "raw.githubusercontent.com"

# Path to the JSON file used as key-value storage for session data
# FileStorage is suitable for single-process apps; replace with a custom
# StorageProtocol implementation for distributed or database-backed setups
STORAGE_PATH = "./tonconnect-storage.json"

# Toncenter API for the network the example connects to (testnet)
# Used to read a wallet's current public key; use https://toncenter.com/api/v2 for mainnet
TONCENTER_API = "https://testnet.toncenter.com/api/v2"


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
    storage = FileStorage(STORAGE_PATH)

    # Load wallet descriptors from the TON wallets registry
    # include_wallets=[...] would restrict the catalogue and the bridge connections opened
    app_wallets_loader = AppWalletsLoader()

    # Initialize the TonConnect manager
    # manifest_url: publicly accessible URL to your tonconnect-manifest.json
    # storage:      persistent session backend (FileStorage, Redis, DB, etc.)
    # app_wallets:  wallet descriptors propagated to each connector as bridge connection sources
    tc = TonConnect(
        storage=storage,
        manifest_url=MANIFEST_URL,
        app_wallets=app_wallets_loader.get_wallets(),
    )

    # Create a connector for this session
    # Each user/session gets its own connector with an isolated storage namespace
    connector = tc.create_connector(SESSION_KEY)

    # Step 1: Generate a challenge payload before showing the connect link
    # The wallet signs this payload, binding the proof to your backend
    # ttl: challenge lifetime in seconds — wallet must connect within this window
    ton_proof_payload = create_ton_proof_payload(
        secret_key=TON_PROOF_SECRET,
        ttl=15 * 60,  # 15 minutes
    )

    # Step 2: Include the payload in the connect request
    # This instructs the wallet to return a signed TonProof alongside the address
    request = connector.make_connect_request(ton_proof_payload=ton_proof_payload)

    # Initiate connection and get the standard tc:// universal link
    # network:  expected network — rejects wallets connected to a different chain
    # timeout:  seconds before the pending connect is canceled (default: 15 min)
    standard_url = await connector.connect(
        request=request,
        network=NetworkGlobalID.TESTNET,
    )

    # Standard tc:// link — works with any TonConnect-compatible wallet
    print(f"Connect URL: {standard_url}")

    # Wallet-specific universal links — each opens directly in its wallet app
    # Uses app_wallet.universal_url as the base instead of tc://
    for app_wallet in app_wallets_loader.get_wallets():
        print(f"{app_wallet.name}: {connector.make_connect_url(request, app_wallet)}")

    # Block until the wallet responds (approve or reject)
    # Returns (wallet, None) on success, (None, error) on failure or timeout
    wallet, error = await connector.wait_connect()

    if error:
        print(f"Connection failed: {error}")
        return

    address = connector.account.address.to_str(is_bounceable=False)
    print(f"Connected to: {connector.app_wallet.name}")
    print(f"Address: {address}")
    print(f"Network: {connector.account.network.name}")

    try:
        # Step 3: Verify the challenge payload before checking the proof itself
        # Ensures the payload was issued by your backend and hasn't expired
        # Raises BadSignatureError if the HMAC is invalid or the payload has expired
        verify_ton_proof_payload(
            secret_key=TON_PROOF_SECRET,
            ton_proof_payload=wallet.ton_proof.payload,
        )

        # Step 4: Verify the TonProof returned by the wallet
        # Reconstructs the payload from the wallet's connect response and verifies:
        #   1. Public key extracted from walletStateInit matches publicKey field
        #   2. Address derived from walletStateInit matches address field
        #   3. Timestamp is within valid_auth_time window (prevents replay attacks)
        #   4. Domain is in allowed_domains (prevents cross-app reuse)
        #   5. Ed25519 signature over the ton-proof-item-v2 message is valid
        proof_payload = TonProofPayloadDto(
            address=wallet.account.address,
            network=wallet.account.network,
            public_key=wallet.account.public_key,
            wallet_state_init=wallet.account.state_init,
            proof=wallet.ton_proof,
        )
        # get_wallet_public_key: optional, checks the Telegram wallet against its current key
        await VerifyTonProof(proof_payload).verify(
            allowed_domains=[APP_DOMAIN],
            valid_auth_time=15 * 60,  # 15 minutes
            get_wallet_public_key=get_wallet_public_key,
        )
        print("TonProof verified")
    except BadSignatureError as e:
        print(f"TonProof verification failed: {e}")

        # Disconnect the wallet if the proof is invalid
        await connector.disconnect()

    # Close all active bridge connections
    await tc.close_all()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
