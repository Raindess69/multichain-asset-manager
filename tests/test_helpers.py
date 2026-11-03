"""Offline unit tests for pure helpers (no network / no real keys)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from solders.keypair import Keypair
import base58

from modules.evm import load_recipients
from modules.solana import SolanaError, load_keypair, to_raw_amount


# ── EVM recipient parsing ──────────────────────────────────────────────────
VALID_A = "0x52908400098527886E0F7030069857D2E4169EE7"  # checksummed
VALID_B = "0xde709f2102306220921060314715629080e2fb77"  # lower-case, valid


def test_load_recipients_filters_and_dedups(tmp_path):
    f = tmp_path / "addr.txt"
    f.write_text(
        "\n".join([
            VALID_A,
            "# a comment",
            "",
            VALID_B + "  # inline comment",
            VALID_A.lower(),      # duplicate of A in different case
            "not-an-address",
        ]),
        encoding="utf-8",
    )
    valid, skipped = load_recipients(f)
    # VALID_B's EIP-55 checksum form happens to be all lower-case.
    assert valid == ["0x52908400098527886E0F7030069857D2E4169EE7",
                     "0xde709f2102306220921060314715629080e2fb77"]
    reasons = sorted(r for _, r in skipped)
    assert reasons == ["duplicate", "invalid address"]


def test_load_recipients_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_recipients(tmp_path / "nope.txt")


# ── Solana amount conversion ───────────────────────────────────────────────
def test_to_raw_amount_exact():
    assert to_raw_amount("1.5", 6) == 1_500_000
    assert to_raw_amount(Decimal("0.000001"), 6) == 1


def test_to_raw_amount_rejects_excess_precision():
    with pytest.raises(SolanaError):
        to_raw_amount("1.2345678", 6)


def test_to_raw_amount_rejects_nonpositive():
    with pytest.raises(SolanaError):
        to_raw_amount("0", 6)


# ── Solana key loading ─────────────────────────────────────────────────────
def test_load_keypair_base58_json_and_file(tmp_path):
    kp = Keypair()
    raw = bytes(kp)

    from_b58 = load_keypair(base58.b58encode(raw).decode())
    assert from_b58.pubkey() == kp.pubkey()

    from_json = load_keypair(str(list(raw)))
    assert from_json.pubkey() == kp.pubkey()

    keyfile = tmp_path / "id.json"
    keyfile.write_text(str(list(raw)), encoding="utf-8")
    from_file = load_keypair(str(keyfile))
    assert from_file.pubkey() == kp.pubkey()


def test_load_keypair_rejects_empty_and_garbage():
    with pytest.raises(SolanaError):
        load_keypair(None)
    with pytest.raises(SolanaError):
        load_keypair("definitely-not-a-key")
