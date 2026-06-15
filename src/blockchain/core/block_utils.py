from __future__ import annotations

import hashlib

from .models import Block, BlockHeader, Transaction
from .models.block import InvalidBlockError


def hash_block_header(header: BlockHeader) -> bytes:
    return hashlib.sha256(header.pack()).digest()

def hash_transaction(tx: Transaction) -> bytes:
    ts_bytes = tx.timestamp.to_bytes(8, "big")
    return hashlib.sha256(tx.sender_key + tx.data + ts_bytes + tx.signature).digest()

def hash_txs(tx_hashes: list[bytes]) -> bytes:
    return hashlib.sha256(b"".join(tx_hashes)).digest()

def count_leading_zero_bits(digest: bytes) -> int:
    count = 0
    for byte in digest:
        if byte == 0:
            count += 8
        else:
            count += (7 - byte.bit_length() + 1) if byte > 0 else 8
            break
    return count

def satisfies_pow(digest: bytes, difficulty: int) -> bool:
    result = count_leading_zero_bits(digest) >= difficulty
    # if result: # -> commented out on purpose, might be needed for demo later
    #     print(
    #         f"[Miner] PoW satisfied: hash={digest.hex()[:16]}... "
    #         f"difficulty={difficulty}"
    #     )
    return result

def validate_block(block: Block) -> None:
    # verify the hash is correct
    expected_hash = hash_block_header(block.header)
    if block.block_hash != expected_hash:
        raise InvalidBlockError(f"block_hash mismatch: got {block.block_hash.hex()}, expected {expected_hash.hex()}")

    # verify PoW
    if not satisfies_pow(block.block_hash, block.header.difficulty):
        raise InvalidBlockError(f"PoW not satisfied: hash {block.block_hash.hex()} does not have {block.header.difficulty} leading zero bits")

    # verify txs_hash matches the tx_hashes list
    expected_txs_hash = hash_txs(list(block.tx_hashes))
    if block.header.txs_hash != expected_txs_hash:
        raise InvalidBlockError(f"txs_hash mismatch: got {block.header.txs_hash.hex()}, expected {expected_txs_hash.hex()}")

