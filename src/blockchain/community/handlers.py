import struct
from ..core.models import Transaction
from ..core.block_utils import hash_transaction
from ipv8.keyvault.crypto import default_eccrypto

from .payloads import SubmitTransactionResponse, ChainHeightResponse, BlockResponse


def on_submit_transaction(community, peer, payload):
    tx, tx_hash, accepted, message = _verify_and_add(community, payload)
    community.ez_send(peer, SubmitTransactionResponse(
        success=accepted,
        tx_hash=tx_hash,
        message=message,
    ))
    if accepted:
        community.broadcast_new_transaction(tx, exclude_peer=peer)


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
        return
    _send_block_response(community, peer, block, payload.height)


# ── helpers ───────────────────────────────────────────────────────────────────

def _verify_and_add(community, payload):
    """Verify the IPv8 signature and add the transaction to the mempool."""
    signed_data = payload.sender_key + payload.data + struct.pack(">q", payload.timestamp)
    try:
        pub_key = default_eccrypto.key_from_public_bin(payload.sender_key)
        if not default_eccrypto.is_valid_signature(pub_key, signed_data, payload.signature):
            return None, b"\x00" * 32, False, "invalid signature"
    except Exception:
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


def _send_block_response(community, peer, block, height):
    community.ez_send(peer, BlockResponse(
        height=height,
        prev_hash=block.header.prev_hash,
        txs_hash=block.header.txs_hash,
        timestamp=block.header.timestamp,
        difficulty=block.header.difficulty,
        nonce=block.header.nonce,
        block_hash=block.block_hash,
        tx_hashes=b"".join(block.tx_hashes),
    ))


# re-exported for sync.py
validate_and_add_transaction = _verify_and_add
