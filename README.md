# Blockchain Engineering Project

---

## Getting started

**Requirements**

- Python 3.10+
- [py-ipv8](https://github.com/Tribler/py-ipv8)
- [pytest](https://docs.pytest.org/)

`requirements.txt` contains the full dependency tree.

**Install**

```
python3 -m pip install -e .
```

or, to match the exact pinned versions:

```
python3 -m pip install -r requirements.txt
```

**Keys**

Each lab member has a private key from lab 1. 
Keys live in `keys/`. The key type is `curve25519`, loaded by IPv8.

**Run a node**

```
python src/blockchain/scripts/node.py
```

The node will:
- Start an IPv8 instance on port 8092
- Discover the two teammate nodes using IPv8 peer discovery
- Register with the lab server using `BLOCKCHAIN_COMMUNITY_ID`
- Start mining once registration succeeds

Config values (ports, difficulty, group id, public keys) live in [`src/blockchain/config.py`](src/blockchain/config.py).

**Run the tests**

```
python -m pytest tests/
```

---

## Project structure

`src/blockchain/config.py`: ports, keys, difficulty, and community ids.

**models**

| file | description |
|---|---|
| `models/block_header.py` | `BlockHeader` dataclass + binary pack/unpack |
| `models/block.py` | `Block` dataclass (header + hash + tx hashes) |
| `models/transaction.py` | `Transaction` dataclass |
| `models/genesis.py` | hardcoded genesis block |
| `models/mempool.py` | pending transaction pool |
| `models/mempool_sync.py` | keeps the mempool in sync with chain state |
| `models/orphan_pool.py` | holds blocks whose parent isn't known yet |

**core**

| file | description |
|---|---|
| `core/block_utils.py` | hashing, PoW check, block validation |
| `core/chain.py` | canonical chain + fork switching logic |
| `core/fork_manager.py` | fork detection and rollback |
| `core/miner.py` | PoW search + async mining loop |

**community**

| file | description |
|---|---|
| `community/payloads.py` | IPv8 message definitions |
| `community/community.py` | `BlockchainCommunity`: message routing |
| `community/handlers.py` | submit transaction, get block by height |
| `community/sync.py` | block and transaction gossip |

**registration**

| file | description |
|---|---|
| `registration/payloads.py` | registration message definitions |
| `registration/registration.py` | `RegistrationCommunity`: lab server handshake |

**scripts**

| file | description |
|---|---|
| `scripts/node.py` | entry point: starts IPv8, discovers peers, mines |
| `scripts/demo.py` | demo script |
| `scripts/mine_genesis.py` | one-off script used to produce the genesis block |

**tests**

| file | description |
|---|---|
| `tests/test_block_primitives.py` | hashing and PoW primitives |
| `tests/test_chain.py` | chain init and fork switching |
| `tests/test_chain_block_addition.py` | adding blocks to the chain |
| `tests/test_chain_consensus_forks.py` | fork resolution and longest chain rule |
| `tests/test_chain_orphans.py` | orphan block handling |
| `tests/test_miner.py` | miner output |

---

## Implementation details

### Transactions and the mempool

A `Transaction` is `sender_key + data + timestamp + signature`. The sender signs `sender_key + data + timestamp` with their curve25519 private key, and the node verifies it using the `sender_key` field included in the transaction.

There are **two** ways a transaction enters a node:

- `SubmitTransaction`: sent by the lab server to submit a new transaction into the network. The node verifies the signature, adds it to the mempool, and sends back a `SubmitTransactionResponse` confirming whether it was accepted.
- `AnnounceTransaction`: used between nodes to gossip a transaction that's already in the network. No response is sent, the node just adds it to the mempool and forwards it to its own peers.

The **mempool** holds all unconfirmed transactions waiting to be included in a block. The miner pulls from it when building a new block.

---

### Genesis block

All nodes start from the same hardcoded genesis block defined in `models/genesis.py`. It was mined once using `scripts/mine_genesis.py`, and the resulting nonce is hardcoded. 
Its `prev_hash` is 32 zero bytes and it contains no transactions.
Every node loads it on startup so they all share the same chain from height 0.

---

### Block flow

**Mining**

- The miner takes the current chain tip (the most recent block) and pending transactions from the mempool
- It builds a `BlockHeader` with `prev_hash = tip.block_hash` and `txs_hash = SHA-256(all tx hashes concatenated)`
- It searches for a nonce such that `SHA-256(header)` has at least `difficulty` leading zero bits
- Once found, the block is added to the local chain and `AnnounceBlock` (height + hash) is broadcast to all peers

**Propagation**

When a block is mined, we don't broadcast the full block to all peers immediately. 
Some peers might already have it (mined the same block, or received it from another peer), 
so sending the full block to everyone unconditionally wastes bandwidth. Instead:

- The miner broadcasts `AnnounceBlock` (just height + hash) to all peers
- A peer skips the announcement if the announced height is strictly below its own chain height (it's already longer, so a shorter block can't help regardless of its hash), or if height and hash both match its current tip. 
- Otherwise it replies with `RequestBlockByHash`.
- The node responds with a full `BlockResponse` containing all header fields and tx hashes
- If the receiving peer doesn't recognize the block's `prev_hash`, it immediately sends another `RequestBlockByHash` for the parent, 
walking backwards until the gap is filled.

**Adding a block**

When `chain.add_block` is called:
- Skip if already known (checked against both chain and orphan pool)
- Validate: recompute the block hash, check PoW, recompute `txs_hash`
- If the parent is unknown, put the block in the orphan pool and request the parent from the peer that sent it
- If the parent is known, add the block to the chain
- Check if any orphans were waiting on this block and recursively add them

When a block is added to the canonical chain, its transactions are removed from the mempool.

**Orphan pool**

Blocks arrive out of order over the network. A block whose parent hasn't arrived yet can't be added to the chain, but dropping it would mean losing it permanently. Instead, orphans are stored keyed by `prev_hash`, and the node immediately requests the missing parent. When the parent arrives and is added to the chain, `_reconnect_orphans` checks if any orphans were waiting on it and adds them too.

---

### Fork handling and consensus

**Fork switching**

Every valid block is stored in `_hash_to_block` regardless of whether it's on the canonical chain.

- If the parent is unknown, the block goes to the orphan pool and the parent is requested
- The orphans reconnect recursively once the missing parents arrive, assembling the full fork in `_hash_to_block`
- `ForkManager.build_fork_from` walks backwards from the fork tip through `_hash_to_block` until it hits a block in the canonical chain (the common ancestor). The collected blocks, reversed, are the fork to apply.
- The new block's height is computed as `_hash_to_height[prev_hash] + 1`
- If it beats the current chain height, the chain switches to the fork. If not, the canonical chain doesn't change.

**Rollback**

Once a fork is confirmed to be longer, the canonical chain is rolled back to the common ancestor before the fork blocks are applied.

- `self.blocks` is truncated to the common ancestor
- `_hash_to_height` is rebuilt from scratch from the remaining blocks
- Each evicted block is passed to `MempoolSync.restore()`, which puts its transactions back in the mempool so they can be re-mined
- `MempoolSync` can do this because it caches every transaction when it's confirmed out of the mempool. Without that cache, those transactions would be permanently lost on a reorg.
- The fork blocks are then appended to the canonical chain one by one


---
## Notes

The `all_assignments` branch contains the code for lab 2 as well.
