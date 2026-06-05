from .block_utils import validate_block
from .models import Block
from .models.block import InvalidBlockError
from .orphan_pool import OrphanPool
from .mempool_sync import MempoolSync
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .mempool import Mempool

class Chain:
    def __init__(self, genesis: Block, mempool: "Mempool") -> None:
        self._blocks: list[Block] = [genesis]
        self._hash_to_height: dict[bytes, int] = {genesis.block_hash: 0}
        self._hash_to_block: Dict[bytes, Block] = {genesis.block_hash: genesis}
        self._orphans = OrphanPool()
        self._mempool_sync = MempoolSync(mempool)

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

    def add_block(self, block: Block) -> bool:
        if self._already_known(block):
            return False

        validate_block(block)

        if block.header.prev_hash not in self._hash_to_height:
            print(f"[Chain] Orphan {block.block_hash.hex()[:16]}...")
            self._orphans.add(block)
        else:
            print(f"[Chain] Add {block.block_hash.hex()[:16]}...")
            self._connect_block(block)

        self._reconnect_orphans(block.block_hash)
        return True

    def _already_known(self, block: Block) -> bool:
        return block.block_hash in self._hash_to_block or self._orphans.contains(block.block_hash)

    # index the block and switch to its fork if it beats the current tip
    def _connect_block(self, block: Block) -> None:
        self._hash_to_block[block.block_hash] = block
        new_height = self._hash_to_height[block.header.prev_hash] + 1
        self._hash_to_height[block.block_hash] = new_height

        if new_height > self.height:
            new_fork = self._build_fork_from(block)
            self.switch_to_fork(new_fork)

    def _reconnect_orphans(self, parent_hash: bytes) -> None:
        for child in self._orphans.pop_children_of(parent_hash):
            self.add_block(child)

    # fork logic ------------------------------------------------------------------------------------------------------

    # replace the canonical chain with a longer fork
    def switch_to_fork(self, fork: list[Block]) -> None:
        if not fork:
            raise ValueError("fork is empty")
        ancestor_height = self._ancestor_height_of(fork)
        _check_fork_links(fork, fork[0].header.prev_hash)

        self._apply_fork(fork, ancestor_height)

    # walk backwards from tip until we hit the canonical chain
    def _build_fork_from(self, tip: Block) -> list[Block]:
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
        self._rollback_to(ancestor_height)
        for block in fork:
            self._append_to_chain(block)

    # remove blocks above ancestor_height from the canonical chain
    # and return their txs to the mempool
    def _rollback_to(self, ancestor_height: int) -> None:
        evicted = self._blocks[ancestor_height + 1:]
        self._blocks = self._blocks[:ancestor_height + 1]
        self._hash_to_height = {b.block_hash: h for h, b in enumerate(self._blocks)}
        for block in evicted:
            self._mempool_sync.restore(block)

    # extend the canonical chain by one block
    # and remove its txs from the mempool
    def _append_to_chain(self, block: Block) -> None:
        self._blocks.append(block)
        self._hash_to_height[block.block_hash] = len(self._blocks) - 1
        self._hash_to_block[block.block_hash] = block

        self._mempool_sync.on_block_added(block)
        print(f"[Chain] h={self.height} {self._chain_view()}")

    def _chain_view(self) -> str:
        parts = [f"{height}:{block.block_hash.hex()[:8]}" for height, block in enumerate(self._blocks)]
        return " -> ".join(parts)

# verify that each block's prev_hash connects to the next
def _check_fork_links(fork: list[Block], base_prev_hash: bytes) -> None:
    prev_hash = base_prev_hash
    for block in fork:
        if block.header.prev_hash != prev_hash:
            raise InvalidBlockError("fork blocks do not form a chain")
        prev_hash = block.block_hash
