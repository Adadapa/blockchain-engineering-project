from __future__ import annotations

import hashlib

from .models import BlockHeader, Transaction

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
    return count_leading_zero_bits(digest) >= difficulty
