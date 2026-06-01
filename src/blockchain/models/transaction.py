from dataclasses import dataclass

@dataclass(frozen=True)
class Transaction:
    sender_key: bytes # IPv8 public key
    data: bytes
    timestamp: int # unix timestamp
    signature: bytes
