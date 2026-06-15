from blockchain.models import Block
from blockchain.models import InvalidBlockError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chain import Chain


class ForkManager:
    def __init__(self, chain: "Chain"):
        self.chain = chain

    # replace the canonical chain with a longer fork
    def switch_to_fork(self, fork: list[Block]) -> None:
        if not fork:
            raise ValueError("fork is empty")
        ancestor_height = self._ancestor_height_of(fork)
        _check_fork_links(fork, fork[0].header.prev_hash)

        self._apply_fork(fork, ancestor_height)

    # walk backwards from tip until we hit the canonical chain
    def build_fork_from(self, tip: Block) -> list[Block]:
        canonical = {b.block_hash for b in self.chain.blocks}
        fork: list[Block] = []
        cur = tip
        while cur.block_hash not in canonical:
            fork.append(cur)
            parent = self.chain._hash_to_block.get(cur.header.prev_hash)
            if parent is None:
                raise ValueError("cannot build fork: missing ancestor block")
            cur = parent
        fork.reverse()
        return fork

    def _ancestor_height_of(self, fork: list[Block]) -> int:
        base_prev = fork[0].header.prev_hash
        if base_prev not in self.chain._hash_to_height:
            raise ValueError("fork does not connect to any known block")
        ancestor_height = self.chain._hash_to_height[base_prev]
        new_height = ancestor_height + len(fork)
        if new_height <= self.chain.height:
            raise ValueError(f"fork height {new_height} does not beat current height {self.chain.height}")
        return ancestor_height

    def _apply_fork(self, fork: list[Block], ancestor_height: int) -> None:
        self.rollback_to(ancestor_height)
        for block in fork:
            self.chain._append_to_chain(block)

    # remove blocks above ancestor_height from the canonical chain
    def rollback_to(self, ancestor_height: int) -> None:
        evicted = self.chain.blocks[ancestor_height + 1:]
        self.chain.blocks = self.chain.blocks[:ancestor_height + 1]
        self.chain._hash_to_height = {b.block_hash: h for h, b in enumerate(self.chain.blocks)}
        for block in evicted:
            self.chain._mempool_sync.restore(block)


# verify that each block's prev_hash connects to the next
def _check_fork_links(fork: list[Block], base_prev_hash: bytes) -> None:
    prev_hash = base_prev_hash
    for block in fork:
        if block.header.prev_hash != prev_hash:
            raise InvalidBlockError("fork blocks do not form a chain")
        prev_hash = block.block_hash
