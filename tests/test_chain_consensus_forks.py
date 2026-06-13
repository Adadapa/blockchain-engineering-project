"""
Tests for fork handling, consensus (longest-chain rule), and block validation.
"""
import hashlib
import pytest
from blockchain.core.chain import Chain
from blockchain.core.mempool import Mempool
from blockchain.core.models import Block, BlockHeader
from blockchain.core.block_utils import hash_block_header, hash_txs, satisfies_pow
from blockchain.core.models.block import InvalidBlockError


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
    return Chain(genesis_block, Mempool())


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


class TestForkAndConsensus:

    def test_fork_switch_when_longer_branch_arrives(self, chain, genesis_block):
        """When a longer branch arrives, switch to it (longest-chain rule)."""
        # Build main chain: genesis -> A -> B
        blockA = make_block(genesis_block.block_hash)
        blockB = make_block(blockA.block_hash)
        
        chain.add_block(blockA)
        chain.add_block(blockB)
        assert chain.height == 2
        assert chain.tip.block_hash == blockB.block_hash
        
        # Build competing branch from genesis: genesis -> A' -> B' -> C'
        blockA_prime = make_block(genesis_block.block_hash)
        blockB_prime = make_block(blockA_prime.block_hash)
        blockC_prime = make_block(blockB_prime.block_hash)
        
        # Add competing blocks in order
        chain.add_block(blockA_prime)
        assert chain.height == 2  # no switch yet, same height
        
        chain.add_block(blockB_prime)
        assert chain.height == 2  # still height 2, both branches equal
        
        chain.add_block(blockC_prime)
        # Now competing branch is longer, should switch
        assert chain.height == 3
        assert chain.tip.block_hash == blockC_prime.block_hash

    def test_fork_switch_deep_reorg(self, chain, genesis_block):
        """Reorg can happen multiple levels deep."""
        # Main chain: genesis -> A -> B -> C
        blockA = make_block(genesis_block.block_hash)
        blockB = make_block(blockA.block_hash)
        blockC = make_block(blockB.block_hash)
        
        chain.add_block(blockA)
        chain.add_block(blockB)
        chain.add_block(blockC)
        assert chain.height == 3
        main_tip = chain.tip.block_hash
        
        # Competing branch at same height as blockB: genesis -> A' -> B'
        blockA_prime = make_block(genesis_block.block_hash)
        blockB_prime = make_block(blockA_prime.block_hash)
        
        chain.add_block(blockA_prime)
        chain.add_block(blockB_prime)
        assert chain.height == 3
        assert chain.tip.block_hash == main_tip  # no switch, still shorter
        
        # Extend competing branch: genesis -> A' -> B' -> C' -> D'
        blockC_prime = make_block(blockB_prime.block_hash)
        blockD_prime = make_block(blockC_prime.block_hash)
        
        chain.add_block(blockC_prime)
        chain.add_block(blockD_prime)
        
        # Competing branch is now longer (height 4 vs 3); reorg should happen
        assert chain.height == 4
        assert chain.tip.block_hash == blockD_prime.block_hash

    def test_side_branch_stored_for_future_extension(self, chain, genesis_block):
        """Side branches are kept so they can be extended and potentially become main chain."""
        blockA = make_block(genesis_block.block_hash)
        blockA_prime = make_block(genesis_block.block_hash)
        
        chain.add_block(blockA)
        chain.add_block(blockA_prime)
        
        # blockA is main, blockA_prime is side branch
        assert chain.height == 1
        assert chain.tip.block_hash == blockA.block_hash
        
        # Extend side branch
        blockB_prime = make_block(blockA_prime.block_hash)
        chain.add_block(blockB_prime)
        
        # Side branch overtakes main chain
        assert chain.height == 2
        assert chain.tip.block_hash == blockB_prime.block_hash

    def test_longest_chain_wins_with_multiple_forks(self, chain, genesis_block):
        """With multiple competing branches, the longest one becomes canonical."""
        # Main:  genesis -> A -> B
        # Fork1: genesis -> A' -> B'
        # Fork2: genesis -> A'' -> B'' -> C''
        
        blockA = make_block(genesis_block.block_hash)
        blockB = make_block(blockA.block_hash)
        chain.add_block(blockA)
        chain.add_block(blockB)
        
        blockA_prime = make_block(genesis_block.block_hash)
        blockB_prime = make_block(blockA_prime.block_hash)
        chain.add_block(blockA_prime)
        chain.add_block(blockB_prime)
        
        blockA_double_prime = make_block(genesis_block.block_hash)
        blockB_double_prime = make_block(blockA_double_prime.block_hash)
        blockC_double_prime = make_block(blockB_double_prime.block_hash)
        
        chain.add_block(blockA_double_prime)
        chain.add_block(blockB_double_prime)
        chain.add_block(blockC_double_prime)
        
        # Fork2 is longest; should be main chain
        assert chain.height == 3
        assert chain.tip.block_hash == blockC_double_prime.block_hash


class TestBlockValidation:
    """Test that invalid blocks are rejected."""

    def test_invalid_pow_rejected(self, chain, genesis_block):
        """Block with invalid PoW is rejected."""
        # Create a block with insufficient PoW (high difficulty but low nonce effort)
        header = BlockHeader(
            prev_hash=genesis_block.block_hash,
            txs_hash=hashlib.sha256(b"").digest(),
            timestamp=1000000,
            difficulty=20,  # require 20 leading zero bits
            nonce=0,  # but don't mine it
        )
        bad_block = Block(header=header, block_hash=hash_block_header(header), tx_hashes=tuple())
        
        with pytest.raises(InvalidBlockError, match="PoW not satisfied"):
            chain.add_block(bad_block)

    def test_mismatched_txs_hash_rejected(self, chain, genesis_block):
        """Block with mismatched txs_hash is rejected."""
        # Create a block with wrong txs_hash
        tx_hashes = (b"\x01" * 32, b"\x02" * 32)
        wrong_txs_hash = hashlib.sha256(b"garbage").digest()  # intentionally wrong
        
        header = BlockHeader(
            prev_hash=genesis_block.block_hash,
            txs_hash=wrong_txs_hash,
            timestamp=1000000,
            difficulty=2,
            nonce=0,
        )
        # Mine the header to satisfy PoW
        nonce = 0
        while True:
            candidate_header = BlockHeader(
                prev_hash=header.prev_hash,
                txs_hash=header.txs_hash,
                timestamp=header.timestamp,
                difficulty=header.difficulty,
                nonce=nonce,
            )
            bh = hash_block_header(candidate_header)
            if satisfies_pow(bh, 2):
                break
            nonce += 1
        
        bad_block = Block(header=candidate_header, block_hash=bh, tx_hashes=tx_hashes)
        
        with pytest.raises(InvalidBlockError, match="txs_hash mismatch"):
            chain.add_block(bad_block)

    def test_invalid_block_rejected_despite_valid_parent(self, chain, genesis_block):
        """Invalid block is rejected even if its parent is valid."""
        # Create a valid block first
        blockA = make_block(genesis_block.block_hash)
        chain.add_block(blockA)
        
        # Try to add an invalid block with valid parent
        header = BlockHeader(
            prev_hash=blockA.block_hash,
            txs_hash=hashlib.sha256(b"").digest(),
            timestamp=1000000,
            difficulty=20,  # require 20 leading zero bits
            nonce=0,  # but don't mine it
        )
        bad_block = Block(header=header, block_hash=hash_block_header(header), tx_hashes=tuple())
        
        with pytest.raises(InvalidBlockError, match="PoW not satisfied"):
            chain.add_block(bad_block)
        
        # Chain should still be at blockA
        assert chain.height == 1
        assert chain.tip.block_hash == blockA.block_hash

