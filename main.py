import config
from modules.evm import EVMManager
from modules.solana import SolanaManager
from loguru import logger
import sys

def main():
    print("=== MULTI-CHAIN ASSET MANAGER ===")
    print("1. Polygon Bulk Sender (MATIC)")
    print("2. Solana SPL Sender")
    print("0. Exit")
    
    choice = input("Select: ")

    if choice == "1":
        # Инициализация EVM
        try:
            bot = EVMManager(config.EVM_RPC, config.EVM_PRIVATE_KEY)
            file_name = input("Enter path to addresses file (e.g. addresses.txt): ")
            amount = float(input("Amount of MATIC per wallet: "))
            bot.bulk_send_native(file_name, amount)
        except Exception as e:
            logger.error(f"Error: {e}")

    elif choice == "2":
        # Инициализация Solana
        bot = SolanaManager(config.SOL_RPC, bytes(config.SOL_PRIVATE_KEY_BYTES))
        
        recipient = input("Recipient Address: ")
        token_mint = input("Token Mint Address: ")
        amount = int(input("Amount (raw units): ")) # Например 1000000 для 1 USDC
        decimals = int(input("Decimals (e.g. 6 for USDC): "))
        
        bot.send_spl_token(recipient, token_mint, amount, decimals)

    elif choice == "0":
        sys.exit()

if __name__ == "__main__":
    main()