# Multi-Chain Asset Manager (EVM & SVM)

A unified command-line tool for managing assets across disparate blockchain architectures: **EVM** (Polygon/Ethereum) and **SVM** (Solana). 
Designed for high-frequency operations like bulk transfers and token distribution.

### ⚡ Key Features

* **Polygon (EVM) Bulk Sender:**
  * Implements manual `nonce` management for high-throughput transaction broadcasting.
  * Bypasses "wait for confirmation" blocking loops for mass-payouts.
  * Supports native asset (MATIC/ETH) distribution from a list.

* **Solana (SVM) Token Operations:**
  * Uses modern `solders` library for interaction with SPL Tokens.
  * Handles Associated Token Account (ATA) derivation logic.
  * Supports `transfer_checked` instruction for secure token transfers.

### 🛠 Tech Stack
* **Python 3.10+**
* **Web3.py** (Ethereum Virtual Machine interaction)
* **Solana-py / Solders** (Solana Virtual Machine interaction)
* **Loguru** (Structured logging)

### 🚀 Usage
1. Configure `config.py` with your RPC endpoints and Private Keys.
2. Prepare `addresses.txt` for bulk operations.
3. Run `python main.py`.