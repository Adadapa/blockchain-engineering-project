# blockchain-engineering-project
For the TUDelft course CS4160

## Requirements

- Python 3.10+
- py-ipv8 library: https://github.com/Tribler/py-ipv8
- py-ipv8 documentation: https://py-ipv8.readthedocs.io/

## Setup

Install the project and Python dependency with:

```bash
python3 -m pip install -e .
```

## Group Registration

Copy `config/lab_client.example.json` to a local config file and fill in:

- `private_key_file` for the member that sends the registration
- `member_public_keys` in the canonical order for later signature bundles

The client discovers the server through IPv8 peer discovery by matching `server_public_key`, so no fixed server host or
port is needed in the config.

### Key Management

Each group member only needs their own private key. Do not share private keys between members.

For registration, the config needs:

- your own private key file in `private_key_file`
- all three group members' public keys in `member_public_keys`

The order of `member_public_keys` is important. It becomes the canonical signature order for later bundle submissions.
All group members should use the same order in their configs.

The server still requires the sender to be one of the listed public keys. That means the private key in
`private_key_file` should match one of the three public keys in `member_public_keys`.

Private keys should be placed under `keys/`. That directory is ignored by Git.

Print the public key hex for an existing member key with:

```bash
lab-key keys/member1_private.pem
```

Put the printed public key into `member_public_keys`.

### Running Registration

Create or update your local config:

```bash
cp config/lab_client.example.json config/lab_client.local.json
```

Fill in:

- `private_key_file`, for example `../keys/member1_private.pem`
- the three `member_public_keys`
- optionally `listen_port` if another local IPv8 client is already using the default port

Run registration with:

```bash
register-lab-group --config config/lab_client.local.json
```

The command will:

- start an IPv8 node
- join the lab group-signing community
- discover peers through IPv8 random walk and bootstrappers
- find the lab server by matching `server_public_key`
- send the group registration payload with the three public keys
- print the server response: `success`, `group_id`, and `message`

## Group Member Discovery

Your teammates appear as peers in the same Lab 2 IPv8 community. The client can discover all peers in the community and
filter the known group members by the public keys in `member_public_keys`.

Run teammate discovery with:

```bash
discover-lab-members --config config/lab_client.local.json
```

Your local private key must match one of the three configured public keys. If it does not, discovery fails immediately.
Otherwise, the command expects to find the other two members.

You can also send a signed group-internal test message to discovered members:

```bash
discover-lab-members --config config/lab_client.local.json --send "hello from member1"
```

Group-internal messages are sent inside the same Lab 2 community with IPv8 authenticated messaging. The receiver checks
the sender from the packet signature, ignores messages from public keys outside `member_public_keys`, and prints the
sender MID and public key for accepted messages.

## Code Layout

- `src/lab_group_client/config.py`
  Loads the JSON config, validates the three public keys, requires the private key file to exist, and builds the IPv8
  config with random-walk server discovery.

- `src/lab_group_client/community.py`
  Defines the IPv8 protocol messages and community logic. `RegisterPayload` is `message_id=1`.
  `RegisterResponsePayload` is `message_id=2`. This file also sends registration to the discovered server peer and
  accepts only authenticated responses from the configured server public key. `GroupMessagePayload` is used for signed
  group-internal messages between discovered teammates.

- `src/lab_group_client/register_group.py`
  CLI workflow for registration. It starts IPv8, waits until the server is discovered by public key, calls the community
  registration method, and prints the result.

- `src/lab_group_client/discover_members.py`
  Separate CLI workflow for teammate discovery. It starts IPv8, filters discovered peers by `member_public_keys`, and
  can optionally send a group-internal test message to each matched teammate.

- `src/lab_group_client/keys.py`
  Small helper CLI for printing the public key hex from an existing private key file.

- `config/lab_client.example.json`
  Template config. Copy this to a local config and fill in real key values.

- `requirements.txt` and `pyproject.toml`
  Python dependency and install metadata. The installable package is `pyipv8`, while the upstream repository is
  `Tribler/py-ipv8`.

## Signature Order

- marina
- ada
- galya
