from __future__ import annotations

import asyncio
import time

from blockchain.models import Block, BlockHeader
from .block_utils import hash_transaction, hash_txs, hash_block_header, satisfies_pow
from typing import TYPE_CHECKING

from ..config import MINING_DIFFICULTY

if TYPE_CHECKING:
    from blockchain.community.community import BlockchainCommunity

def mine(header: BlockHeader) -> tuple[BlockHeader, bytes]:
    print(
        f"[Miner] Searching nonce for block: "
        f"prev={header.prev_hash.hex()[:16]}... "
        f"difficulty={header.difficulty}"
    )
    nonce = 0
    while True:
        candidate = header.copy_with_new_nonce(nonce)
        digest = hash_block_header(candidate)
        if satisfies_pow(digest, candidate.difficulty):
            return candidate, digest
        nonce += 1


async def mining_loop(community: BlockchainCommunity):
    loop = asyncio.get_running_loop()
    print("Starting mining")
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

            mined_header, block_hash = await loop.run_in_executor(None, mine, header)
            block = Block(header=mined_header, block_hash=block_hash, tx_hashes=tx_hashes)

            community.chain.add_block(block)
            community.broadcast_new_block(block)
            print(
                f"Mined next Block {community.chain.height}: "
                f"{block_hash.hex()[:16]}... ({len(tx_hashes)} txs)"
            )
    except asyncio.CancelledError:
        raise
