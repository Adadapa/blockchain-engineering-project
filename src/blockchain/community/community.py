from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper

from .payloads import (
    SubmitTransaction,
    GetChainHeight,
    GetBlock,
    AnnounceBlock,
    RequestBlock,
    BlockResponse,
)
from . import handlers, sync


class BlockchainCommunity(Community):
    # Must match the community_id you register with the server (20 bytes).
    community_id = b'your-20-byte-id!!'  # replace with your actual ID

    def __init__(self, settings, chain, mempool):
        super().__init__(settings)
        self.chain = chain
        self.mempool = mempool

        # server-facing
        self.add_message_handler(SubmitTransaction, self._on_submit_transaction)
        self.add_message_handler(GetChainHeight, self._on_get_chain_height)
        self.add_message_handler(GetBlock, self._on_get_block)

        # peer sync
        self.add_message_handler(AnnounceBlock, self._on_announce_block)
        self.add_message_handler(RequestBlock, self._on_request_block)
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

        @lazy_wrapper(BlockResponse)
        def _on_block_response(self, peer, payload):
            sync.on_block_response(self, peer, payload)

        # called by your miner

        def broadcast_new_block(self, block):
            sync.broadcast_new_block(self, block)