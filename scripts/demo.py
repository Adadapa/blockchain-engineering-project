"""
Blockchain node: registers with the Lab 3 server, then mines and syncs blocks.

Usage: .venv/bin/python scripts/node.py
"""
import asyncio
import struct
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
from ipv8.keyvault.crypto import default_eccrypto
from blockchain.core.models import Transaction

TX_SCHEDULE = [
    (1.0, b"a1"),
    (13.2, b"a2"),
    (25.4, b"a3")
]
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

async def broadcast_scheduled_transactions(community, schedule):
    start = time.time()

    for delay, data in schedule:
        now = time.time()
        sleep_for = start + delay - now
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)

        timestamp = int(time.time())
        tx = broadcast_transaction(community, data=data, timestamp=timestamp)
        tx_hash = hash_transaction(tx)

        print(
            f"[Tx] broadcaster={tx.sender_key.hex()[:16]}... "
            f"tx_hash={tx_hash.hex()[:8]}... "
            f"broadcasted {tx.data!r}"
        )


def broadcast_transaction(community, data: bytes, timestamp: int) -> Transaction:
    sender_key = community.my_peer.public_key.key_to_bin()
    signed_data = sender_key + data + struct.pack(">q", timestamp)
    signature = default_eccrypto.create_signature(community.my_peer.key, signed_data)

    tx = Transaction(
        sender_key=sender_key,
        data=data,
        timestamp=timestamp,
        signature=signature,
    )

    community.mempool.add(tx)
    community.broadcast_new_transaction(tx)
    return tx

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

        if blockchain is None:
            raise RuntimeError("Failed to load BlockchainCommunity overlay")

        blockchain.chain = chain
        blockchain.mempool = mempool
        print(f"[Node] Port={NODE_LISTEN_PORT} community_id={blockchain.community_id.hex()}")

        # Discover teammates, then broadcast transactions, then mine.
        await discover_peers(blockchain)

        asyncio.create_task(
            broadcast_scheduled_transactions(blockchain, TX_SCHEDULE)
        )

        await mining_loop(blockchain)

    except KeyboardInterrupt:
        print("\n[Node] Interrupted")
    finally:
        print("[Node] Stopping...")
        await ipv8.stop()
        print("[Node] Stopped")


if __name__ == "__main__":
    asyncio.run(main())
