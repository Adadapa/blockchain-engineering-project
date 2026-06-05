from .block_utils import validate_block
from .models import Block
from .models.block import InvalidBlockError
from typing import Dict, List, Optional

class Chain:
    def __init__(self, genesis: Block) -> None:
        self._blocks: list[Block] = [genesis]
        self._hash_to_height: dict[bytes, int] = {genesis.block_hash: 0}
        self._hash_to_block: Dict[bytes, Block] = {genesis.block_hash: genesis}
        self._orphans_by_parent: Dict[bytes, List[Block]] = {}
        self._orphan_set = set()

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
        self._hash_to_block[block.block_hash] = block
        # TODO: remove block.tx_hashes from the mempool here after this block is
        # added to self._blocks, because these transactions are now in a block
        # we are keeping and should not be mined again.
        # TODO: if we later stop using this block, its transactions may need to
        # be put back into the mempool.
        return True

    # Returns True if the block is recorded new and False if it was already known
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

            # if this branch overtakes the current tip, assemble fork and switch
            if new_height > self.height:
                self.switch_to_fork([block])
                # TODO: after switch_to_fork starts using this block, remove this
                # block's tx_hashes from the mempool so they are not mined again.
                # TODO: later, when support is added for switching away from old
                # blocks, their transactions may need to go back into the mempool.
        else:
            # this is an orphan
            if bh in self._orphan_set:
                return False
            self._orphans_by_parent.setdefault(parent, []).append(block)
            self._orphan_set.add(bh)

        # Check for orphans of this block
        children = self._orphans_by_parent.pop(bh, [])
        for child in children:
            self._orphan_set.discard(child.block_hash)
            self.add_block(child)

        return True

    def get_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        return self._hash_to_block.get(block_hash)

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
        # TODO: for each block added below, remove its tx_hashes from the mempool
        # after it is appended to self._blocks so those transactions are not
        # mined again.
        # TODO: the blocks removed by the truncation above are not handled yet;
        # if we stop using them, their transactions may need to go back into
        # the mempool.

        for block in fork:
            height = len(self._blocks)
            self._blocks.append(block)
            self._hash_to_height[block.block_hash] = height
            self._hash_to_block[block.block_hash] = block

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
