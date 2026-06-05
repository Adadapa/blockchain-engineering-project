
import hashlib
import struct
from ..models import Transaction
from ..block_utils import hash_transaction
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .payloads import (
    SubmitTransactionResponse,
    ChainHeightResponse,
    BlockResponse,
)

# Verify the transaction signature, add to mempool, and respond.
# Signature covers: sender_key || data || timestamp (8-byte big-endian)
def validate_and_add_transaction(community, payload):
    signed_data = payload.sender_key + payload.data + struct.pack(">q", payload.timestamp)

    try:
        pub_key = Ed25519PublicKey.from_public_bytes(payload.sender_key)
        pub_key.verify(payload.signature, signed_data)
    except (InvalidSignature, ValueError):
        return None, b"\x00" * 32, False, "invalid signature"

    tx = Transaction(
        sender_key=payload.sender_key,
        data=payload.data,
        timestamp=payload.timestamp,
        signature=payload.signature,
    )
    tx_hash = hash_transaction(tx)
    accepted = community.mempool.add(tx)

    return tx, tx_hash, accepted, "accepted" if accepted else "duplicate"

def on_submit_transaction(community, peer, payload):
    tx, tx_hash, accepted, message = validate_and_add_transaction(community, payload)

    community.ez_send(peer, SubmitTransactionResponse(
        success=accepted,
        tx_hash=tx_hash,
        message=message,
    ))

    if accepted:
        community.broadcast_transaction(tx, exclude_peer=peer)

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



