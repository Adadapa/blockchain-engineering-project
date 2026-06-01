"""
peer-to-peer block sync logic.
"""
import hashlib
from .payloads import AnnounceBlock, RequestBlock, BlockResponse
from .handlers import on_get_block
from ..models import Block, BlockHeader


def broadcast_new_block(community, block):
    announcement = AnnounceBlock(
        height=community.chain.height,
        block_hash=block.block_hash,
    )
    for peer in community.get_peers():
        community.ez_send(peer, announcement)


# When a new block is mined by peer, if the block is ahead of us we need to request all
# missing blocks before switching forks
def on_announce_block(community, peer, payload):
    # our block is not behind
    if payload.height <= community.chain.height:
        return

    for height in range(community.chain.height + 1, payload.height + 1):
        community.ez_send(peer, RequestBlock(height=height))


def on_request_block(community, peer, payload):
    on_get_block(community, peer, payload)


def on_block_response(community, peer, payload):
    block = _deserialize_block(payload)
    if block is not None:
        community.chain.add_block(block)


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
