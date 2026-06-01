from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.peer import Peer

from .payloads import RegisterBlockchain, RegisterBlockchainResponse


class RegistrationCommunity(Community):
    community_id = b"<registration-id-20b>"

    def __init__(self, settings):
        super().__init__(settings)
        self.add_message_handler(RegisterBlockchainResponse, self._on_register_response)
        self.response = None

    def register_blockchain(self, server_peer: Peer, group_id: str, community_id: bytes):
        self.ez_send(server_peer, RegisterBlockchain(group_id, community_id))

    @lazy_wrapper(RegisterBlockchainResponse)
    def _on_register_response(self, peer, payload):
        self.response = payload
        print(f"success={payload.success}")
        print(f"message={payload.message}")