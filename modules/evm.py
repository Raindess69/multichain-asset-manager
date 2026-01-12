from web3 import Web3
from loguru import logger
import time
import sys

class EVMManager:
    def __init__(self, rpc_url, private_key):
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = self.web3.eth.account.from_key(private_key)
        self.address = self.account.address
        
        if not self.web3.is_connected():
            logger.error("Failed to connect to EVM RPC")
            sys.exit(1)

    def bulk_send_native(self, recipients_file: str, amount_ether: float):
        """Массовая отправка нативного токена (MATIC/ETH/BNB)"""
        try:
            with open(recipients_file, 'r') as f:
                recipients = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logger.error(f"File {recipients_file} not found")
            return

        logger.info(f"Loaded {len(recipients)} wallets. Prepare to send {amount_ether} to each.")
        
        # Получаем nonce один раз
        nonce = self.web3.eth.get_transaction_count(self.address)
        amount_wei = self.web3.to_wei(amount_ether, 'ether')
        
        for recipient in recipients:
            try:
                tx = {
                    'chainId': self.web3.eth.chain_id,
                    'from': self.address,
                    'to': self.web3.to_checksum_address(recipient),
                    'value': amount_wei,
                    'nonce': nonce,
                    'gas': 21000,
                    'gasPrice': self.web3.eth.gas_price
                }

                signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                
                logger.success(f"Sent to {recipient[:6]}... | Hash: {self.web3.to_hex(tx_hash)}")
                
                # Мы инкрементируем nonce сами, чтобы не ждать подтверждения (High Load подход)
                nonce += 1
                time.sleep(0.5) # Небольшая пауза, чтобы RPC не захлебнулась
                
            except Exception as e:
                logger.error(f"Failed to send to {recipient}: {e}")

        logger.info("Bulk send completed.")