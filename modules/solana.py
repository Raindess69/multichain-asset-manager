"""Solana SPL token sender (classic Token and Token-2022 mints)."""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

from loguru import logger
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.models import TxOpts
from solders.keypair import Keypair
from solders.message import MessageV0
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from spl.token.instructions import (
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    create_idempotent_associated_token_account,
    get_associated_token_address,
    transfer_checked,
)
from spl.token.models import TransferCheckedParams

# Byte offset of `decimals` inside an SPL Mint account (same for Token-2022).
_MINT_DECIMALS_OFFSET = 44


class SolanaError(RuntimeError):
    """Raised for configuration, lookup, or transaction problems."""


def load_keypair(secret: str | None) -> Keypair:
    """Accept a base58 secret, a JSON byte array, or a path to a keypair file."""
    if not secret:
        raise SolanaError("SOL_PRIVATE_KEY is not set (see .env.example)")
    secret = secret.strip()

    # Only treat the value as a path if it plausibly is one; a long base58 or
    # JSON key would otherwise make the filesystem raise "File name too long".
    if not secret.startswith("["):
        try:
            candidate = Path(secret).expanduser()
            if candidate.is_file():
                secret = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    if secret.startswith("["):
        try:
            return Keypair.from_bytes(bytes(json.loads(secret)))
        except (ValueError, TypeError) as exc:
            raise SolanaError(f"invalid JSON byte-array key: {exc}") from exc
    try:
        return Keypair.from_base58_string(secret)
    except ValueError as exc:
        raise SolanaError(f"invalid base58 secret key: {exc}") from exc


def to_raw_amount(ui_amount: Decimal | str | float, decimals: int) -> int:
    """Convert a human amount (e.g. 1.5 USDC) to base units without float error."""
    raw = Decimal(str(ui_amount)) * (Decimal(10) ** decimals)
    if raw != raw.to_integral_value():
        raise SolanaError(f"{ui_amount} has more than {decimals} decimal places")
    if raw <= 0:
        raise SolanaError("amount must be greater than zero")
    return int(raw)


class SolanaManager:
    def __init__(self, rpc_url: str, secret: str | None):
        self.rpc_url = rpc_url
        self.sender = load_keypair(secret)
        logger.info(f"Solana wallet {self.sender.pubkey()}")

    async def _mint_info(self, client: AsyncClient, mint: Pubkey) -> tuple[Pubkey, int]:
        """Return (token program id, decimals) read from the mint account itself."""
        resp = await client.get_account_info(mint, commitment=Confirmed)
        account = resp.value
        if account is None:
            raise SolanaError(f"mint not found: {mint}")
        if account.owner not in (TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID):
            raise SolanaError(f"{mint} is not an SPL token mint (owner {account.owner})")
        decimals = bytes(account.data)[_MINT_DECIMALS_OFFSET]
        return account.owner, decimals

    async def send_spl_token_async(
        self,
        recipient_addr: str,
        token_mint_addr: str,
        ui_amount: Decimal | str | float,
        *,
        dry_run: bool = False,
    ) -> str | None:
        """Send ``ui_amount`` tokens. Returns the signature (None on dry run).

        Decimals and the token program are read on-chain, so the caller only
        supplies a human amount — no raw-unit or decimals guessing.
        """
        try:
            mint = Pubkey.from_string(token_mint_addr)
            owner = Pubkey.from_string(recipient_addr)
        except ValueError as exc:
            raise SolanaError(f"invalid address: {exc}") from exc

        payer = self.sender.pubkey()
        async with AsyncClient(self.rpc_url) as client:
            program_id, decimals = await self._mint_info(client, mint)
            amount = to_raw_amount(ui_amount, decimals)

            source_ata = get_associated_token_address(payer, mint, program_id)
            dest_ata = get_associated_token_address(owner, mint, program_id)

            balance = await client.get_token_account_balance(source_ata, commitment=Confirmed)
            have = int(balance.value.amount)
            if have < amount:
                raise SolanaError(f"insufficient token balance: have {have}, need {amount} (raw)")

            instructions = [
                # Creates the recipient's token account only if it doesn't exist yet.
                create_idempotent_associated_token_account(payer, owner, mint, program_id),
                transfer_checked(
                    TransferCheckedParams(
                        program_id=program_id,
                        source=source_ata,
                        mint=mint,
                        dest=dest_ata,
                        owner=payer,
                        amount=amount,
                        decimals=decimals,
                        signers=[],
                    )
                ),
            ]

            logger.info(
                f"{ui_amount} of {mint} ({'Token-2022' if program_id == TOKEN_2022_PROGRAM_ID else 'Token'}) "
                f"-> {owner}"
            )
            if dry_run:
                logger.info("dry run — nothing broadcast")
                return None

            blockhash = (await client.get_latest_blockhash(commitment=Confirmed)).value
            message = MessageV0.try_compile(payer, instructions, [], blockhash.blockhash)
            tx = VersionedTransaction(message, [self.sender])

            resp = await client.send_transaction(
                tx,
                opts=TxOpts(
                    preflight_commitment=Confirmed,
                    last_valid_block_height=blockhash.last_valid_block_height,
                ),
            )
            signature = resp.value
            await client.confirm_transaction(
                signature,
                commitment=Confirmed,
                last_valid_block_height=blockhash.last_valid_block_height,
            )
            logger.success(f"confirmed: {signature}")
            return str(signature)

    def send_spl_token(self, *args, **kwargs) -> str | None:
        """Synchronous wrapper for CLI use."""
        return asyncio.run(self.send_spl_token_async(*args, **kwargs))
