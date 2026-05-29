import pytest

from blockchain.block_utils import hash_block_header, satisfies_pow
from blockchain.miner import mine
from blockchain.models import BlockHeader

ZERO_HASH = b"\x00" * 32

def make_header(difficulty: int) -> BlockHeader:
    return BlockHeader(
        prev_hash=ZERO_HASH,
        txs_hash=ZERO_HASH,
        timestamp=1000000,
        difficulty=difficulty,
        nonce=0,
    )

class TestMine:
    def test_returned_hash_satisfies_difficulty(self):
        header, digest = mine(make_header(difficulty=4))
        assert satisfies_pow(digest, 4)

    def test_returned_hash_matches_returned_header(self):
        header, digest = mine(make_header(difficulty=4))
        assert hash_block_header(header) == digest

    def test_difficulty_zero_returns_immediately(self):
        header, digest = mine(make_header(difficulty=0))
        assert satisfies_pow(digest, 0)

    def test_mined_header_preserves_all_fields_except_nonce(self):
        original = make_header(difficulty=4)
        mined, _ = mine(original)
        assert mined.prev_hash == original.prev_hash
        assert mined.txs_hash == original.txs_hash
        assert mined.timestamp == original.timestamp
        assert mined.difficulty == original.difficulty

    def test_higher_difficulty_also_satisfies_lower(self):
        header, digest = mine(make_header(difficulty=6))
        assert satisfies_pow(digest, 4)
