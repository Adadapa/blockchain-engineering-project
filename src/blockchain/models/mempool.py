
from blockchain.core.block_utils import hash_transaction

class Mempool:
    def __init__(self):
        self._txs: dict[bytes, object] = {} # txs_hashes

    # Used for pretty-printing the state
    def _state_view(self) -> str:
        hashes = ",".join(tx_hash.hex()[:8] for tx_hash in self._txs)
        return f"[{hashes}]"

    def add(self, tx) -> bool:
        tx_hash = hash_transaction(tx)
        if tx_hash in self._txs:
            print(f"[Mempool] Duplicate tx={tx_hash.hex()[:8]} state={self._state_view()}")
            return False
        self._txs[tx_hash] = tx
        print(f"[Mempool] Added tx={tx_hash.hex()[:8]} state={self._state_view()}")
        return True

    def get_pending(self, max_count: int = 100) -> list:
        return list(self._txs.values())[:max_count]

    def remove_confirmed(self, tx_hashes: tuple[bytes, ...]) -> list:
        removed = []
        for h in tx_hashes:
            tx = self._txs.pop(h, None)
            if tx is not None:
                removed.append(tx)
                print(f"[Mempool] Confirmed tx={h.hex()[:8]} state={self._state_view()}")
        return removed
