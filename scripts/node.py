"""
Blockchain node: mines blocks, syncs with peers, and registers with the Lab 3 server.

Usage: .venv/bin/python scripts/node.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blockchain.core.genesis import GENESIS_BLOCK
from blockchain.core.chain import Chain
from blockchain.core.mempool import Mempool
from blockchain.core.miner import mine_and_broadcast
from blockchain.core.models import BlockHeader
from blockchain.community.community import BlockchainCommunity
from blockchain.registration.registration import RegistrationCommunity, find_server
from blockchain.config import (
    PRIVATE_KEY_FILE, KEY_TYPE, NODE_LISTEN_PORT,
    BLOCKCHAIN_COMMUNITY_ID, MINING_DIFFICULTY,
    GROUP_ID, SERVER_PUBLIC_KEY,
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


async def register(registration: RegistrationCommunity, blockchain_community_id: bytes):
    try:
        print("[Register] Discovering Lab 3 server...")
        server = await find_server(registration, SERVER_PUBLIC_KEY)
        print(f"[Register] Server found at {server.address}")
        registration.register_blockchain(server, GROUP_ID, blockchain_community_id)
        print("[Register] Waiting for registration response...")
        while registration.response is None:
            await asyncio.sleep(0.1)
        print(f"[Register] Done — success={registration.response.success} message={registration.response.message}")
    except Exception as exc:
        print(f"[Register] Failed: {exc}", file=sys.stderr)


async def mining_loop(community: BlockchainCommunity, interval: float = 2.0):
    print("[Miner] Mining...")
    try:
        while True:
            tip = community.chain.tip
            header = BlockHeader(
                prev_hash=tip.block_hash,
                txs_hash=b"\x00" * 32,
                timestamp=int(time.time()),
                difficulty=MINING_DIFFICULTY,
                nonce=0,
            )
            mined_block = mine_and_broadcast(header, community)
            print(
                f"[Miner] Mined block at height {community.chain.height}: "
                f"{mined_block.block_hash.hex()[:16]}... "
                f"with {len(mined_block.tx_hashes)} txs"
            )
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("[Miner] Mining loop stopped")
        raise


async def main():
    BlockchainCommunity.community_id = BLOCKCHAIN_COMMUNITY_ID

    mempool = Mempool()
    chain = Chain(GENESIS_BLOCK, mempool)
    print(f"[Node] Chain initialized (height={chain.height})")

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
        print(f"[Node] Running on port {NODE_LISTEN_PORT}, community_id={blockchain.community_id.hex()}")

        asyncio.create_task(register(registration, BLOCKCHAIN_COMMUNITY_ID))
        await mining_loop(blockchain)

    except KeyboardInterrupt:
        print("\n[Node] Interrupted")
    finally:
        print("[Node] Stopping...")
        await ipv8.stop()
        print("[Node] Stopped")


if __name__ == "__main__":
    asyncio.run(main())
