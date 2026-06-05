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
from blockchain.config import (
    PRIVATE_KEY_FILE, KEY_TYPE, GROUP_ID, MEMBER_PUBLIC_KEYS,
    BLOCKCHAIN_COMMUNITY_ID, REGISTRATION_COMMUNITY_ID, SERVER_PUBLIC_KEY, REGISTRATION_LISTEN_PORT,
)

# run this script to register your blockchain community
# .venv/bin/python scripts/register_blockchain.py

RegistrationCommunity.community_id = REGISTRATION_COMMUNITY_ID
BlockchainCommunity.community_id = BLOCKCHAIN_COMMUNITY_ID

def ipv8_config():
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.set_address("0.0.0.0")
    builder.set_port(REGISTRATION_LISTEN_PORT)
    builder.set_walker_interval(0.5)
    builder.add_key("member", KEY_TYPE, PRIVATE_KEY_FILE)
    builder.add_overlay(
        "RegistrationCommunity",
        "member",
        [WalkerDefinition(Strategy.EdgeWalk, 20, {})],
        default_bootstrap_defs,
        {},
        [],
    )
    builder.add_overlay(
        "BlockchainCommunity",
        "member",
        [WalkerDefinition(Strategy.EdgeWalk, 20, {})],
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
        await wait_until_group_ready(
            blockchain,
            GROUP_ID,
            MEMBER_PUBLIC_KEYS,
        )

        print("discovering Lab 3 server...")
        server = await find_server(registration, SERVER_PUBLIC_KEY)

        print(f"server found at {server.address}")
        registration.register_blockchain(server, GROUP_ID, BlockchainCommunity.community_id)

        print("waiting for registration response...")
        while registration.response is None:
            await asyncio.sleep(0.1)

        print("registration complete")

    finally:
        await ipv8.stop()


if __name__ == "__main__":
    asyncio.run(main())