from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
import asyncio

from .payloads import (
    Ready,
    SubmitTransaction, GetChainHeight, GetBlock,
    AnnounceBlock, RequestBlock, RequestBlockByHash, BlockResponse, AnnounceTransaction,
)
from . import handlers, sync
from blockchain.config import (BLOCKCHAIN_COMMUNITY_ID)


class BlockchainCommunity(Community):
    community_id = BLOCKCHAIN_COMMUNITY_ID

    def __init__(self, settings):
        super().__init__(settings)
        self.chain = None
        self.mempool = None
        self.ready_peers: set[bytes] = set()

        self.add_message_handler(Ready, self._on_ready)

        self.add_message_handler(SubmitTransaction, self._on_submit_transaction)
        self.add_message_handler(GetChainHeight, self._on_get_chain_height)
        self.add_message_handler(GetBlock, self._on_get_block)

        self.add_message_handler(AnnounceBlock, self._on_announce_block)
        self.add_message_handler(RequestBlock, self._on_request_block)
        self.add_message_handler(RequestBlockByHash, self._on_request_block_by_hash)
        self.add_message_handler(BlockResponse, self._on_block_response)
        self.add_message_handler(AnnounceTransaction, self._on_announce_transaction)

    def broadcast_new_block(self, block):
        sync.broadcast_new_block(self, block)

    def broadcast_new_transaction(self, tx, exclude_peer=None):
        sync.broadcast_new_transaction(self, tx, exclude_peer=exclude_peer)

    def send_ready(self, peer, group_id):
        self.ez_send(peer, Ready(group_id))

    @lazy_wrapper(Ready)
    def _on_ready(self, peer, payload):
        self.ready_peers.add(peer.public_key.key_to_bin())

    @lazy_wrapper(SubmitTransaction)
    def _on_submit_transaction(self, peer, payload):
        handlers.on_submit_transaction(self, peer, payload)

    @lazy_wrapper(GetChainHeight)
    def _on_get_chain_height(self, peer, payload):
        handlers.on_get_chain_height(self, peer, payload)

    @lazy_wrapper(GetBlock)
    def _on_get_block(self, peer, payload):
        handlers.on_get_block(self, peer, payload)

    @lazy_wrapper(AnnounceBlock)
    def _on_announce_block(self, peer, payload):
        sync.on_announce_block(self, peer, payload)

    @lazy_wrapper(RequestBlock)
    def _on_request_block(self, peer, payload):
        sync.on_request_block(self, peer, payload)

    @lazy_wrapper(RequestBlockByHash)
    def _on_request_block_by_hash(self, peer, payload):
        sync.on_request_block_by_hash(self, peer, payload)

    @lazy_wrapper(BlockResponse)
    def _on_block_response(self, peer, payload):
        sync.on_block_response(self, peer, payload)

    @lazy_wrapper(AnnounceTransaction)
    def _on_announce_transaction(self, peer, payload):
        sync.on_announce_transaction(self, peer, payload)

async def wait_until_group_ready(community, group_id, member_public_keys):
    while True:
        peers = [
            p for p in community.get_peers()
            if p.public_key.key_to_bin() in member_public_keys
        ]
        for peer in peers:
            community.walk_to(peer.address)
            community.send_ready(peer, group_id)

        print(f"teammates found: {len(peers)}/2  ready: {len(community.ready_peers)}/2")

        if len(community.ready_peers) >= 2:
            return peers

        await asyncio.sleep(1)
