import hashlib

from .models import BlockHeader

# todo: replace this with the same ones chosen in mine_genesis.py
GENESIS_TIMESTAMP = 1748736000
GENESIS_DIFFICULTY = 8

# todo: update this with the resulting nonce from the script
RESULTING_NONCE = 1

# to remine: update scripts/mine_genesis.py and paste the result here
GENESIS_BLOCK = BlockHeader(
    prev_hash=b"\x00" * 32,
    txs_hash=hashlib.sha256(b"").digest(),
    timestamp=GENESIS_TIMESTAMP,
    difficulty=GENESIS_DIFFICULTY,
    nonce=RESULTING_NONCE
)
