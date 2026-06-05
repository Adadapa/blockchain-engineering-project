"""
peer-to-peer block sync logic.
"""
import hashlib
from .payloads import AnnounceBlock, RequestBlock, BlockResponse,RequestBlockByHash, AnnounceTransaction
from .handlers import on_get_block, validate_and_add_transaction
from ..models import Block, BlockHeader


def broadcast_new_block(community, block):
    announcement = AnnounceBlock(
        height=community.chain.height,
        block_hash=block.block_hash,
    )
    for peer in community.get_peers():
        community.ez_send(peer, announcement)

def broadcast_new_transaction(community, tx, exclude_peer=None):
    payload = AnnounceTransaction(
        sender_key=tx.sender_key,
        data=tx.data,
        timestamp=tx.timestamp,
        signature=tx.signature,
    )

    excluded_key = None if exclude_peer is None else exclude_peer.public_key.key_to_bin()

    for peer in community.get_peers():
        if excluded_key is not None and peer.public_key.key_to_bin() == excluded_key:
            continue
        community.ez_send(peer, payload)

# When a new block is mined by peer, if the block is ahead of us we need to request all
# missing blocks before switching forks
def on_announce_block(community, peer, payload):
    # our block is not behind
    if payload.height < community.chain.height:
        return

    if payload.height == community.chain.height and payload.block_hash == community.chain.tip.block_hash:
        return

    community.ez_send(peer, RequestBlockByHash(block_hash=payload.block_hash))
    # for height in range(community.chain.height + 1, payload.height + 1):
    #     community.ez_send(peer, RequestBlock(height=height))

# this is when we received a broadcasted transaction
def on_announce_transaction(community, peer, payload):
    tx, tx_hash, accepted, message = validate_and_add_transaction(community, payload)

    if not accepted: # this is triggered if we have seen this transaction before, stop broadcasting
        return

    community.broadcast_new_transaction(tx, exclude_peer=peer)

def on_request_block(community, peer, payload):
    on_get_block(community, peer, payload)

def on_request_block_by_hash(community, peer, payload):
    block = community.chain.get_block_by_hash(payload.block_hash)
    if block is None:
        return
    height = getattr(community.chain, "_hash_to_height", {}).get(block.block_hash)
    if height is None:
        height = -1
    tx_hashes = b"".join(block.tx_hashes)
    community.ez_send(peer, BlockResponse(
        height=height,
        prev_hash=block.header.prev_hash,
        txs_hash=block.header.txs_hash,
        timestamp=block.header.timestamp,
        difficulty=block.header.difficulty,
        nonce=block.header.nonce,
        block_hash=block.block_hash,
        tx_hashes=tx_hashes,
    ))

def on_block_response(community, peer, payload):
    try:
        block = _deserialize_block(payload)
        if block is None:
            return

        community.chain.add_block(block)

        parent = block.header.prev_hash
        if community.chain.get_block_by_hash(parent) is None and parent not in getattr(community.chain, "_hash_to_height",
                                                                                       {}):
            community.ez_send(peer, RequestBlockByHash(block_hash=parent))
    except Exception as exc:
        print(f"Invalid block from {peer}: {exc}")


def _deserialize_block(payload: BlockResponse):
    raw_hashes = payload.tx_hashes
    if len(raw_hashes) % 32 != 0:
        return None

    tx_hashes = tuple(raw_hashes[i:i + 32] for i in range(0, len(raw_hashes), 32))

    header = BlockHeader(
        prev_hash=payload.prev_hash,
        txs_hash=payload.txs_hash,
        timestamp=payload.timestamp,
        difficulty=payload.difficulty,
        nonce=payload.nonce,
    )
    block_hash = hashlib.sha256(header.pack()).digest()
    return Block(header=header, block_hash=block_hash, tx_hashes=tx_hashes)
