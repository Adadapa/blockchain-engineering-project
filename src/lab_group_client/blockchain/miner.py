from .block import hash_block_header, satisfies_pow
from .models import BlockHeader

## search for a nonce that makes the block hash satisfy the difficulty
def mine(header: BlockHeader) -> tuple[BlockHeader, bytes]:
    nonce = 0
    while True:
        candidate = header.copy_with_new_nonce(nonce)
        digest = hash_block_header(candidate)
        if satisfies_pow(digest, candidate.difficulty):
            return candidate, digest
        nonce += 1
