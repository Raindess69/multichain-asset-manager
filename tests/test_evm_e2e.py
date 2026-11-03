"""End-to-end bulk send against an in-memory EVM chain (eth-tester).

Exercises real signing, EIP-1559 fees, local nonce management and balance
checks without touching any real network.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

eth_tester = pytest.importorskip("eth_tester")
from web3 import Web3, EthereumTesterProvider  # noqa: E402

from modules.evm import EVMError, EVMManager  # noqa: E402


@pytest.fixture
def manager(monkeypatch):
    provider = EthereumTesterProvider()
    w3 = Web3(provider)
    funded = provider.ethereum_tester.get_accounts()[0]
    sender = w3.eth.account.create()
    w3.eth.send_transaction({"from": funded, "to": sender.address, "value": w3.to_wei(10, "ether")})

    monkeypatch.setattr("modules.evm.Web3.HTTPProvider", lambda *a, **k: provider)
    mgr = EVMManager("http://unused", sender.key.hex())
    return mgr, w3


def _addresses(w3, n):
    return [w3.eth.account.create().address for _ in range(n)]


def test_bulk_send_pays_everyone_with_sequential_nonces(tmp_path, manager):
    mgr, w3 = manager
    recipients = _addresses(w3, 3)
    f = tmp_path / "addr.txt"
    f.write_text("\n".join(recipients), encoding="utf-8")

    result = mgr.bulk_send_native(f, Decimal("0.1"), delay=0)

    assert [a for a, _ in result.sent] == recipients
    assert not result.failed
    for addr in recipients:
        assert w3.eth.get_balance(addr) == w3.to_wei(Decimal("0.1"), "ether")
    assert w3.eth.get_transaction_count(mgr.address) == 3


def test_dry_run_sends_nothing(tmp_path, manager):
    mgr, w3 = manager
    recipients = _addresses(w3, 2)
    f = tmp_path / "addr.txt"
    f.write_text("\n".join(recipients), encoding="utf-8")

    result = mgr.bulk_send_native(f, "0.1", dry_run=True)

    assert result.sent == []
    assert all(w3.eth.get_balance(a) == 0 for a in recipients)


def test_insufficient_balance_is_rejected_before_any_send(tmp_path, manager):
    mgr, w3 = manager
    recipients = _addresses(w3, 2)
    f = tmp_path / "addr.txt"
    f.write_text("\n".join(recipients), encoding="utf-8")

    with pytest.raises(EVMError, match="insufficient balance"):
        mgr.bulk_send_native(f, "6", delay=0)  # 12 ETH > 10 ETH balance
    assert all(w3.eth.get_balance(a) == 0 for a in recipients)


def test_recipient_cap_is_enforced(tmp_path, manager):
    mgr, w3 = manager
    f = tmp_path / "addr.txt"
    f.write_text("\n".join(_addresses(w3, 3)), encoding="utf-8")

    with pytest.raises(EVMError, match="MAX_BULK_RECIPIENTS"):
        mgr.bulk_send_native(f, "0.1", max_recipients=2)
