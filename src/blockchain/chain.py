from .block_utils import validate_block
from .models import Block
from .models.block import InvalidBlockError

class Chain:
    def __init__(self, genesis: Block) -> None:
        self._blocks: list[Block] = [genesis]
        self._hash_to_height: dict[bytes, int] = {genesis.block_hash: 0}

    @property
    def height(self) -> int:
        return len(self._blocks) - 1

    ## current head of the chain of blocks
    @property
    def tip(self) -> Block:
        return self._blocks[-1]

    def block_at(self, height: int) -> Block:
        if height < 0 or height > self.height:
            raise IndexError(f"no block at height {height}, chain height is {self.height}")
        return self._blocks[height]

    def contains(self, block_hash: bytes) -> bool:
        return block_hash in self._hash_to_height

    ## validate and append a block if it extends the current tip
    def try_append(self, block: Block) -> bool:
        if block.header.prev_hash != self.tip.block_hash:
            return False

        validate_block(block)

        height = self.height + 1
        self._blocks.append(block)
        self._hash_to_height[block.block_hash] = height
        return True

    ## find the height of the common ancestor of current chain,
    ## and check the fork is longer
    def _find_ancestor_height(self, fork: list[Block]) -> int:
        fork_base_prev_hash = fork[0].header.prev_hash
        if fork_base_prev_hash not in self._hash_to_height:
            raise ValueError("fork does not connect to any known block")

        ancestor_height = self._hash_to_height[fork_base_prev_hash]
        new_height = ancestor_height + len(fork)

        if new_height <= self.height:
            raise ValueError(f"fork height {new_height} is not longer than current chain height {self.height}")

        return ancestor_height

    ## truncate the chain to the common ancestor and append the fork blocks
    def _apply_fork(self, fork: list[Block], ancestor_height: int) -> None:
        self._blocks = self._blocks[:ancestor_height + 1]
        self._hash_to_height = {b.block_hash: h for h, b in enumerate(self._blocks)}

        for block in fork:
            height = len(self._blocks)
            self._blocks.append(block)
            self._hash_to_height[block.block_hash] = height

    ## switch the canonical chain to a longer fork
    ## todo: the networking layer must fetch all missing blocks from peers before calling this
    def switch_to_fork(self, fork: list[Block]) -> None:
        if not fork:
            raise ValueError("fork is empty")

        ancestor_height = self._find_ancestor_height(fork)
        _validate_fork_chain(fork, fork[0].header.prev_hash)
        self._apply_fork(fork, ancestor_height)

## validate each block in the fork
def _validate_fork_chain(fork: list[Block], ancestor_prev_hash: bytes) -> None:
    prev_hash = ancestor_prev_hash
    for block in fork:
        if block.header.prev_hash != prev_hash:
            raise InvalidBlockError("fork blocks do not form a chain")
        validate_block(block)
        prev_hash = block.block_hash