import hashlib
from blockchain.block_utils import hash_block_header
from .models import BlockHeader, Block

# todo: replace this with the same ones chosen in mine_genesis.py
GENESIS_TIMESTAMP = 1748736000
GENESIS_DIFFICULTY = 8

# todo: update this with the resulting nonce from the script
RESULTING_NONCE = 1

# to remine: update scripts/mine_genesis.py and paste the result here

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