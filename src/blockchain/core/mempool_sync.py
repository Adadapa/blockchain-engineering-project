from .block_utils import hash_transaction
from .models import Block
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .mempool import Mempool


class MempoolSync:
    """Keeps the mempool in sync as blocks enter or leave the canonical chain."""

    def __init__(self, mempool: Optional["Mempool"] = None) -> None:
        self._mempool = mempool
        self._cache: dict[bytes, object] = {}  # tx_hash → tx, held for reorg restoration

    def confirm(self, block: Block) -> None:
        """Block joined the canonical chain — remove its txs from the mempool."""
        if self._mempool is None or not block.tx_hashes:
            return
        for tx in self._mempool.remove_confirmed(block.tx_hashes):
            self._cache[hash_transaction(tx)] = tx

    def restore(self, block: Block) -> None:
        """Block left the canonical chain — return its txs to the mempool."""
        if self._mempool is None or not block.tx_hashes:
            return
        for tx_hash in block.tx_hashes:
            tx = self._cache.pop(tx_hash, None)
            if tx is not None:
                self._mempool.add(tx)
