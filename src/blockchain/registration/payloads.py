from dataclasses import dataclass
from ipv8.messaging.payload_dataclass import dataclass as payload_dataclass

@payload_dataclass(msg_id=1)
class RegisterBlockchain:
    group_id: str
    community_id: bytes

@payload_dataclass(msg_id=2)
class RegisterBlockchainResponse:
    success: bool
    message: str