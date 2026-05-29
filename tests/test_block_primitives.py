import hashlib
import struct

import pytest

from lab_group_client.blockchain.block import (
    count_leading_zero_bits,
    hash_block_header,
    hash_transaction,
    hash_txs,
    satisfies_pow,
)
from lab_group_client.blockchain.models import BlockHeader, HEADER_SIZE, Transaction

ZERO_HASH = b"\x00" * 32

# unit tests for block primitives :)

# header packing
class TestHeaderPacking:

    ## setup a default header for tests
    def _make_header(self, **overrides) -> BlockHeader:
        defaults = dict(
            prev_hash=b"\x01" * 32,
            txs_hash=b"\x02" * 32,
            timestamp=1000000,
            difficulty=8,
            nonce=42,
        )
        defaults.update(overrides)
        return BlockHeader(**defaults)

    def test_packed_length_is_84(self):
        assert len(self._make_header().pack()) == 84

    def test_roundtrip(self):
        h = self._make_header()
        assert BlockHeader.unpack(h.pack()) == h

    ## tests to check that each field lands at the correct byte offset in the header
    def test_prev_hash_is_at_offset_0(self):
        sample_32_bytes = b"\xAA" * 32
        packed = self._make_header(prev_hash=sample_32_bytes).pack()
        assert packed[0:32] == sample_32_bytes

    def test_txs_hash_is_at_offset_32(self):
        sample_32_bytes = b"\xBB" * 32
        packed = self._make_header(txs_hash=sample_32_bytes).pack()
        assert packed[32:64] == sample_32_bytes

    def test_timestamp_is_big_endian_uint64(self):
        ts = 0x0102030405060708
        packed = self._make_header(timestamp=ts).pack()
        assert packed[64:72] == b"\x01\x02\x03\x04\x05\x06\x07\x08"

    def test_difficulty_is_big_endian_uint32(self):
        packed = self._make_header(difficulty=0x00000010).pack()
        assert packed[72:76] == b"\x00\x00\x00\x10"

    def test_nonce_is_big_endian_uint64_at_offset_76(self):
        packed = self._make_header(nonce=0x00000000DEADBEEF).pack()
        assert packed[76:84] == b"\x00\x00\x00\x00\xDE\xAD\xBE\xEF"

    ## test the error handling
    def test_unpack_wrong_length_raises(self):
        with pytest.raises(ValueError):
            BlockHeader.unpack(b"\x00" * 83)

    def test_invalid_prev_hash_length_raises(self):
        with pytest.raises(ValueError):
            BlockHeader(prev_hash=b"\x00" * 31,
                        txs_hash=ZERO_HASH,
                        timestamp=0,
                        difficulty=0,
                        nonce=0)

    def test_copy_with_new_nonce_only_changes_nonce(self):
        h = self._make_header(nonce=0)
        h2 = h.copy_with_new_nonce(4444)
        assert h2.nonce == 4444
        assert h2.prev_hash == h.prev_hash
        assert h2.txs_hash == h.txs_hash
        assert h2.timestamp == h.timestamp
        assert h2.difficulty == h.difficulty


# block_hash = SHA256(84-byte header)
class TestBlockHash:
    def test_matches_manual_sha256(self):
        h = BlockHeader(
            prev_hash=ZERO_HASH,
            txs_hash=ZERO_HASH,
            timestamp=0,
            difficulty=0,
            nonce=0,
        )
        expected = hashlib.sha256(h.pack()).digest()
        assert hash_block_header(h) == expected

    def test_different_nonce_gives_different_hash(self):
        base = BlockHeader(ZERO_HASH, ZERO_HASH, 0, 0, 0)
        assert hash_block_header(base.copy_with_new_nonce(0)) != hash_block_header(base.copy_with_new_nonce(1))

    def test_returns_32_bytes(self):
        h = BlockHeader(ZERO_HASH, ZERO_HASH, 0, 0, 0)
        assert len(hash_block_header(h)) == 32


# tx_hash = SHA256(sender_key || data || timestamp_8byte_be || signature)
class TestTxHash:

    ## setup a default transaction for tests
    def _make_tx(self, **overrides) -> Transaction:
        defaults = dict(
            sender_key=b"\xAA" * 32,
            data=b"hello",
            timestamp=42,
            signature=b"\xBB" * 64,
        )
        defaults.update(overrides)
        return Transaction(**defaults)

    def test_different_timestamps_give_different_hashes(self):
        tx1 = self._make_tx(timestamp=1)
        tx2 = self._make_tx(timestamp=256)
        assert hash_transaction(tx1) != hash_transaction(tx2)

    def test_returns_32_bytes(self):
        assert len(hash_transaction(self._make_tx())) == 32

    def test_different_data_gives_different_hash(self):
        assert hash_transaction(self._make_tx(data=b"a")) != hash_transaction(self._make_tx(data=b"b"))


# txs_hash = SHA256(tx_hash_1 || ... || tx_hash_n); empty = SHA256(b"")
class TestTxsHash:

    ## tests for the common pitfall in assignment description:
    ## "Forgetting that `txs_hash` for an empty block is `SHA256(b"")`, not 32 zero bytes."
    def test_empty_block_is_sha256_of_empty_bytes(self):
        expected = hashlib.sha256(b"").digest()
        assert hash_txs([]) == expected

    def test_empty_is_not_32_zero_bytes(self):
        assert hash_txs([]) != ZERO_HASH

    def test_single_tx(self):
        h = b"\x01" * 32
        expected = hashlib.sha256(h).digest()
        assert hash_txs([h]) == expected

    def test_order_matters(self):
        h1, h2 = b"\x01" * 32, b"\x02" * 32
        assert hash_txs([h1, h2]) != hash_txs([h2, h1])


# tests for counting leading-zero-bit and PoW check
class TestLeadingZeroBits:
    def test_all_zero_digest(self):
        assert count_leading_zero_bits(b"\x00" * 32) == 256

    def test_first_byte_0x80(self):
        # 0x80 = 10000000 → 0 leading zeros
        assert count_leading_zero_bits(b"\x80" + b"\x00" * 31) == 0

    def test_first_byte_0x00_second_0x80(self):
        assert count_leading_zero_bits(b"\x00\x80" + b"\x00" * 30) == 8

    def test_first_byte_0x0F(self):
        # 0x0F = 00001111 → 4 leading zeros
        assert count_leading_zero_bits(b"\x0F" + b"\x00" * 31) == 4

    def test_first_byte_0x01(self):
        # 0x01 = 00000001 → 7 leading zeros
        assert count_leading_zero_bits(b"\x01" + b"\x00" * 31) == 7

    def test_satisfies_pow_exact(self):
        digest = b"\x00" + b"\xFF" * 31  # exactly 8 leading zero bits
        assert satisfies_pow(digest, 8)
        assert not satisfies_pow(digest, 9)

    def test_satisfies_pow_zero_difficulty(self):
        assert satisfies_pow(b"\xFF" * 32, 0)
