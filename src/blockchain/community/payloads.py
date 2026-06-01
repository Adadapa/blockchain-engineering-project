from dataclasses import dataclass
from ipv8.messaging.payload_dataclass import dataclass as payload_dataclass


@payload_dataclass(msg_id=1)
class SubmitTransaction:
    sender_key: bytes
    data: bytes
    timestamp: int
    signature: bytes

@payload_dataclass(msg_id=2)
class SubmitTransactionResponse:
    success: bool
    tx_hash: bytes
    message: str

@payload_dataclass(msg_id=3)
class GetChainHeight:
    request_id: int

@payload_dataclass(msg_id=4)
class ChainHeightResponse:
    request_id: int
    height: int
    tip_hash: bytes

@payload_dataclass(msg_id=5)
class GetBlock:
    height: int

@payload_dataclass(msg_id=6)
class BlockResponse:
    height: int
    prev_hash: bytes
    txs_hash: bytes
    timestamp: int
    difficulty: int
    nonce: int
    block_hash: bytes
    tx_hashes: bytes

# peer-to-peer sync messages
@payload_dataclass(msg_id=7)
class AnnounceBlock:
    height: int
    block_hash: bytes

@payload_dataclass(msg_id=8)
class RequestBlock:
    height: int