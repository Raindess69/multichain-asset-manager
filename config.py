"""Runtime configuration.

Secrets are read from the environment (or a local, git-ignored ``.env``
file) and are never hard-coded. Copy ``.env.example`` to ``.env`` and fill
it in, or export the variables in your shell.
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path = Path(__file__).with_name(".env")) -> None:
    """Minimal ``.env`` loader (no extra dependency). Existing env vars win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# ── EVM (Polygon by default; any EVM chain works) ─────────────────────────
EVM_RPC: str = os.getenv("EVM_RPC", "https://polygon-rpc.com")
EVM_PRIVATE_KEY: str | None = os.getenv("EVM_PRIVATE_KEY")

# ── Solana ────────────────────────────────────────────────────────────────
SOL_RPC: str = os.getenv("SOL_RPC", "https://api.mainnet-beta.solana.com")
# Either a base58 secret key string, a JSON byte array "[1,2,...]", or a path
# to a Solana CLI keypair file (e.g. ~/.config/solana/id.json).
SOL_PRIVATE_KEY: str | None = os.getenv("SOL_PRIVATE_KEY")

# ── Safety ────────────────────────────────────────────────────────────────
# Upper bound on how many recipients one bulk run may pay, to limit damage
# from a malformed or wrong addresses file.
MAX_BULK_RECIPIENTS: int = int(os.getenv("MAX_BULK_RECIPIENTS", "500"))
