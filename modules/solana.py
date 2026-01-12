from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from spl.token.instructions import transfer_checked, get_associated_token_address
from solana.transaction import Transaction
from solana.rpc.types import TxOpts
from loguru import logger
import sys

class SolanaManager:
    def __init__(self, rpc_url, private_key_bytes):
        self.client = Client(rpc_url)
        # Инициализация из байтов
        self.sender = Keypair.from_bytes(private_key_bytes)
        logger.info(f"Solana Wallet Loaded: {self.sender.pubkey()}")

    def send_spl_token(self, recipient_addr: str, token_mint_addr: str, amount: int, decimals: int):
        """Отправка SPL токена"""
        try:
            mint = Pubkey.from_string(token_mint_addr)
            dest = Pubkey.from_string(recipient_addr)

            # Получаем адреса ATA (Associated Token Account)
            source_ata = get_associated_token_address(self.sender.pubkey(), mint)
            dest_ata = get_associated_token_address(dest, mint)

            # Формируем транзакцию
            logger.info("Building transaction...")
            txn = Transaction()
            
            # Добавляем инструкцию трансфера
            txn.add(
                transfer_checked(
                    amount=amount,
                    decimals=decimals,
                    program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
                    owner=self.sender.pubkey(),
                    source=source_ata,
                    dest=dest_ata,
                    mint=mint,
                    signers=[self.sender] #
                )
            )

            # Отправка
            opts = TxOpts(skip_confirmation=False, preflight_commitment="confirmed")
            resp = self.client.send_transaction(txn, self.sender, opts=opts)
            
            logger.success(f"Token Sent! Signature: {resp.value}")
            return True

        except Exception as e:
            logger.error(f"Solana Transfer Failed: {e}")
            return False