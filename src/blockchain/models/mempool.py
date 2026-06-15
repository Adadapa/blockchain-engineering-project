
from blockchain.core.block_utils import hash_transaction

class Mempool:
    def __init__(self):
        self._txs: dict[bytes, object] = {} # txs_hashes

    def add(self, tx) -> bool:
        tx_hash = hash_transaction(tx)
        if tx_hash in self._txs:
            return False
        self._txs[tx_hash] = tx
        return True

    def get_pending(self, max_count: int = 100) -> list:
        return list(self._txs.values())[:max_count]

    def remove_confirmed(self, tx_hashes: tuple[bytes, ...]) -> list:
        removed = []
        for h in tx_hashes:
            tx = self._txs.pop(h, None)
            if tx is not None:
                removed.append(tx)
        return removed
