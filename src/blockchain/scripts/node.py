"""
Blockchain node: registers with the Lab 3 server, then mines and syncs blocks.

Usage: .venv/bin/python src/blockchain/scripts/node.py
"""
import asyncio
import sys
from pathlib import Path

# sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blockchain.models.genesis import GENESIS_BLOCK
from blockchain.core.chain import Chain
from blockchain.models.mempool import Mempool
from blockchain.core.miner import mining_loop
from blockchain.community.community import BlockchainCommunity
from blockchain.registration.registration import RegistrationCommunity, find_server
from blockchain.config import (
    PRIVATE_KEY_FILE, KEY_TYPE, NODE_LISTEN_PORT,
    BLOCKCHAIN_COMMUNITY_ID,
    GROUP_ID, SERVER_PUBLIC_KEY, MEMBER_PUBLIC_KEYS,
)
from ipv8.configuration import ConfigBuilder, Strategy, WalkerDefinition, default_bootstrap_defs
from ipv8_service import IPv8


def ipv8_config():
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.set_address("0.0.0.0")
    builder.set_port(NODE_LISTEN_PORT)
    builder.set_walker_interval(0.5)
    builder.add_key("member", KEY_TYPE, PRIVATE_KEY_FILE)
    builder.add_overlay(
        "BlockchainCommunity",
        "member",
        [WalkerDefinition(Strategy.EdgeWalk, 20, {})],
        default_bootstrap_defs,
        {},
        [],
    )
    builder.add_overlay(
        "RegistrationCommunity",
        "member",
        [WalkerDefinition(Strategy.EdgeWalk, 20, {})],
        default_bootstrap_defs,
        {},
        [],
    )
    return builder.finalize()


async def discover_peers(community: BlockchainCommunity) -> list:
    print("Discovering teammates...")
    while True:
        peers = [
            p for p in community.get_peers()
            if p.public_key.key_to_bin() in MEMBER_PUBLIC_KEYS
        ]
        for peer in peers:
            community.walk_to(peer.address)

        if len(peers) >= 2:
            print(f"Teammates found")
            return peers
        await asyncio.sleep(1)


async def register(registration: RegistrationCommunity, blockchain_community_id: bytes) -> bool:
    try:
        print("Discovering Lab 3 server...")
        server = await find_server(registration, SERVER_PUBLIC_KEY)
        print(f"Server found")
        registration.register_blockchain(server, GROUP_ID, blockchain_community_id)
        while registration.response is None:
            await asyncio.sleep(0.1)
        print(registration.response)
        return registration.response.success
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return False


async def main():
    BlockchainCommunity.community_id = BLOCKCHAIN_COMMUNITY_ID
    mempool = Mempool()
    chain = Chain(GENESIS_BLOCK, mempool)

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

        blockchain.chain = chain
        blockchain.mempool = mempool

        await discover_peers(blockchain)
        await register(registration, BLOCKCHAIN_COMMUNITY_ID)
        await mining_loop(blockchain)

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        await ipv8.stop()


if __name__ == "__main__":
    asyncio.run(main())
