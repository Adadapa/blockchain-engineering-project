from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from typing import Any

from ipv8.peer import Peer
from ipv8_service import IPv8

from lab_group_client.community import LabGroupSigningCommunity
from lab_group_client.config import LabClientConfig, ipv8_configuration


@dataclass(frozen=True)
class PreparedPeer:
    address: tuple[str, int]
    mid_hex: str
    public_key_hex: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover the Lab 2 server and group members before starting timed tasks."
    )
    parser.add_argument(
        "--config",
        default="config/lab_client.example.json",
        help="Path to the lab client JSON config.",
    )
    parser.add_argument(
        "--cache",
        default=None,
        help="Optional session cache path. Defaults to session_cache_file from config.",
    )
    return parser.parse_args()


def describe_peer(peer: Peer) -> str:
    return (
        f"address={peer.address} "
        f"mid={peer.mid.hex()} "
        f"public_key={peer.public_key.key_to_bin().hex()}"
    )


def peer_to_prepared(peer: Peer) -> PreparedPeer:
    host, port = peer.address
    return PreparedPeer(
        address=(host, port),
        mid_hex=peer.mid.hex(),
        public_key_hex=peer.public_key.key_to_bin().hex(),
    )


def member_label(config: LabClientConfig, public_key: bytes) -> str:
    return f"member{config.member_public_keys.index(public_key) + 1}"


async def wait_for_ready_topology(
    community: LabGroupSigningCommunity,
    config: LabClientConfig,
) -> tuple[Peer, dict[bytes, Peer]]:
    local_public_key = community.my_peer.public_key.key_to_bin()
    if local_public_key not in config.member_public_keys:
        raise ValueError(
            "local private key does not match any configured member_public_keys entry; "
            f"local public key is {local_public_key.hex()}"
        )

    print(f"Using identity file: {config.private_key_file}")
    print(f"Joined community: {config.community_id.hex()}")
    print(f"Expecting server public key: {config.server_public_key.hex()}")
    print("Discovering server and group members...")

    deadline = asyncio.get_running_loop().time() + config.discovery_timeout
    seen_peer_keys: set[bytes] = set()
    server_peer: Peer | None = None
    member_peers: dict[bytes, Peer] = {}

    while True:
        server_peer = community.find_server_peer(config.server_public_key) or server_peer
        member_peers = community.find_member_peers(config.member_public_keys)

        for peer in community.get_discovered_peers():
            public_key = peer.public_key.key_to_bin()
            if public_key in seen_peer_keys:
                continue
            seen_peer_keys.add(public_key)

            if public_key == config.server_public_key:
                print(f"Matched server: {describe_peer(peer)}")
            elif public_key in config.member_public_keys:
                print(f"Matched {member_label(config, public_key)}: {describe_peer(peer)}")
            else:
                print(f"Discovered non-group peer: {describe_peer(peer)}")

        if server_peer is not None and len(member_peers) >= 2:
            return server_peer, member_peers

        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(
                "timed out preparing session; "
                f"server_found={server_peer is not None}, member_peers_found={len(member_peers)}/2"
            )

        print(
            "Still preparing: "
            f"server_found={server_peer is not None}, member_peers_found={len(member_peers)}/2"
        )
        await asyncio.sleep(config.discovery_poll_interval)


def build_cache(
    config: LabClientConfig,
    community: LabGroupSigningCommunity,
    server_peer: Peer,
    member_peers: dict[bytes, Peer],
) -> dict[str, Any]:
    local_public_key = community.my_peer.public_key.key_to_bin()
    return {
        "created_at": time.time(),
        "community_id": config.community_id.hex(),
        "local_public_key": local_public_key.hex(),
        "server": peer_to_prepared(server_peer).__dict__,
        "members": {
            public_key.hex(): peer_to_prepared(peer).__dict__
            for public_key, peer in member_peers.items()
        },
        "registration_order": [public_key.hex() for public_key in config.member_public_keys],
    }


async def prepare_session(config: LabClientConfig, cache_path_override: str | None) -> int:
    cache_path = config.session_cache_file
    if cache_path_override is not None:
        override = config.session_cache_file.parent / cache_path_override
        cache_path = override.resolve() if override.is_absolute() else override
    ipv8 = IPv8(
        ipv8_configuration(config),
        extra_communities={"LabGroupSigningCommunity": LabGroupSigningCommunity},
    )
    await ipv8.start()
    try:
        community = ipv8.get_overlay(LabGroupSigningCommunity)
        if community is None or not isinstance(community, LabGroupSigningCommunity):
            raise RuntimeError("failed to load LabGroupSigningCommunity overlay")

        server_peer, member_peers = await wait_for_ready_topology(community, config)
        cache = build_cache(config, community, server_peer, member_peers)

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Session prepared and written to {cache_path}")
        return 0
    finally:
        await ipv8.stop()


def main() -> int:
    args = parse_args()
    try:
        config = LabClientConfig.from_file(args.config)
        return asyncio.run(prepare_session(config, args.cache))
    except Exception as exc:
        print(f"session preparation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
