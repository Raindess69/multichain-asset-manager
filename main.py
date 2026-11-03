"""Interactive CLI for the multi-chain asset manager."""
from __future__ import annotations

import sys
from decimal import Decimal, InvalidOperation

from loguru import logger

import config
from modules.evm import EVMError, EVMManager
from modules.solana import SolanaError, SolanaManager


def _ask_decimal(prompt: str) -> Decimal:
    while True:
        try:
            value = Decimal(input(prompt).strip())
            if value > 0:
                return value
        except InvalidOperation:
            pass
        print("Enter a positive number, e.g. 0.5")


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} Type 'yes' to continue: ").strip().lower() == "yes"


def run_evm() -> None:
    bot = EVMManager(config.EVM_RPC, config.EVM_PRIVATE_KEY)
    path = input("Path to addresses file [addresses.txt]: ").strip() or "addresses.txt"
    amount = _ask_decimal("Amount of native coin per wallet: ")

    # Always preview first: validates file, balance and gas without sending.
    bot.bulk_send_native(path, amount, max_recipients=config.MAX_BULK_RECIPIENTS, dry_run=True)
    if not _confirm("Broadcast these transactions for real?"):
        logger.info("aborted")
        return
    result = bot.bulk_send_native(path, amount, max_recipients=config.MAX_BULK_RECIPIENTS)
    if result.failed:
        logger.warning("failed recipients:")
        for addr, reason in result.failed:
            logger.warning(f"  {addr}: {reason}")


def run_solana() -> None:
    bot = SolanaManager(config.SOL_RPC, config.SOL_PRIVATE_KEY)
    recipient = input("Recipient wallet address: ").strip()
    mint = input("Token mint address: ").strip()
    amount = _ask_decimal("Amount (human units, e.g. 1.5 for 1.5 USDC): ")

    bot.send_spl_token(recipient, mint, amount, dry_run=True)
    if not _confirm("Send for real?"):
        logger.info("aborted")
        return
    bot.send_spl_token(recipient, mint, amount)


def main() -> int:
    print("=== MULTI-CHAIN ASSET MANAGER ===")
    print("1. EVM bulk sender (native coin)")
    print("2. Solana SPL token sender")
    print("0. Exit")

    actions = {"1": run_evm, "2": run_solana}
    choice = input("Select: ").strip()
    if choice == "0":
        return 0
    action = actions.get(choice)
    if action is None:
        print("Invalid choice")
        return 1
    try:
        action()
    except (EVMError, SolanaError, FileNotFoundError) as exc:
        logger.error(str(exc))
        return 1
    except KeyboardInterrupt:
        logger.info("interrupted")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
