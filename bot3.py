import time
import requests
import threading
from helius import TransactionsAPI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Helius API key
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

# Telegram bot token and chat ID
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Dictionary to store wallet addresses and their corresponding names
WALLETS = {
    "6wjQHFeiLNf294euPEEBjpd6W8RBJxAbg5MbkgkbyGTx": "Wallet 1",
    "CRj1X8gwvBckeeqqcHVK5WEA8fQzhAeiFcNgsDYSEV4a": "Wallet 2",
    # Add more wallets and their names here
}

def get_token_name(mint_address):
    url = "https://mainnet.helius-rpc.com/?api-key=" + HELIUS_API_KEY
    payload = {
        "jsonrpc": "2.0",
        "id": "get_token_name",
        "method": "getAsset",
        "params": {
            "id": mint_address,
            "options": {}
        }
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        result = response.json()
        if "result" in result and "content" in result["result"] and "metadata" in result["result"]["content"]:
            return result["result"]["content"]["metadata"]["name"]
    return mint_address

def send_telegram_notification(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"Failed to send Telegram notification. Status code: {response.status_code}")

def track_wallet_transactions(wallet_address, wallet_name):
    transactions_api = TransactionsAPI(HELIUS_API_KEY)
    last_processed_timestamp = int(time.time())

    while True:
        try:
            parsed_transaction_history = transactions_api.get_parsed_transaction_history(
                address=wallet_address,
                before=None
            )

            if parsed_transaction_history:
                for transaction in parsed_transaction_history:
                    if transaction["timestamp"] > last_processed_timestamp:
                        last_processed_timestamp = transaction["timestamp"]
                        message = f"New transaction detected for wallet {wallet_name} ({wallet_address}):\n"
                        message += f"Date: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(transaction['timestamp']))}\n"
                        message += f"Signature: [Click to view on Solscan](https://solscan.io/tx/{transaction['signature']})\n"

                        if "tokenTransfers" in transaction:
                            token_transfers = transaction["tokenTransfers"]
                            if len(token_transfers) > 2:
                                # Identify the tokens being swapped
                                token_in = None
                                token_out = None
                                amount_in = 0
                                amount_out = 0
                                for transfer in token_transfers:
                                    token_name = get_token_name(transfer["mint"])
                                    amount = transfer["tokenAmount"]
                                    if "decimals" in transfer:
                                        amount /= 10**transfer["decimals"]
                                    if token_name == "USD Coin" and amount_in == 0:
                                        token_in = token_name
                                        amount_in = amount
                                    elif token_out is None:
                                        token_out = token_name
                                        amount_out = amount

                                if token_in and token_out:
                                    message += f"Swap Summary:\n"
                                    message += f"Swapped {amount_in:.2f} {token_in} for {amount_out:.2f} {token_out} on Jupiter Aggregator\n"
                                else:
                                    message += "Token transfers:\n"
                                    for transfer in token_transfers:
                                        token_name = get_token_name(transfer["mint"])
                                        amount = transfer["tokenAmount"]
                                        if "decimals" in transfer:
                                            amount /= 10**transfer["decimals"]
                                        message += f"  {amount:.2f} {token_name}\n"
                            else:
                                message += "Token transfers:\n"
                                for transfer in token_transfers:
                                    token_name = get_token_name(transfer["mint"])
                                    amount = transfer["tokenAmount"]
                                    if "decimals" in transfer:
                                        amount /= 10**transfer["decimals"]
                                    message += f"  {amount:.2f} {token_name}\n"

                        send_telegram_notification(message)

            time.sleep(600)  # Check for new transactions every 10 minutes (600 seconds)

        except Exception as e:
            print(f"Error occurred while tracking wallet transactions: {e}")
            time.sleep(600)  # Wait for 10 minutes before retrying

if __name__ == "__main__":
    threads = []
    for wallet_address, wallet_name in WALLETS.items():
        print(f"Starting transaction tracking for wallet {wallet_name} ({wallet_address})")
        thread = threading.Thread(target=track_wallet_transactions, args=(wallet_address, wallet_name))
        thread.start()
        threads.append(thread)

    # Send a startup message to the Telegram channel
    startup_message = "Transaction tracking script has started. Everything is working correctly."
    send_telegram_notification(startup_message)

    for thread in threads:
        thread.join()