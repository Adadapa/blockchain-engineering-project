from dataclasses import dataclass

from .block_header import BlockHeader

@dataclass(frozen=True)
class Block:
    header: BlockHeader
    block_hash: bytes
    tx_hashes: tuple[bytes, ...]

class InvalidBlockError(Exception):
    pass