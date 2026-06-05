"""
Simple blockchain node runner.
Starts a single blockchain node that:
- Initializes with genesis block
- Runs a mining loop
- Broadcasts blocks to peers
- Answers server queries
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blockchain.genesis import GENESIS_BLOCK
from blockchain.chain import Chain
from blockchain.mempool import Mempool
from blockchain.models import Block, BlockHeader
from blockchain.miner import mine_and_broadcast
from blockchain.community.community import BlockchainCommunity
from blockchain.config import (
    PRIVATE_KEY_FILE, KEY_TYPE, NODE_LISTEN_PORT,
    GROUP_ID, MEMBER_PUBLIC_KEYS, BLOCKCHAIN_COMMUNITY_ID, MINING_DIFFICULTY,
)
from ipv8.configuration import ConfigBuilder, Strategy, WalkerDefinition, default_bootstrap_defs
from ipv8_service import IPv8


async def mining_loop(community, interval: float = 1.0, difficulty: int = MINING_DIFFICULTY):
    print("[Miner] Mining...")
    try:
        while True:
            tip = community.chain.tip
            header = BlockHeader(
                prev_hash=tip.block_hash,
                txs_hash=b"\x00" * 32,  # placeholder; mine_and_broadcast fills this
                timestamp=int(time.time()),
                difficulty=difficulty,
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
    except Exception as exc:
        print(f"[Miner] Error: {exc}", file=sys.stderr)
        raise


def ipv8_config():
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.set_address("0.0.0.0")
    builder.set_port(NODE_LISTEN_PORT)
    builder.set_walker_interval(0.5)
    builder.add_key("blockchain-node", KEY_TYPE, PRIVATE_KEY_FILE)
    builder.add_overlay(
        "BlockchainCommunity",
        "blockchain-node",
        [WalkerDefinition(Strategy.EdgeWalk, 20, {})],
        default_bootstrap_defs,
        {},
        [],
    )
    return builder.finalize()


async def main():
    BlockchainCommunity.community_id = BLOCKCHAIN_COMMUNITY_ID

    mempool = Mempool()
    chain = Chain(GENESIS_BLOCK, mempool)
    print(f"[Node] Chain initialized (height={chain.height})")

    ipv8 = IPv8(
        ipv8_config(),
        extra_communities={"BlockchainCommunity": BlockchainCommunity},
    )
    await ipv8.start()

    try:
        community = ipv8.get_overlay(BlockchainCommunity)
        if community is None:
            raise RuntimeError("Failed to load BlockchainCommunity overlay")

        community.chain = chain
        community.mempool = mempool
        print(f"[Node] BlockchainCommunity loaded (community_id={community.community_id.hex()})")

        mining_task = asyncio.create_task(mining_loop(community, interval=2.0))
        await mining_task

    except KeyboardInterrupt:
        print("\nExiting")
    except Exception as exc:
        print(f"[Node] Error: {exc}", file=sys.stderr)
        raise
    finally:
        print("[Node] Stopping IPv8 service...")
        await ipv8.stop()
        print("[Node] Node stopped")


if __name__ == "__main__":
    asyncio.run(main())
