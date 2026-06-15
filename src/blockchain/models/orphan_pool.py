from blockchain.models import Block

class OrphanPool:
    def __init__(self) -> None:
        self._by_parent: dict[bytes, list[Block]] = {}
        self._hashes: set[bytes] = set()

    def contains(self, block_hash: bytes) -> bool:
        return block_hash in self._hashes

    def add(self, block: Block) -> None:
        if block.block_hash in self._hashes:
            return
        self._by_parent.setdefault(block.header.prev_hash, []).append(block)
        self._hashes.add(block.block_hash)

    def pop_children_of(self, parent_hash: bytes) -> list[Block]:
        children = self._by_parent.pop(parent_hash, [])
        for child in children:
            self._hashes.discard(child.block_hash)
        return children
