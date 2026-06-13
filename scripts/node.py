"""
Blockchain node: registers with the Lab 3 server, then mines and syncs blocks.

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
from blockchain.core.miner import mine
from blockchain.core.block_utils import hash_transaction, hash_txs
from blockchain.core.models import BlockHeader
from blockchain.core.models.block import Block
from blockchain.community.community import BlockchainCommunity
from blockchain.registration.registration import RegistrationCommunity, find_server
from blockchain.config import (
    PRIVATE_KEY_FILE, KEY_TYPE, NODE_LISTEN_PORT,
    BLOCKCHAIN_COMMUNITY_ID, MINING_DIFFICULTY,
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
    print("[Peers] Discovering teammates...")
    while True:
        peers = [
            p for p in community.get_peers()
            if p.public_key.key_to_bin() in MEMBER_PUBLIC_KEYS
        ]
        for peer in peers:
            community.walk_to(peer.address)
        print(f"[Peers] {len(peers)}/2 teammates found")
        if len(peers) >= 2:
            return peers
        await asyncio.sleep(1)


async def register(registration: RegistrationCommunity, blockchain_community_id: bytes) -> bool:
    try:
        print("[Register] Discovering Lab 3 server...")
        server = await find_server(registration, SERVER_PUBLIC_KEY)
        print(f"[Register] Server found at {server.address}")
        registration.register_blockchain(server, GROUP_ID, blockchain_community_id)
        print("[Register] Waiting for registration response...")
        while registration.response is None:
            await asyncio.sleep(0.1)
        print(f"[Register] Done — success={registration.response.success} message={registration.response.message}")
        return registration.response.success
    except Exception as exc:
        print(f"[Register] Failed: {exc}", file=sys.stderr)
        return False


async def mining_loop(community: BlockchainCommunity):
    loop = asyncio.get_running_loop()
    print("[Miner] Starting mining loop...")
    try:
        while True:
            tip = community.chain.tip
            pending = community.mempool.get_pending()
            tx_hashes = tuple(hash_transaction(tx) for tx in pending)
            txs_hash = hash_txs(list(tx_hashes))
            header = BlockHeader(
                prev_hash=tip.block_hash,
                txs_hash=txs_hash,
                timestamp=int(time.time()),
                difficulty=MINING_DIFFICULTY,
                nonce=0,
            )
            # Run PoW in a thread so the event loop stays free for incoming messages.
            mined_header, block_hash = await loop.run_in_executor(None, mine, header)
            block = Block(header=mined_header, block_hash=block_hash, tx_hashes=tx_hashes)
            community.chain.add_block(block)
            community.broadcast_new_block(block)
            print(
                f"[Miner] Block {community.chain.height}: "
                f"{block_hash.hex()[:16]}... ({len(tx_hashes)} txs)"
            )
    except asyncio.CancelledError:
        print("[Miner] Stopped")
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
        print(f"[Node] Port={NODE_LISTEN_PORT} community_id={blockchain.community_id.hex()}")

        # Discover teammates, then register, then mine.
        await discover_peers(blockchain)
        await register(registration, BLOCKCHAIN_COMMUNITY_ID)
        await mining_loop(blockchain)

    except KeyboardInterrupt:
        print("\n[Node] Interrupted")
    finally:
        print("[Node] Stopping...")
        await ipv8.stop()
        print("[Node] Stopped")


if __name__ == "__main__":
    asyncio.run(main())
