import aiohttp
from ton_core import (
    Address,
    Cell,
    ExternalMessage,
    InternalMessage,
    JettonTransferBody,
    MessageAny,
    NetworkGlobalID,
    to_amount,
    to_nano,
)

from ton_connect import AppWalletsLoader, FileStorage, TonConnect
from ton_connect.models import (
    SendTransactionMessage,
    SendTransactionPayload,
)

# URL to your tonconnect-manifest.json (must be publicly accessible)
# The wallet fetches this to display your app's name and icon
MANIFEST_URL = "https://raw.githubusercontent.com/nessshon/ton-connect/main/assets/tonconnect-manifest.json"

# Unique session key — identifies this connection in storage
# In production use a per-user identifier (e.g. Telegram user_id)
SESSION_KEY = "user-123"

# Path to the JSON file used as key-value storage for session data
# FileStorage is suitable for single-process apps; replace with a custom
# StorageProtocol implementation for distributed or database-backed setups
STORAGE_PATH = "./tonconnect-storage.json"

# USD₮ jetton master on mainnet — the transferred token and the one the relay takes its fee in
USDT_MASTER_ADDRESS = Address("EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs")

# Jetton amount in base units: USD₮ has 6 decimals, 0.1 USD₮ → 100,000
JETTON_AMOUNT = to_nano(0.1, decimals=6)


async def tonapi(method: str, path: str, body: dict | None = None) -> dict:
    """Call the Tonapi REST API (gasless relay included); works without an API key."""
    async with (
        aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
        session.request(method, f"https://tonapi.io/v2{path}", json=body) as resp,
    ):
        resp.raise_for_status()
        return await resp.json()


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

    try:
        # Create a connector for this session
        # Each user/session gets its own connector with an isolated storage namespace
        connector = tc.create_connector(SESSION_KEY)

        # Try to restore a previously saved connection before starting a new one
        # Returns True if an active session was found in storage
        restored = await connector.restore()

        if not restored:
            request = connector.make_connect_request()

            # Initiate connection and get the standard tc:// universal link
            # network:  expected network — USD₮ and the relay live on mainnet
            # timeout:  seconds before the pending connect is canceled (default: 15 min)
            await connector.connect(
                request=request,
                network=NetworkGlobalID.MAINNET,
            )

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

        owner = connector.account.address
        public_key = connector.account.public_key.as_hex
        print(f"Address: {owner.to_str(is_bounceable=False)}")

        # Jetton transfers go through the sender's own jetton wallet; the master's get_wallet_address finds it
        jetton = await tonapi(
            "GET",
            f"/blockchain/accounts/{USDT_MASTER_ADDRESS.to_str()}/methods/get_wallet_address?args={owner.to_str()}",
        )
        relay = await tonapi("GET", "/gasless/config")

        # Step 1: describe the transfer to the relay and get its quote
        # The relay pays the gas, so it gets back the unspent TON (response_address)
        # Tonapi relays Wallet V5 only; other wallets get 400 "failed to determine wallet version"
        transfer = InternalMessage(
            dest=Address(jetton["decoded"]["jetton_wallet_address"]),
            value=to_nano(0.05),
            bounce=True,
            body=JettonTransferBody(
                destination=owner,
                jetton_amount=JETTON_AMOUNT,
                response_address=Address(relay["relay_address"]),
            ).serialize(),
        )
        quote = await tonapi(
            "POST",
            f"/gasless/estimate/{USDT_MASTER_ADDRESS.to_str()}",
            {
                "wallet_address": owner.to_str(),
                "wallet_public_key": public_key,
                "messages": [{"boc": transfer.as_hex}],
            },
        )
        print(f"Relay fee: {to_amount(int(quote['commission']), decimals=6)} USD₮")

        # Step 2: the user signs the quote's messages — the transfer plus the relay fee — without sending them
        # Payloads come as hex BoCs: parse them, a plain string payload would be sent as a text comment
        # Raises WalletNotSupportFeatureError if the wallet did not declare SignMessage on connect
        request_id = await connector.sign_message(
            SendTransactionPayload(
                valid_until=quote["valid_until"],
                messages=[
                    SendTransactionMessage(
                        address=Address(Address(message["address"]).to_str(is_bounceable=True)),
                        amount=message["amount"],
                        payload=Cell.one_from_boc(message["payload"]),
                    )
                    for message in quote["messages"]
                ],
            )
        )
        print(f"Open wallet: {connector.make_request_url()}")

        result, error = await connector.wait_sign_message(request_id)
        if error:
            print(f"Signing failed: {error}")
            return

        # Step 3: the relay broadcasts the signed message
        # internal_boc is an internal message to the user's wallet; the relay takes it as an external one
        signed = MessageAny.deserialize(result.to_cell().begin_parse())
        external = ExternalMessage(dest=signed.info.dest, body=signed.body, state_init=signed.init)
        sent = await tonapi(
            "POST",
            "/gasless/send",
            {"wallet_public_key": public_key, "boc": external.as_hex},
        )
        print(f"Sent through the relay: {sent}")
    finally:
        # Close all active bridge connections, also when a request above fails
        await tc.close_all()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
