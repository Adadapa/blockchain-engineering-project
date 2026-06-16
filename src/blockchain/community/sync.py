from .payloads import AnnounceBlock, BlockResponse, RequestBlockByHash, AnnounceTransaction
from .handlers import _verify_and_add, _send_block_response
from blockchain.models import Block, BlockHeader
from ..core.block_utils import hash_block_header


def broadcast_new_block(community, block):
    announcement = AnnounceBlock(
        height=community.chain.height,
        block_hash=block.block_hash,
    )
    print("broadcasting new block", announcement.block_hash)
    for peer in community.get_peers():
        community.ez_send(peer, announcement)


def broadcast_new_transaction(community, tx, exclude_peer=None):
    payload = AnnounceTransaction(
        sender_key=tx.sender_key,
        data=tx.data,
        timestamp=tx.timestamp,
        signature=tx.signature,
    )
    excluded = None if exclude_peer is None else exclude_peer.public_key.key_to_bin()
    for peer in community.get_peers():
        if peer.public_key.key_to_bin() != excluded:
            community.ez_send(peer, payload)


def on_announce_block(community, peer, payload):
    already_have_it = (
        payload.height < community.chain.height or
        (payload.height == community.chain.height and payload.block_hash == community.chain.tip.block_hash)
    )
    if not already_have_it:
        community.ez_send(peer, RequestBlockByHash(block_hash=payload.block_hash))


def on_request_block_by_hash(community, peer, payload):
    block = community.chain.get_block_by_hash(payload.block_hash)
    if block is None:
        return
    height = community.chain._hash_to_height.get(block.block_hash, -1)
    _send_block_response(community, peer, block, height)


def on_block_response(community, peer, payload):
    try:
        block = _deserialize_block(payload)
        if block is None:
            return
        print(f"Received {block.block_hash.hex()[:16]} from {peer}")
        community.chain.add_block(block)
        if not community.chain.contains(block.header.prev_hash):
            community.ez_send(peer, RequestBlockByHash(block_hash=block.header.prev_hash))
    except Exception as exc:
        print(f"Invalid block from {peer}: {exc}")


def on_announce_transaction(community, peer, payload):
    tx, tx_hash, accepted, _ = _verify_and_add(community, payload)
    if accepted:
        community.broadcast_new_transaction(tx, exclude_peer=peer)

# helper

def _deserialize_block(payload: BlockResponse) -> Block | None:
    if len(payload.tx_hashes) % 32 != 0:
        return None
    tx_hashes = tuple(
        payload.tx_hashes[i:i + 32] for i in range(0, len(payload.tx_hashes), 32)
    )
    header = BlockHeader(
        prev_hash=payload.prev_hash,
        txs_hash=payload.txs_hash,
        timestamp=payload.timestamp,
        difficulty=payload.difficulty,
        nonce=payload.nonce,
    )
    return Block(header=header, block_hash=hash_block_header(header), tx_hashes=tx_hashes)
