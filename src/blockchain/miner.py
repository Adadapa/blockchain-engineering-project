from .models import Block, BlockHeader
from .block_utils import hash_transaction, hash_txs, hash_block_header, satisfies_pow

## search for a nonce that makes the block hash satisfy the difficulty
def mine(header: BlockHeader) -> tuple[BlockHeader, bytes]:
    nonce = 0
    while True:
        candidate = header.copy_with_new_nonce(nonce)
        digest = hash_block_header(candidate)
        if satisfies_pow(digest, candidate.difficulty):
            return candidate, digest
        nonce += 1


def mine_and_broadcast(header: BlockHeader, community) -> Block:
    pending = community.mempool.get_pending()
    tx_hashes = tuple(hash_transaction(tx) for tx in pending)
    txs_hash = hash_txs(list(tx_hashes))

    header_with_txs = BlockHeader(
        prev_hash=header.prev_hash,
        txs_hash=txs_hash,
        timestamp=header.timestamp,
        difficulty=header.difficulty,
        nonce=0,
    )

    mined_header, block_hash = mine(header_with_txs)
    block = Block(header=mined_header, block_hash=block_hash, tx_hashes=tx_hashes)

    community.chain.add_block(block)
    community.broadcast_new_block(block)
    return block
