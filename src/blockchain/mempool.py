
from .block_utils import hash_transaction

class Mempool:
    def __init__(self):
        self._txs: dict[bytes, object] = {} # txs_hashes

    def add(self, tx) -> bool:
        tx_hash = hash_transaction(tx)
        if tx_hash in self._txs:
            return False
        self._txs[tx_hash] = tx
        return True

    # max_count transactions to include in next block
    def get_pending(self, max_count: int = 100) -> list:
        return list(self._txs.values())[:max_count]

    def remove_confirmed(self, tx_hashes: tuple[bytes, ...]) -> None:
        for h in tx_hashes:
            self._txs.pop(h, None)
