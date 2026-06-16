from .block_utils import validate_block
from blockchain.models import Block
from blockchain.models.orphan_pool import OrphanPool
from blockchain.models.mempool_sync import MempoolSync
from typing import TYPE_CHECKING, Dict, Optional
from .fork_manager import ForkManager

if TYPE_CHECKING:
    from blockchain.models.mempool import Mempool

class Chain:
    def __init__(self, genesis: Block, mempool: "Mempool") -> None:
        self.blocks: list[Block] = [genesis]
        self._hash_to_height: dict[bytes, int] = {genesis.block_hash: 0}
        self._hash_to_block: Dict[bytes, Block] = {genesis.block_hash: genesis}
        self._orphans = OrphanPool()
        self._mempool_sync = MempoolSync(mempool)
        self._forks = ForkManager(self)

    @property
    def height(self) -> int:
        return len(self.blocks) - 1

    @property
    def tip(self) -> Block:
        return self.blocks[-1]

    def block_at(self, height: int) -> Block:
        if height < 0 or height > self.height:
            raise IndexError(f"no block at height {height}, chain height is {self.height}")
        return self.blocks[height]

    def contains(self, block_hash: bytes) -> bool:
        return block_hash in self._hash_to_height

    def get_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        return self._hash_to_block.get(block_hash)

    def add_block(self, block: Block) -> bool:
        if self._already_known(block):
            return False

        validate_block(block)

        if block.header.prev_hash not in self._hash_to_height:
            print(f"Orphan {block.block_hash.hex()[:16]}")
            self._orphans.add(block)
        else:
            print(f"Add {block.block_hash.hex()[:16]}")
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
            new_fork = self._forks.build_fork_from(block)
            self._forks.switch_to_fork(new_fork)

    def _reconnect_orphans(self, parent_hash: bytes) -> None:
        for child in self._orphans.pop_children_of(parent_hash):
            self.add_block(child)

    # extend the canonical chain by one block
    def _append_to_chain(self, block: Block) -> None:
        self.blocks.append(block)
        self._hash_to_height[block.block_hash] = len(self.blocks) - 1
        self._hash_to_block[block.block_hash] = block

        self._mempool_sync.on_block_added(block)
        print(f"Height {self.height} {self._chain_view()}")

    def _chain_view(self) -> str:
        # Used for pretty-printing the chain state
        parts = []
        for height, block in enumerate(self.blocks):
            txs = ",".join(tx_hash.hex()[:8] for tx_hash in block.tx_hashes)
            parts.append(
                f"{height}:{block.block_hash.hex()[:8]} txs=[{txs}]"
                if block.tx_hashes
                else f"{height}:{block.block_hash.hex()[:8]} txs=[]"
            )
        return " -> ".join(parts)


