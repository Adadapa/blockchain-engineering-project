import hashlib
import pytest

from blockchain.core.block_utils import hash_block_header, hash_txs
from blockchain.core.chain import Chain
from blockchain.core.models import InvalidBlockError
from blockchain.core.models import Block, BlockHeader
from blockchain.core.miner import mine

ZERO_HASH = b"\x00" * 32
EMPTY_TXS_HASH = hashlib.sha256(b"").digest()

def make_genesis() -> Block:
    header, block_hash = mine(BlockHeader(
        prev_hash=ZERO_HASH,
        txs_hash=EMPTY_TXS_HASH,
        timestamp=1000000,
        difficulty=4,
        nonce=0,
    ))
    return Block(header=header, block_hash=block_hash, tx_hashes=())

def mine_next(parent: Block, difficulty: int = 4) -> Block:
    header, block_hash = mine(BlockHeader(
        prev_hash=parent.block_hash,
        txs_hash=EMPTY_TXS_HASH,
        timestamp=parent.header.timestamp + 1,
        difficulty=difficulty,
        nonce=0,
    ))
    return Block(header=header, block_hash=block_hash, tx_hashes=())

class TestChainInit:
    def test_height_is_zero_after_init(self):
        genesis = make_genesis()
        chain = Chain(genesis)

        assert chain.height == 0

    def test_tip_is_genesis(self):
        genesis = make_genesis()
        chain = Chain(genesis)

        assert chain.tip == genesis

    def test_block_at_zero_is_genesis(self):
        genesis = make_genesis()
        chain = Chain(genesis)

        assert chain.block_at(0) == genesis

    def test_contains_genesis_hash(self):
        genesis = make_genesis()
        chain = Chain(genesis)

        assert chain.contains(genesis.block_hash)


class TestSwitchToFork:
    def test_switches_to_longer_fork(self):
        genesis = make_genesis()
        chain = Chain(genesis)
        block1 = mine_next(genesis)
        chain.add_block(block1)

        # fork from genesis
        fork1 = mine_next(genesis)
        fork2 = mine_next(fork1)
        chain.switch_to_fork([fork1, fork2])

        assert chain.height == 2
        assert chain.tip == fork2

    def test_raises_if_fork_not_longer(self):
        genesis = make_genesis()
        chain = Chain(genesis)
        block1 = mine_next(genesis)
        block2 = mine_next(block1)

        chain.add_block(block1)
        chain.add_block(block2)
        fork1 = mine_next(genesis)

        with pytest.raises(ValueError):
            chain.switch_to_fork([fork1])

    def test_raises_on_empty_fork(self):
        genesis = make_genesis()
        chain = Chain(genesis)

        with pytest.raises(ValueError):
            chain.switch_to_fork([])

    def test_raises_if_fork_does_not_connect(self):
        genesis = make_genesis()
        chain = Chain(genesis)

        orphan_header = BlockHeader(
            prev_hash=b"\xFF" * 32,
            txs_hash=EMPTY_TXS_HASH,
            timestamp=9999999,
            difficulty=4,
            nonce=0,
        )
        mined, block_hash = mine(orphan_header)
        orphan = Block(header=mined, block_hash=block_hash, tx_hashes=())

        with pytest.raises(ValueError):
            chain.switch_to_fork([orphan])
