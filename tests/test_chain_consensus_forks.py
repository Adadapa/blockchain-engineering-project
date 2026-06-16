
import hashlib
import pytest
from blockchain.core.chain import Chain
from blockchain.models.mempool import Mempool
from blockchain.models import Block, BlockHeader
from blockchain.core.block_utils import hash_block_header, hash_txs, satisfies_pow
from blockchain.models.block import InvalidBlockError


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
        # Build main chain: genesis -> A -> B
        blockA = make_block(genesis_block.block_hash, 0)
        blockB = make_block(blockA.block_hash, 1)
        
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
        # Main chain: genesis -> A -> B -> C
        blockA = make_block(genesis_block.block_hash)
        blockB = make_block(blockA.block_hash)
        blockC = make_block(blockB.block_hash)
        
        chain.add_block(blockA)
        chain.add_block(blockB)
        chain.add_block(blockC)
        assert chain.height == 3
        main_tip = chain.tip.block_hash
        print("\n" + "=" * 72)
        print("TEST: CANONICAL CHAIN BEFORE COMPETING BRANCH")
        print("=" * 72)
        print("Genesis -> A -> B -> C")
        print()
        print(f"BEFORE: {chain._chain_view()}")
        print()
        
        # Competing branch after A: genesis -> A -> B'
        blockB_prime = make_block(blockA.block_hash, 5)

        print(
            f"TEST: RECEIVED BLOCK B' {blockB_prime.block_hash.hex()[:8]} "
            f"(parent {blockB_prime.header.prev_hash.hex()[:8]})"
        )
        chain.add_block(blockB_prime)
        assert chain.height == 3
        assert chain.tip.block_hash == main_tip  # no switch, still shorter
        
        # Extend competing branch: genesis -> A -> B' -> C' -> D'
        blockC_prime = make_block(blockB_prime.block_hash, 6)
        blockD_prime = make_block(blockC_prime.block_hash, 7)

        print(
            f"TEST: RECEIVED BLOCK C' {blockC_prime.block_hash.hex()[:8]} "
            f"(parent {blockC_prime.header.prev_hash.hex()[:8]})"
        )
        chain.add_block(blockC_prime)

        print(
            f"TEST: RECEIVED BLOCK D' {blockD_prime.block_hash.hex()[:8]} "
            f"(parent {blockD_prime.header.prev_hash.hex()[:8]})"
        )
        chain.add_block(blockD_prime)
        
        # Competing branch is now longer (height 4 vs 3); reorg should happen
        print()
        print("=" * 72)
        print("TEST: CANONICAL CHAIN AFTER COMPETING BRANCH PROCESSING")
        print("=" * 72)
        print()
        print(f"AFTER:  {chain._chain_view()}")
        print()
        assert chain.height == 4
        assert chain.tip.block_hash == blockD_prime.block_hash

    def test_side_branch_stored_for_future_extension(self, chain, genesis_block):
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
        # Main:  genesis -> A -> B
        # Fork1: genesis -> A' -> B'
        # Fork2: genesis -> A'' -> B'' -> C''
        
        blockA = make_block(genesis_block.block_hash)
        blockB = make_block(blockA.block_hash)
        chain.add_block(blockA)
        chain.add_block(blockB)

        print("\n" + "=" * 72)
        print("TEST: MULTI-FORK RACE - INITIAL CANONICAL CHAIN")
        print("=" * 72)
        print()
        print(f"CANONICAL: {chain._chain_view()}")
        print()

        blockA_prime = make_block(genesis_block.block_hash, 10)
        blockB_prime = make_block(blockA_prime.block_hash, 11)
        print(f"TEST: RECEIVED FORK1 BLOCK A' {blockA_prime.block_hash.hex()[:8]}")
        chain.add_block(blockA_prime)
        print(f"STATE: {chain._chain_view()}")
        print()
        print(f"TEST: RECEIVED FORK1 BLOCK B' {blockB_prime.block_hash.hex()[:8]}")
        chain.add_block(blockB_prime)
        print(f"STATE: {chain._chain_view()}")
        print()

        blockA_double_prime = make_block(genesis_block.block_hash, 20)
        blockB_double_prime = make_block(blockA_double_prime.block_hash, 21)
        blockC_double_prime = make_block(blockB_double_prime.block_hash, 22)

        print(f"TEST: RECEIVED FORK2 BLOCK A'' {blockA_double_prime.block_hash.hex()[:8]}")
        chain.add_block(blockA_double_prime)
        print(f"STATE: {chain._chain_view()}")
        print()
        print(f"TEST: RECEIVED FORK2 BLOCK B'' {blockB_double_prime.block_hash.hex()[:8]}")
        chain.add_block(blockB_double_prime)
        print(f"STATE: {chain._chain_view()}")
        print()
        print(f"TEST: RECEIVED FORK2 BLOCK C'' {blockC_double_prime.block_hash.hex()[:8]}")
        chain.add_block(blockC_double_prime)

        print()
        print("=" * 72)
        print("TEST: MULTI-FORK RACE - FINAL CANONICAL CHAIN")
        print("=" * 72)
        print()
        print(f"WINNER:    {chain._chain_view()}")
        print()

        # Fork2 is longest; should be main chain
        assert chain.height == 3
        assert chain.tip.block_hash == blockC_double_prime.block_hash


class TestBlockValidation:

    def test_invalid_pow_rejected(self, chain, genesis_block):
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
        # Create a block with wrong txs_hash
        tx_hashes = (b"\x01" * 32, b"\x02" * 32)
        wrong_txs_hash = hashlib.sha256(b"garbage").digest()  # wrong
        
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
