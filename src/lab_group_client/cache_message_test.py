from __future__ import annotations

import argparse
import asyncio
import sys
import time

from ipv8_service import IPv8

from lab_group_client.community import LabGroupSigningCommunity
from lab_group_client.config import LabClientConfig, ipv8_configuration
from lab_group_client.run_rounds import load_session_cache, member_number_for_public_key, member_peers_from_cache


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test teammate messaging using the prepared session cache.")
    parser.add_argument(
        "--config",
        default="config/lab_client.example.json",
        help="Path to the lab client JSON config.",
    )
    parser.add_argument(
        "--message",
        default="cache hello",
        help="Group-internal message to send to cached teammates.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=20.0,
        help="How long to keep sending/listening.",
    )
    parser.add_argument(
        "--send-interval",
        type=float,
        default=2.0,
        help="Seconds between repeated sends.",
    )
    return parser.parse_args()


async def cache_message_test(config: LabClientConfig, message: str, duration: float, send_interval: float) -> int:
    cache = load_session_cache(config.session_cache_file)
    member_peers = member_peers_from_cache(config, cache)

    ipv8 = IPv8(
        ipv8_configuration(config),
        extra_communities={"LabGroupSigningCommunity": LabGroupSigningCommunity},
    )
    await ipv8.start()
    try:
        community = ipv8.get_overlay(LabGroupSigningCommunity)
        if community is None or not isinstance(community, LabGroupSigningCommunity):
            raise RuntimeError("failed to load LabGroupSigningCommunity overlay")

        local_public_key = community.my_peer.public_key.key_to_bin()
        local_member_number = member_number_for_public_key(config, local_public_key)
        teammate_peers = {
            public_key: peer
            for public_key, peer in member_peers.items()
            if public_key != local_public_key
        }
        expected_teammate_keys = set(config.member_public_keys) - {local_public_key}
        missing_teammates = expected_teammate_keys - teammate_peers.keys()
        if missing_teammates:
            missing = ", ".join(key.hex() for key in missing_teammates)
            raise ValueError(f"session cache is missing teammate peer(s): {missing}")

        print(f"Local member number from registration order: {local_member_number}")
        print(f"Loaded {len(teammate_peers)} cached teammate peer(s) from {config.session_cache_file}")
        print(f"Sending '{message}' every {send_interval:.2f}s for {duration:.2f}s; keep all clients running.")

        deadline = time.monotonic() + duration
        send_count = 0
        while time.monotonic() < deadline:
            send_count += 1
            for public_key, peer in teammate_peers.items():
                member_number = member_number_for_public_key(config, public_key)
                tagged_message = f"{message} from member{local_member_number} attempt {send_count}"
                print(f"Sending to member{member_number} at {peer.address}: {tagged_message}")
                community.send_group_message(peer, tagged_message)
            await asyncio.sleep(send_interval)

        received_from = {
            group_message.sender_public_key
            for group_message in community.received_group_messages
            if group_message.sender_public_key in expected_teammate_keys
        }
        print(
            "Cache message test finished: "
            f"received_messages={len(community.received_group_messages)}, "
            f"teammates_seen={len(received_from)}/{len(expected_teammate_keys)}"
        )
        return 0 if received_from == expected_teammate_keys else 1
    finally:
        await ipv8.stop()


def main() -> int:
    args = parse_args()
    try:
        config = LabClientConfig.from_file(args.config)
        return asyncio.run(cache_message_test(config, args.message, args.duration, args.send_interval))
    except Exception as exc:
        print(f"cache message test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
