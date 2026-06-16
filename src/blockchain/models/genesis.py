import hashlib
from blockchain.core.block_utils import hash_block_header
from blockchain.models import BlockHeader, Block

GENESIS_TIMESTAMP = 1748736000
GENESIS_DIFFICULTY = 8

RESULTING_NONCE = 1

GENESIS_BLOCK_HEADER = BlockHeader(
    prev_hash=b"\x00" * 32,
    txs_hash=hashlib.sha256(b"").digest(),
    timestamp=GENESIS_TIMESTAMP,
    difficulty=GENESIS_DIFFICULTY,
    nonce=RESULTING_NONCE
)

block_hash = hash_block_header(GENESIS_BLOCK_HEADER)

GENESIS_BLOCK = Block(
    header=GENESIS_BLOCK_HEADER,
    block_hash=block_hash,
    tx_hashes=tuple()
)