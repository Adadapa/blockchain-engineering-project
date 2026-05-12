from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.payload_dataclass import dataclass as payload_dataclass
from ipv8.peer import Peer


@payload_dataclass(msg_id=1)
class RegisterPayload:
    # Wire format: three varlenH byte fields, in the canonical order used later for signatures.
    member1_key: bytes
    member2_key: bytes
    member3_key: bytes


@payload_dataclass(msg_id=2)
class RegisterResponsePayload:
    # Wire format: bool, varlenHutf8 group_id, varlenHutf8 status message.
    success: bool
    group_id: str
    message: str


@dataclass(frozen=True)
class RegistrationResult:
    success: bool
    group_id: str
    message: str


class LabGroupSigningCommunity(Community):
    community_id = b"Lab2GroupSigning2026"

    def __init__(self, settings) -> None:
        # IPv8 constructs settings first and then copies "initialize" config fields onto it.
        self.community_id = settings.community_id
        super().__init__(settings)
        self.add_message_handler(RegisterResponsePayload, self.on_register_response)
        self._registration_response: asyncio.Future[RegistrationResult] | None = None
        self._expected_server_public_key: bytes | None = None

    async def register_group(
        self,
        server_peer: Peer,
        member_public_keys: tuple[bytes, bytes, bytes],
        timeout: float,
    ) -> RegistrationResult:
        # Store the pending response future before sending, so a fast server reply cannot be missed.
        self._registration_response = asyncio.get_running_loop().create_future()
        self._expected_server_public_key = server_peer.public_key.key_to_bin()

        # The discovered Peer already carries both the verified server key and its current UDP address.
        self.ez_send(server_peer, RegisterPayload(*member_public_keys))

        try:
            return await asyncio.wait_for(self._registration_response, timeout=timeout)
        except TimeoutError as exc:
            raise TimeoutError(f"Timed out waiting for registration response after {timeout:.2f} seconds") from exc
        finally:
            self._registration_response = None
            self._expected_server_public_key = None

    def find_server_peer(self, server_public_key: bytes) -> Peer | None:
        for peer in self.get_peers():
            if peer.public_key.key_to_bin() == server_public_key:
                return peer
        return None

    def get_discovered_peers(self) -> list[Peer]:
        return self.get_peers()

    @lazy_wrapper(RegisterResponsePayload)
    def on_register_response(self, peer: Peer, payload: RegisterResponsePayload) -> None:
        # lazy_wrapper already verifies the packet signature; this check ensures it was the server's key.
        if peer.public_key.key_to_bin() != self._expected_server_public_key:
            return
        if self._registration_response and not self._registration_response.done():
            self._registration_response.set_result(
                RegistrationResult(
                    success=payload.success,
                    group_id=payload.group_id,
                    message=payload.message,
                )
            )
