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

from blockchain.genesis import GENESIS_BLOCK

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from blockchain.chain import Chain
from blockchain.mempool import Mempool
from blockchain.models import Block, BlockHeader
from blockchain.miner import mine_and_broadcast
from blockchain.community.community import BlockchainCommunity
from ipv8_service import IPv8


async def mining_loop(community, interval: float = 1.0, difficulty: int = 8):
    """
    Continuously mine blocks and broadcast them.
    Mines blocks with pending transactions from the mempool.
    """
    print("[Miner] Mining...")
    try:
        while True:
            tip = community.chain.tip
            # Create a header for the next block
            header = BlockHeader(
                prev_hash=tip.block_hash,
                txs_hash=b"\x00" * 32,  # placeholder; mine_and_broadcast will fill this
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


async def ipv8_config_default():
    """
    Minimal IPv8 configuration for a single node.
    In a real deployment, use your actual config (e.g., from config file).
    """
    return {
        "overlays": [
            {
                "class": "BlockchainCommunity",
                "key": "anonymous id",
                "walkers": [
                    {
                        "strategy": "RandomWalk",
                        "peers": 2,
                        "timeout": 3.0,
                    }
                ],
                "bootstrappers": [
                    # Add bootstrap peers here if you have a discovery service
                    # e.g., ("192.168.1.1", 8000)
                ],
            }
        ]
    }


async def main():
    # Initialize chain and mempool
    chain = Chain(GENESIS_BLOCK)
    mempool = Mempool()
    print(f"[Node] Chain initialized (height={chain.height})")
    print(f"[Node] Mempool initialized")

    # Get IPv8 configuration (use your actual config if available)
    config = await ipv8_config_default()

    # Create and start IPv8 service
    print("[Node] Starting IPv8 service...")
    ipv8 = IPv8(
        config,
        extra_communities={"BlockchainCommunity": BlockchainCommunity}
    )
    await ipv8.start()

    try:
        # Get the blockchain community overlay
        community = ipv8.get_overlay(BlockchainCommunity)
        if community is None:
            raise RuntimeError("Failed to load BlockchainCommunity overlay")


        community.chain = chain
        community.mempool = mempool
        print(f"[Node] BlockchainCommunity loaded (community_id={community.community_id.hex()[:16]}...)")

        mining_task = asyncio.create_task(mining_loop(community, interval=2.0, difficulty=8))
        await mining_task  # This will run until cancelled

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