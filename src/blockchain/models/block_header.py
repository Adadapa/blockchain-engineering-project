from __future__ import annotations

from dataclasses import dataclass

HEADER_SIZE = 84

@dataclass(frozen=True)
class BlockHeader:
    prev_hash: bytes # 32 bytes
    txs_hash: bytes # 32 bytes
    timestamp: int # uint64
    difficulty: int # uint32
    nonce: int # uint64

    def __post_init__(self) -> None:
        if len(self.prev_hash) != 32:
            raise ValueError(f"prev_hash must be 32 bytes, got {len(self.prev_hash)}")
        if len(self.txs_hash) != 32:
            raise ValueError(f"txs_hash must be 32 bytes, got {len(self.txs_hash)}")

    def pack(self) -> bytes:
        return (
            self.prev_hash
            + self.txs_hash
            + self.timestamp.to_bytes(8, "big")
            + self.difficulty.to_bytes(4, "big")
            + self.nonce.to_bytes(8, "big")
        )

    @classmethod
    def unpack(cls, data: bytes) -> BlockHeader:
        if len(data) != HEADER_SIZE:
            raise ValueError(f"header must be {HEADER_SIZE} bytes but got {len(data)}")

        prev_hash = data[0:32]
        txs_hash = data[32:64]
        timestamp = int.from_bytes(data[64:72], "big")
        difficulty = int.from_bytes(data[72:76], "big")
        nonce = int.from_bytes(data[76:84], "big")

        return cls(
            prev_hash=prev_hash,
            txs_hash=txs_hash,
            timestamp=timestamp,
            difficulty=difficulty,
            nonce=nonce,
        )

    def copy_with_new_nonce(self, nonce: int) -> BlockHeader:
        return BlockHeader(
            prev_hash=self.prev_hash,
            txs_hash=self.txs_hash,
            timestamp=self.timestamp,
            difficulty=self.difficulty,
            nonce=nonce,
        )
