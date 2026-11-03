"""EVM native-asset bulk sender (Polygon, Ethereum, BSC, any EVM chain)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from loguru import logger
from web3 import Web3
from web3.exceptions import Web3Exception
from web3.middleware import ExtraDataToPOAMiddleware

NATIVE_TRANSFER_GAS = 21_000


class EVMError(RuntimeError):
    """Raised for configuration or connectivity problems."""


@dataclass
class BulkResult:
    sent: list[tuple[str, str]] = field(default_factory=list)  # (address, tx hash)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (address, reason)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (raw line, reason)


def load_recipients(path: str | Path) -> tuple[list[str], list[tuple[str, str]]]:
    """Read one address per line. Blank lines and ``#`` comments are ignored.

    Returns ``(valid_checksummed_addresses, skipped)``. Duplicates are dropped
    so nobody is paid twice by accident.
    """
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"recipients file not found: {file}")

    valid: list[str] = []
    skipped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if not Web3.is_address(line):
            skipped.append((line, "invalid address"))
            continue
        checksummed = Web3.to_checksum_address(line)
        if checksummed in seen:
            skipped.append((line, "duplicate"))
            continue
        seen.add(checksummed)
        valid.append(checksummed)
    return valid, skipped


class EVMManager:
    def __init__(self, rpc_url: str, private_key: str | None, *, timeout: int = 30):
        if not private_key:
            raise EVMError("EVM_PRIVATE_KEY is not set (see .env.example)")

        self.web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout}))
        if not self.web3.is_connected():
            raise EVMError(f"cannot connect to EVM RPC: {rpc_url}")

        # Polygon/BSC and other POA chains put extra data in the block header.
        self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self.account = self.web3.eth.account.from_key(private_key)
        self.address = self.account.address
        self.chain_id = self.web3.eth.chain_id  # fetched once, not per tx
        logger.info(f"EVM wallet {self.address} on chain {self.chain_id}")

    # ── fees ──────────────────────────────────────────────────────────────
    def _fee_fields(self) -> dict:
        """EIP-1559 fees when supported, legacy gasPrice otherwise."""
        latest = self.web3.eth.get_block("latest")
        base_fee = latest.get("baseFeePerGas")
        if base_fee is None:
            return {"gasPrice": self.web3.eth.gas_price}
        priority = self.web3.eth.max_priority_fee
        # 2× base fee headroom keeps the tx valid through several full blocks.
        return {
            "type": 2,
            "maxPriorityFeePerGas": priority,
            "maxFeePerGas": base_fee * 2 + priority,
        }

    @staticmethod
    def _max_fee_per_gas(fees: dict) -> int:
        return fees.get("maxFeePerGas") or fees["gasPrice"]

    # ── bulk send ─────────────────────────────────────────────────────────
    def bulk_send_native(
        self,
        recipients_file: str | Path,
        amount_ether: Decimal | float | str,
        *,
        max_recipients: int = 500,
        dry_run: bool = False,
        delay: float = 0.3,
    ) -> BulkResult:
        """Send ``amount_ether`` of the native asset to every address in a file.

        Nonces are managed locally so transactions are broadcast without
        waiting for each confirmation. If a broadcast fails, the nonce is
        re-synced from the node so later transactions don't get stuck behind
        a gap.
        """
        result = BulkResult()
        recipients, result.skipped = load_recipients(recipients_file)
        for line, reason in result.skipped:
            logger.warning(f"skip {line!r}: {reason}")

        if not recipients:
            logger.error("no valid recipients")
            return result
        if len(recipients) > max_recipients:
            raise EVMError(
                f"{len(recipients)} recipients exceeds MAX_BULK_RECIPIENTS="
                f"{max_recipients}; raise the limit deliberately if this is intended"
            )

        # Decimal avoids float rounding (e.g. 0.1 MATIC -> 100000000000000000 wei).
        amount_wei = self.web3.to_wei(Decimal(str(amount_ether)), "ether")
        if amount_wei <= 0:
            raise EVMError("amount must be greater than zero")

        fees = self._fee_fields()
        worst_case_cost = len(recipients) * (
            amount_wei + NATIVE_TRANSFER_GAS * self._max_fee_per_gas(fees)
        )
        balance = self.web3.eth.get_balance(self.address)
        logger.info(
            f"{len(recipients)} recipients × {amount_ether} = "
            f"{self.web3.from_wei(amount_wei * len(recipients), 'ether')} "
            f"(+ gas, worst case total {self.web3.from_wei(worst_case_cost, 'ether')}); "
            f"balance {self.web3.from_wei(balance, 'ether')}"
        )
        if balance < worst_case_cost:
            raise EVMError("insufficient balance for amount + worst-case gas")

        if dry_run:
            logger.info("dry run — nothing broadcast")
            for addr in recipients:
                logger.info(f"would send to {addr}")
            return result

        # 'pending' includes our own not-yet-mined txs, so reruns don't collide.
        nonce = self.web3.eth.get_transaction_count(self.address, "pending")

        for recipient in recipients:
            tx = {
                "chainId": self.chain_id,
                "from": self.address,
                "to": recipient,
                "value": amount_wei,
                "nonce": nonce,
                "gas": NATIVE_TRANSFER_GAS,
                **fees,
            }
            try:
                signed = self.account.sign_transaction(tx)
                tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
            except (Web3Exception, ValueError) as exc:
                logger.error(f"failed {recipient}: {exc}")
                result.failed.append((recipient, str(exc)))
                # Re-sync: the failed tx did not consume the nonce.
                nonce = self.web3.eth.get_transaction_count(self.address, "pending")
                continue

            hex_hash = self.web3.to_hex(tx_hash)
            result.sent.append((recipient, hex_hash))
            logger.success(f"sent to {recipient} | {hex_hash}")
            nonce += 1
            time.sleep(delay)  # be gentle with public RPCs

        logger.info(
            f"done: {len(result.sent)} sent, {len(result.failed)} failed, "
            f"{len(result.skipped)} skipped"
        )
        return result
