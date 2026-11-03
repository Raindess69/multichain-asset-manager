# Multi-Chain Asset Manager (EVM + Solana)

A small command-line tool for moving your own assets on two blockchain families:

- **EVM** (Polygon, Ethereum, BSC, Base, or any EVM chain): send the same amount of the native coin to a list of addresses, such as payroll, rewards, or airdrops to your own users.
- **Solana**: send an SPL token (classic Token and **Token-2022**) to one recipient.

Every send gets a **preview first**: the tool validates input, checks balances and gas, and shows what would happen. Nothing is broadcast until you type `yes`.

---

## Features

### EVM bulk sender
- **EIP-1559 fees** (`maxFeePerGas` / `maxPriorityFeePerGas`), with automatic fallback to legacy `gasPrice` on chains that don't support it.
- **POA-chain support** (Polygon, BSC) through `ExtraDataToPOAMiddleware`.
- **Local nonce management**: broadcasts without waiting for each confirmation. Nonces start from the `pending` count, so a rerun won't collide with transactions that are still in flight. If a send fails, the nonce is re-synced so later transactions don't get stuck behind a gap.
- **Pre-flight balance check**: aborts *before sending anything* if `amount + worst-case gas` for the whole batch exceeds your balance.
- **Address hygiene**: checksums every address, skips invalid lines and duplicates (so nobody gets paid twice), and supports `#` comments.
- **Safety cap**: `MAX_BULK_RECIPIENTS` (default 500) limits damage from a wrong or oversized file.
- **Exact amounts**: uses `Decimal`, not `float`, so 0.1 really means 0.1.

### Solana SPL sender
- Modern **versioned (v0) transactions** built with `solders`.
- **Reads decimals and the token program from the mint on-chain**, so you enter a human amount like `1.5` instead of raw units.
- **Token-2022** mints are detected and handled automatically.
- Creates the recipient's **associated token account** if it doesn't exist (idempotent, so it's safe to repeat).
- Checks your token balance before sending, then waits for **confirmation** within the blockhash validity window.

---

## Install

Requires **Python 3.10+**.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configure

Secrets come from environment variables or a local `.env` file. They are **never** written in code.

```bash
cp .env.example .env
# then edit .env
```

| Variable | Meaning |
|---|---|
| `EVM_RPC` | EVM RPC URL (default: Polygon public RPC) |
| `EVM_PRIVATE_KEY` | Hex private key of the paying wallet |
| `SOL_RPC` | Solana RPC URL (default: mainnet-beta) |
| `SOL_PRIVATE_KEY` | Base58 secret, a JSON byte array `[..]`, or a path to a keypair file such as `~/.config/solana/id.json` |
| `MAX_BULK_RECIPIENTS` | Hard cap on recipients per bulk run (default 500) |

`.env`, keypair files, and `addresses.txt` are git-ignored.

> **Security:** use a dedicated hot wallet that holds only what you plan to send. Don't put a main wallet's key on a machine you don't fully trust. Public RPCs are rate-limited, so use your own endpoint (Alchemy, Infura, Helius, QuickNode, …) for large batches.

## Usage

```bash
python main.py
```

**EVM bulk send:** prepare `addresses.txt` with one address per line:

```text
# team payouts
0x52908400098527886E0F7030069857D2E4169EE7
0xde709f2102306220921060314715629080e2fb77
```

Choose `1`, enter the amount per wallet, review the preview, and type `yes`.

**Solana:** choose `2`, then enter the recipient wallet, the token mint, and a human amount (for example `1.5`).

> Tip: try everything on a testnet first, such as Polygon Amoy or Solana devnet, by pointing `EVM_RPC` / `SOL_RPC` at it.

## Tests

```bash
pip install -r requirements-dev.txt "eth-tester[py-evm]"
pytest
```

The suite works fully offline:
- unit tests for address parsing, amount conversion, and key loading;
- **end-to-end bulk-send tests on an in-memory EVM chain** (`eth-tester`), covering real signing, sequential nonces, received balances, dry runs, the insufficient-balance guard, and the recipient cap.

## Project structure

```text
├── main.py             # Interactive CLI (preview → confirm → send)
├── config.py           # Env/.env configuration, no hard-coded secrets
├── modules/
│   ├── evm.py          # EVM bulk sender
│   └── solana.py       # Solana SPL sender
├── tests/              # Offline unit + EVM end-to-end tests
├── .env.example
└── requirements.txt
```

## Changelog — 2026 modernization

- **Fixed:** `config.py` had a syntax error (`[1, 2, 3...]`), so the app couldn't start.
- **Fixed:** `signed_tx.rawTransaction` → `raw_transaction` (renamed in web3.py v7+, which crashed every EVM send).
- **Fixed:** the Solana module imported `solana.transaction` and the sync `solana.rpc.api.Client`, both **removed** in current solana-py. It's now rewritten on `AsyncClient` with `solders` v0 transactions.
- **Fixed:** Solana sends failed when the recipient had no token account. It's now created idempotently.
- **Fixed:** raw-unit and decimals were typed by hand, which risked 1000× errors. They're now read from the mint.
- **Fixed:** `float` amounts caused rounding errors. Amounts now use `Decimal`.
- **Fixed:** a failed send left a nonce gap that stalled every later transaction. The nonce now re-syncs.
- **Added:** EIP-1559 fees, POA middleware, preview + confirmation, balance pre-check, dedup, recipient cap, and Token-2022 support.
- **Security:** private keys moved from source to env / `.env` (git-ignored).
- **Tests:** the project had none. It now has 11 tests, including EVM end-to-end tests.
- Pinned dependency ranges.
