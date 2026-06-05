from .block_utils import validate_block
from .models import Block
from .models.block import InvalidBlockError
from .orphan_pool import OrphanPool
from .mempool_sync import MempoolSync
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .mempool import Mempool


class Chain:
    def __init__(self, genesis: Block, mempool: Optional["Mempool"] = None) -> None:
        self._blocks: list[Block] = [genesis]
        self._hash_to_height: dict[bytes, int] = {genesis.block_hash: 0}
        self._hash_to_block: Dict[bytes, Block] = {genesis.block_hash: genesis}
        self._orphans = OrphanPool()
        self._mempool_sync = MempoolSync(mempool)

    # ── public read API ───────────────────────────────────────────────────────

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

    def get_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        return self._hash_to_block.get(block_hash)

    # ── public write API ──────────────────────────────────────────────────────

    def add_block(self, block: Block) -> bool:
        """
        Accept a new block from the network.

        Three cases:
          1. Parent known, block makes longer chain → switch_to_fork
          2. Parent known, block doesn't beat us   → record it, do nothing
          3. Parent unknown                         → park as orphan

        After any case, reconnect orphans that were waiting on this block.
        """
        if block.block_hash in self._hash_to_block or self._orphans.contains(block.block_hash):
            return False

        validate_block(block)

        if block.header.prev_hash not in self._hash_to_height:
            self._orphans.add(block)
        else:
            self._hash_to_block[block.block_hash] = block
            new_height = self._hash_to_height[block.header.prev_hash] + 1
            self._hash_to_height[block.block_hash] = new_height
            if new_height > self.height:
                self.switch_to_fork(self._build_fork_from(block))

        for child in self._orphans.pop_children_of(block.block_hash):
            self.add_block(child)

        return True

    def switch_to_fork(self, fork: list[Block]) -> None:
        """Replace the canonical chain with a longer fork."""
        if not fork:
            raise ValueError("fork is empty")
        ancestor_height = self._ancestor_height_of(fork)
        _validate_fork_chain(fork, fork[0].header.prev_hash)
        self._apply_fork(fork, ancestor_height)

    # ── fork resolution ───────────────────────────────────────────────────────

    def _build_fork_from(self, tip: Block) -> list[Block]:
        """Walk backwards from tip until we hit the canonical chain."""
        canonical = {b.block_hash for b in self._blocks}
        fork: list[Block] = []
        cur = tip
        while cur.block_hash not in canonical:
            fork.append(cur)
            parent = self._hash_to_block.get(cur.header.prev_hash)
            if parent is None:
                raise ValueError("cannot build fork: missing ancestor block")
            cur = parent
        fork.reverse()
        return fork

    def _ancestor_height_of(self, fork: list[Block]) -> int:
        base_prev = fork[0].header.prev_hash
        if base_prev not in self._hash_to_height:
            raise ValueError("fork does not connect to any known block")
        ancestor_height = self._hash_to_height[base_prev]
        new_height = ancestor_height + len(fork)
        if new_height <= self.height:
            raise ValueError(f"fork height {new_height} does not beat current height {self.height}")
        return ancestor_height

    def _apply_fork(self, fork: list[Block], ancestor_height: int) -> None:
        """Truncate the canonical chain to the ancestor and append the fork blocks."""
        orphaned = self._blocks[ancestor_height + 1:]
        self._blocks = self._blocks[:ancestor_height + 1]
        self._hash_to_height = {b.block_hash: h for h, b in enumerate(self._blocks)}

        for block in orphaned:
            self._mempool_sync.restore(block)
        for block in fork:
            self._blocks.append(block)
            self._hash_to_height[block.block_hash] = len(self._blocks) - 1
            self._hash_to_block[block.block_hash] = block
            self._mempool_sync.confirm(block)


def _validate_fork_chain(fork: list[Block], base_prev_hash: bytes) -> None:
    prev_hash = base_prev_hash
    for block in fork:
        if block.header.prev_hash != prev_hash:
            raise InvalidBlockError("fork blocks do not form a chain")
        validate_block(block)
        prev_hash = block.block_hash
