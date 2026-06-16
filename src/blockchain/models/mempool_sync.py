from blockchain.core.block_utils import hash_transaction
from blockchain.models import Block
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blockchain.models.mempool import Mempool

# synchronizer for the mempool
class MempoolSync:
    def __init__(self, mempool: "Mempool") -> None:
        self._mempool = mempool
        self._cache: dict[bytes, object] = {}  # tx_hash → tx, held for reorg restoration

    # the block joined the canonical chain, so we remove its txs from the mempool
    def on_block_added(self, block: Block) -> None:
        if not block.tx_hashes:
            return
        for tx in self._mempool.remove_confirmed(block.tx_hashes):
            self._cache[hash_transaction(tx)] = tx

    # the block left the canonical chain,so we return its txs to the mempool
    def restore(self, block: Block) -> None:
        if not block.tx_hashes:
            return
        for tx_hash in block.tx_hashes:
            tx = self._cache.pop(tx_hash, None)
            if tx is not None:
                self._mempool.add(tx)
