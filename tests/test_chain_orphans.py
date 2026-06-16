
import hashlib
import pytest
from blockchain.core.chain import Chain
from blockchain.models.mempool import Mempool
from blockchain.models import Block, BlockHeader
from blockchain.core.block_utils import hash_block_header, hash_txs, satisfies_pow


@pytest.fixture
def genesis_block():
    header = BlockHeader(
        prev_hash=b"\x00" * 32,
        txs_hash=hashlib.sha256(b"").digest(),
        timestamp=1000000,
        difficulty=2,  # low difficulty for fast tests
        nonce=0,
    )
    block_hash = hash_block_header(header)
    return Block(header=header, block_hash=block_hash, tx_hashes=tuple())


@pytest.fixture
def chain(genesis_block):
    return Chain(genesis_block, Mempool())


def make_block(prev_hash: bytes, nonce: int = 0, difficulty: int = 2, tx_hashes: tuple = None) -> Block:
    if tx_hashes is None:
        tx_hashes = tuple()
    
    txs_hash = hash_txs(list(tx_hashes))
    
    # Find a nonce that satisfies PoW
    nonce_candidate = nonce
    while True:
        header = BlockHeader(
            prev_hash=prev_hash,
            txs_hash=txs_hash,
            timestamp=1000000,
            difficulty=difficulty,
            nonce=nonce_candidate,
        )
        bh = hash_block_header(header)
        if satisfies_pow(bh, difficulty):
            return Block(header=header, block_hash=bh, tx_hashes=tx_hashes)
        nonce_candidate += 1


class TestOrphanHandling:

    def test_orphan_buffered_when_parent_missing(self, chain, genesis_block):
        block1 = make_block(genesis_block.block_hash)
        block2 = make_block(block1.block_hash)  # depends on block1
        
        # Add block2 before block1; block2 should be buffered as orphan
        success = chain.add_block(block2)
        assert success is True
        assert chain.height == 0  # chain not extended yet

    def test_orphan_attached_when_parent_arrives(self, chain, genesis_block):
        block1 = make_block(genesis_block.block_hash)
        block2 = make_block(block1.block_hash)

        print("\n" + "=" * 72)
        print("TEST: ORPHAN RECONNECT WHEN PARENT ARRIVES")
        print("=" * 72)
        print()
        print(f"START:  {chain._chain_view()}")
        print()

        # Add block2 first (orphan)
        print(f"TEST: RECEIVED CHILD FIRST {block2.block_hash.hex()[:8]}")
        chain.add_block(block2)
        assert chain.height == 0

        print()
        print("STATE: child is buffered as orphan; canonical chain unchanged")
        print(f"CHAIN:  {chain._chain_view()}")
        print()

        # Add block1 (parent of orphan)
        print(f"TEST: RECEIVED MISSING PARENT {block1.block_hash.hex()[:8]}")
        chain.add_block(block1)

        print()
        print("STATE: parent connects and buffered orphan attaches automatically")
        print(f"FINAL:  {chain._chain_view()}")
        print()
        assert chain.height == 2  # chain extended through both blocks
        assert chain.tip.block_hash == block2.block_hash

    def test_multiple_orphans_attached_sequentially(self, chain, genesis_block):
        block1 = make_block(genesis_block.block_hash)
        block2 = make_block(block1.block_hash)
        block3 = make_block(block2.block_hash)
        
        # Add all out of order
        chain.add_block(block3)
        chain.add_block(block2)
        assert chain.height == 0  # still at genesis
        
        chain.add_block(block1)
        assert chain.height == 3
        assert chain.tip.block_hash == block3.block_hash


    def test_deep_orphan_chain_attachment(self, chain, genesis_block):
        block1 = make_block(genesis_block.block_hash)
        block2 = make_block(block1.block_hash)
        block3 = make_block(block2.block_hash)
        block4 = make_block(block3.block_hash)
        block5 = make_block(block4.block_hash)
        
        # Add all blocks out of order (reverse)
        chain.add_block(block5)
        chain.add_block(block4)
        chain.add_block(block3)
        chain.add_block(block2)
        assert chain.height == 0  # all still orphans
        
        # Add root block
        chain.add_block(block1)
        assert chain.height == 5
        assert chain.tip.block_hash == block5.block_hash
