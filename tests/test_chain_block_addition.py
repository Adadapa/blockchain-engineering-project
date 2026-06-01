"""
Tests for basic block addition and chain queries.
"""
import hashlib
import pytest
from blockchain.chain import Chain
from blockchain.models import Block, BlockHeader
from blockchain.block_utils import hash_block_header, hash_txs, satisfies_pow


@pytest.fixture
def genesis_block():
    """Create a valid genesis block."""
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
    """Create a fresh chain with genesis block."""
    return Chain(genesis_block)


def make_block(prev_hash: bytes, nonce: int = 0, difficulty: int = 2, tx_hashes: tuple = None) -> Block:
    """
    Helper to create a valid block.
    Mines a block with given parent hash and difficulty.
    """
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


class TestBasicBlockAddition:
    """Test adding valid blocks that extend the current tip."""

    def test_add_block_extends_tip(self, chain, genesis_block):
        """Adding a block with correct parent extends the chain."""
        block1 = make_block(genesis_block.block_hash)
        
        success = chain.add_block(block1)
        assert success is True
        assert chain.height == 1
        assert chain.tip.block_hash == block1.block_hash

    def test_add_multiple_blocks_sequentially(self, chain, genesis_block):
        """Add multiple blocks in sequence."""
        block1 = make_block(genesis_block.block_hash)
        block2 = make_block(block1.block_hash)
        block3 = make_block(block2.block_hash)
        
        chain.add_block(block1)
        chain.add_block(block2)
        chain.add_block(block3)
        
        assert chain.height == 3
        assert chain.tip.block_hash == block3.block_hash
        assert chain.block_at(0).block_hash == genesis_block.block_hash
        assert chain.block_at(1).block_hash == block1.block_hash
        assert chain.block_at(2).block_hash == block2.block_hash
        assert chain.block_at(3).block_hash == block3.block_hash

    def test_duplicate_block_rejected(self, chain, genesis_block):
        """Adding the same block twice returns False."""
        block1 = make_block(genesis_block.block_hash)
        
        assert chain.add_block(block1) is True
        assert chain.add_block(block1) is False  # duplicate
        assert chain.height == 1


class TestChainQueries:
    """Test querying the chain for blocks."""

    def test_get_block_by_hash_main_chain(self, chain, genesis_block):
        """Retrieve blocks from main chain by hash."""
        block1 = make_block(genesis_block.block_hash)
        chain.add_block(block1)
        
        retrieved = chain.get_block_by_hash(block1.block_hash)
        assert retrieved == block1

    def test_contains_on_main_chain(self, chain, genesis_block):
        """Check if a block is on main chain."""
        block1 = make_block(genesis_block.block_hash)
        chain.add_block(block1)
        
        assert chain.contains(block1.block_hash) is True
        assert chain.contains(b"\xFF" * 32) is False

    def test_block_at_height(self, chain, genesis_block):
        """Retrieve block by height."""
        block1 = make_block(genesis_block.block_hash)
        block2 = make_block(block1.block_hash)
        
        chain.add_block(block1)
        chain.add_block(block2)
        
        assert chain.block_at(0).block_hash == genesis_block.block_hash
        assert chain.block_at(1).block_hash == block1.block_hash
        assert chain.block_at(2).block_hash == block2.block_hash
        
        with pytest.raises(IndexError):
            chain.block_at(10)

