import os

# EVM SETTINGS (Polygon)
EVM_RPC = "https://polygon-rpc.com"
EVM_PRIVATE_KEY = "YOUR_PRIVATE_KEY_HERE"  # Или используй os.getenv('EVM_PK')

# SOLANA SETTINGS
SOL_RPC = "https://api.mainnet-beta.solana.com"
SOL_PRIVATE_KEY_BYTES = [1, 2, 3...] # Твой массив байтов или путь к файлу .json
# Если ключ в формате Base58 (буквы), раскомментируй логику в solana.py

# TOKEN SETTINGS
SOL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"