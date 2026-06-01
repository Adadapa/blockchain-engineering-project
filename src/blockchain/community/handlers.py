
import hashlib
import struct

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .payloads import (
    SubmitTransactionResponse,
    ChainHeightResponse,
    BlockResponse,
)

# Verify the transaction signature, add to mempool, and respond.
# Signature covers: sender_key || data || timestamp (8-byte big-endian)
def on_submit_transaction(community, peer, payload):
    signed_data = (payload.sender_key + payload.data + struct.pack(">q", payload.timestamp))

    try:
        pub_key = Ed25519PublicKey.from_public_bytes(payload.sender_key)
        pub_key.verify(payload.signature, signed_data)
    except (InvalidSignature, ValueError):
        community.ez_send(peer, SubmitTransactionResponse(
            success=False,
            tx_hash=b"\x00" * 32,
            message="invalid signature",
        ))
        return

    tx_hash = _compute_tx_hash(payload)
    accepted = community.mempool.add(payload)

    community.ez_send(peer, SubmitTransactionResponse(
        success=accepted,
        tx_hash=tx_hash,
        message="accepted" if accepted else "duplicate",
    ))


def on_get_chain_height(community, peer, payload):
    community.ez_send(peer, ChainHeightResponse(
        request_id=payload.request_id,
        height=community.chain.height,
        tip_hash=community.chain.tip.block_hash,
    ))


def on_get_block(community, peer, payload):
    try:
        block = community.chain.block_at(payload.height)
    except IndexError:
        return  # ignore requests for heights we don't have

    tx_hashes = b"".join(block.tx_hashes)

    community.ez_send(peer, BlockResponse(
        height=payload.height,
        prev_hash=block.header.prev_hash,
        txs_hash=block.header.txs_hash,
        timestamp=block.header.timestamp,
        difficulty=block.header.difficulty,
        nonce=block.header.nonce,
        block_hash=block.block_hash,
        tx_hashes=tx_hashes,
    ))


# ── helpers ───────────────────────────────────────────────────────────────

def _compute_tx_hash(payload) -> bytes:
    return hashlib.sha256(
        payload.sender_key
        + payload.data
        + struct.pack(">q", payload.timestamp)
        + payload.signature
    ).digest()