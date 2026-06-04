from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from .payloads import Ready
import asyncio

from .payloads import (
    SubmitTransaction,
    GetChainHeight,
    GetBlock,
    AnnounceBlock,
    RequestBlock,
    BlockResponse,
    RequestBlockByHash
)
from . import handlers, sync


class BlockchainCommunity(Community):
    community_id = bytes.fromhex("4c61623247726f75705369676e696e6732303236") #20 bytes

    def __init__(self, settings):
        super().__init__(settings)
        self.chain = None
        self.mempool = None

        # initial peer-discovery
        self.ready_peers = set()
        self.add_message_handler(Ready, self._on_ready)

        # server-facing
        self.add_message_handler(SubmitTransaction, self._on_submit_transaction)
        self.add_message_handler(GetChainHeight, self._on_get_chain_height)
        self.add_message_handler(GetBlock, self._on_get_block)

        # peer sync
        self.add_message_handler(AnnounceBlock, self._on_announce_block)
        self.add_message_handler(RequestBlock, self._on_request_block)
        self.add_message_handler(RequestBlockByHash, self._on_request_block_by_hash)
        self.add_message_handler(BlockResponse, self._on_block_response)

    # server communication

    @lazy_wrapper(SubmitTransaction)
    def _on_submit_transaction(self, peer, payload):
        handlers.on_submit_transaction(self, peer, payload)

    @lazy_wrapper(GetChainHeight)
    def _on_get_chain_height(self, peer, payload):
        handlers.on_get_chain_height(self, peer, payload)

    @lazy_wrapper(GetBlock)
    def _on_get_block(self, peer, payload):
        handlers.on_get_block(self, peer, payload)

    # peer sync

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

    # called by your miner

    def broadcast_new_block(self, block):
        sync.broadcast_new_block(self, block)

    # for initial peer discovery
    @lazy_wrapper(Ready)
    def _on_ready(self, peer, payload):
        self.ready_peers.add(peer.public_key.key_to_bin())

    def send_ready(self, peer, group_id):
        self.ez_send(peer, Ready(group_id))


async def wait_until_group_ready(community, group_id, member_public_keys):
    ready_sent_to: set[bytes] = set()  # track per-peer, not a single bool

    while True:
        known_peers = {
            peer.public_key.key_to_bin(): peer
            for peer in community.get_peers()
            if peer.public_key.key_to_bin() in member_public_keys
        }

        # Always walk to and ping every known group peer, every tick
        for key, peer in known_peers.items():
            community.walk_to(peer.address)

            # Send Ready to any group peer we haven't sent to yet,
            # OR re-send if we still haven't heard back from them
            if key not in community.ready_peers:
                community.send_ready(peer, group_id)
                ready_sent_to.add(key)

        found = len(known_peers)
        ready = len(community.ready_peers)

        if found >= 2 and ready >= 2:
            print("ready received from both teammates")
            return list(known_peers.values())

        print(f"found {found}/2 teammates, ready from {ready}/2")
        await asyncio.sleep(1)

# # before registration, called to first make sure every group memebr discovered everyone
# async def wait_until_group_ready(community, group_id, member_public_keys):
#     ready_sent = False
#
#     while True:
#         known_peers = [
#             peer
#             for peer in community.get_peers()
#             if peer.public_key.key_to_bin() in member_public_keys
#         ]
#
#         for peer in known_peers:
#             community.walk_to(peer.address) # establish stronger connection
#
#         if len(known_peers) >= 2 and not ready_sent:
#             print("discovered both teammates; sending ready")
#             for peer in known_peers:
#                 community.send_ready(peer, group_id)
#             ready_sent = True
#
#         if ready_sent:
#
#             if  len(community.ready_peers) == 2:
#                 print("ready received from both teammates")
#                 return known_peers
#
#             for peer in known_peers: # keep sending ready until you get a response from everyone
#                 community.send_ready(peer, group_id)
#
#             print(f"ready from {len(community.ready_peers)}/2 teammates")
#         else:
#             print(f"found {len(known_peers)}/2 teammates")
#
#         await asyncio.sleep(1)


