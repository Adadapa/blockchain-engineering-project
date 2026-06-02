import asyncio
import sys
sys.path.insert(0, "src")

from ipv8.configuration import ConfigBuilder, Strategy, WalkerDefinition, default_bootstrap_defs
from ipv8_service import IPv8

from blockchain.community.community import (BlockchainCommunity,
    wait_until_group_ready)
from blockchain.registration.registration import (
    RegistrationCommunity,
    find_server
)
# run this script to register your blockchain community
# .venv/bin/python scripts/register_blockchain.py

# --- configure these before running ---
PRIVATE_KEY_FILE = "keys/lab1_identity.pem"
KEY_TYPE = "curve25519"
LISTEN_PORT = 8091

GROUP_ID = "your-lab-2-group-id"

MEMBER_PUBLIC_KEYS = {
    bytes.fromhex("member-1-public-key-hex"),
    bytes.fromhex("member-2-public-key-hex"),
    bytes.fromhex("member-3-public-key-hex"),
}

REGISTRATION_COMMUNITY_ID = bytes.fromhex("4c616233426c6f636b636861696e323032365057")
SERVER_PUBLIC_KEY = bytes.fromhex(
    "4c69624e61434c504b3ae3fc099fb56ca3b5e1de9a1c843387f2acdbb78b1bd4350ffde518068a0d246344b10d0d8"
    "c355fd0d76873e7d7f7838f3715e025af08f791324495e083331ce6"
)
# --------------------------------------

RegistrationCommunity.community_id = REGISTRATION_COMMUNITY_ID


def ipv8_config():
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.set_address("0.0.0.0")
    builder.set_port(LISTEN_PORT)
    builder.set_walker_interval(0.5)
    builder.add_key("member", KEY_TYPE, PRIVATE_KEY_FILE)
    builder.add_overlay(
        "RegistrationCommunity",
        "member",
        [WalkerDefinition(Strategy.RandomWalk, 20, {"timeout": 3.0})],
        default_bootstrap_defs,
        {},
        [],
    )
    return builder.finalize()


async def main():
    ipv8 = IPv8(
        ipv8_config(),
        extra_communities={
            "BlockchainCommunity": BlockchainCommunity,
            "RegistrationCommunity": RegistrationCommunity,
        },
    )
    await ipv8.start()

    try:
        blockchain = ipv8.get_overlay(BlockchainCommunity)
        registration = ipv8.get_overlay(RegistrationCommunity)

        print("discovering teammates...")
        # await wait_until_group_ready(
        #     blockchain,
        #     GROUP_ID,
        #     MEMBER_PUBLIC_KEYS,
        # )

        print("discovering Lab 3 server...")
        server = await find_server(
            registration,
            SERVER_PUBLIC_KEY,
        )

        print(f"server found at {server.address}")
        # registration.register_blockchain(
        #     server,
        #     GROUP_ID,
        #     BlockchainCommunity.community_id,
        # )

        while registration.response is None:
            await asyncio.sleep(0.1)

    finally:
        await ipv8.stop()