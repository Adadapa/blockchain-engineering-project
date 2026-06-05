from .block_utils import validate_block
from .models import Block
from .models.block import InvalidBlockError
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .mempool import Mempool


class Chain:
    def __init__(self, genesis: Block, mempool: Optional["Mempool"] = None) -> None:
        self._blocks: list[Block] = [genesis]
        self._hash_to_height: dict[bytes, int] = {genesis.block_hash: 0}
        self._hash_to_block: Dict[bytes, Block] = {genesis.block_hash: genesis}
        self._orphans_by_parent: Dict[bytes, List[Block]] = {}
        self._orphan_set = set()
        self._mempool = mempool
        # Saves tx objects removed from the mempool so they can be restored if their
        # block is later orphaned during a fork switch.
        self._orphanable_txs: dict[bytes, object] = {}

    @property
    def height(self) -> int:
        return len(self._blocks) - 1

    @property
    def tip(self) -> Block:
        return self._blocks[-1]

    def block_at(self, height: int) -> Block:
        if height < 0 or height > self.height:
            raise IndexError(f"no block at height {height}, chain height is {self.height}")
        return self._blocks[height]

    def contains(self, block_hash: bytes) -> bool:
        return block_hash in self._hash_to_height

    def try_append(self, block: Block) -> bool:
        if block.header.prev_hash != self.tip.block_hash:
            return False

        validate_block(block)

        height = self.height + 1
        self._blocks.append(block)
        self._hash_to_height[block.block_hash] = height
        self._hash_to_block[block.block_hash] = block
        self._confirm_block_txs(block)
        return True

    def add_block(self, block: Block) -> bool:
        bh = block.block_hash

        if bh in self._hash_to_block:
            return False

        validate_block(block)

        parent = block.header.prev_hash
        if parent in self._hash_to_height:
            self._hash_to_block[bh] = block
            parent_height = self._hash_to_height[parent]
            new_height = parent_height + 1
            self._hash_to_height[bh] = new_height

            if new_height > self.height:
                fork = self._build_fork_chain(block)
                self.switch_to_fork(fork)
        else:
            if bh in self._orphan_set:
                return False
            self._orphans_by_parent.setdefault(parent, []).append(block)
            self._orphan_set.add(bh)

        children = self._orphans_by_parent.pop(bh, [])
        for child in children:
            self._orphan_set.discard(child.block_hash)
            self.add_block(child)

        return True

    def get_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        return self._hash_to_block.get(block_hash)

    def _find_ancestor_height(self, fork: list[Block]) -> int:
        fork_base_prev_hash = fork[0].header.prev_hash
        if fork_base_prev_hash not in self._hash_to_height:
            raise ValueError("fork does not connect to any known block")

        ancestor_height = self._hash_to_height[fork_base_prev_hash]
        new_height = ancestor_height + len(fork)

        if new_height <= self.height:
            raise ValueError(f"fork height {new_height} is not longer than current chain height {self.height}")

        return ancestor_height

    def _apply_fork(self, fork: list[Block], ancestor_height: int) -> None:
        orphaned_blocks = self._blocks[ancestor_height + 1:]

        self._blocks = self._blocks[:ancestor_height + 1]
        self._hash_to_height = {b.block_hash: h for h, b in enumerate(self._blocks)}

        # Return orphaned blocks' transactions to the mempool.
        for block in orphaned_blocks:
            self._restore_block_txs(block)

        for block in fork:
            height = len(self._blocks)
            self._blocks.append(block)
            self._hash_to_height[block.block_hash] = height
            self._hash_to_block[block.block_hash] = block
            self._confirm_block_txs(block)

    def switch_to_fork(self, fork: list[Block]) -> None:
        if not fork:
            raise ValueError("fork is empty")

        ancestor_height = self._find_ancestor_height(fork)
        _validate_fork_chain(fork, fork[0].header.prev_hash)
        self._apply_fork(fork, ancestor_height)

    def _build_fork_chain(self, tip: Block) -> list[Block]:
        """Walk _hash_to_block back from tip until reaching the canonical chain."""
        canonical = {b.block_hash for b in self._blocks}
        chain: list[Block] = []
        cur = tip
        while cur.block_hash not in canonical:
            chain.append(cur)
            parent = self._hash_to_block.get(cur.header.prev_hash)
            if parent is None:
                raise ValueError("cannot build fork chain: missing ancestor block")
            cur = parent
        chain.reverse()
        return chain

    def _confirm_block_txs(self, block: Block) -> None:
        """Remove block's txs from mempool, saving them in case this block is later orphaned."""
        if self._mempool is None or not block.tx_hashes:
            return
        removed = self._mempool.remove_confirmed(block.tx_hashes)
        for tx in removed:
            from .block_utils import hash_transaction
            self._orphanable_txs[hash_transaction(tx)] = tx

    def _restore_block_txs(self, block: Block) -> None:
        """Re-add a now-orphaned block's transactions back to the mempool."""
        if self._mempool is None or not block.tx_hashes:
            return
        for tx_hash in block.tx_hashes:
            tx = self._orphanable_txs.pop(tx_hash, None)
            if tx is not None:
                self._mempool.add(tx)


def _validate_fork_chain(fork: list[Block], ancestor_prev_hash: bytes) -> None:
    prev_hash = ancestor_prev_hash
    for block in fork:
        if block.header.prev_hash != prev_hash:
            raise InvalidBlockError("fork blocks do not form a chain")
        validate_block(block)
        prev_hash = block.block_hash
