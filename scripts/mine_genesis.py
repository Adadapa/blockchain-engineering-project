import hashlib
import sys
import time
sys.path.insert(0, "src")

from blockchain.core.models import BlockHeader
from blockchain.core.block_utils import hash_block_header, satisfies_pow

# run this script to mine a new genesis block
# .venv/bin/python scripts/mine_genesis.py

# --- configure these before running ---
GENESIS_TIMESTAMP = 1748736000 # todo: we need to choose a timestamp before running
GENESIS_DIFFICULTY = 8
# --------------------------------------

prev_hash = b"\x00" * 32
txs_hash = hashlib.sha256(b"").digest()

print(f"mining genesis block with difficulty={GENESIS_DIFFICULTY}, timestamp={GENESIS_TIMESTAMP}...")
start = time.time()

nonce = 0
while True:
    header = BlockHeader(
        prev_hash=prev_hash,
        txs_hash=txs_hash,
        timestamp=GENESIS_TIMESTAMP,
        difficulty=GENESIS_DIFFICULTY,
        nonce=nonce,
    )
    digest = hash_block_header(header)
    if satisfies_pow(digest, GENESIS_DIFFICULTY):
        break
    nonce += 1

elapsed = time.time() - start
print(f"Done in {elapsed:.2f}s after {nonce + 1} attempts")
print(f"  nonce      = {nonce}")
print(f"  block_hash = {digest.hex()}")
print(f"  txs_hash   = {txs_hash.hex()}")
print()
print("Paste into genesis.py:")
print(f"  nonce={nonce},")
print(f"  # block_hash: {digest.hex()}")
