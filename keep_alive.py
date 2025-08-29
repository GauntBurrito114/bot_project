import requests
import asyncio
import os
from dotenv import load_dotenv
import logging

load_dotenv()

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

logging.basicConfig(level=logging.INFO)

async def keep_alive():
    while True:
        if not RENDER_EXTERNAL_URL:
            logging.error("RENDER_EXTERNAL_URL が設定されていないため keep_alive を終了します。")
            return

        try:
            response = requests.get(RENDER_EXTERNAL_URL, timeout=10)
            if response.status_code == 200 and "Bot is running!" in response.text:
                logging.info("keep alive OK")
            else:
                logging.warning(f"Unexpected response: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending keep alive request: {e}")

        await asyncio.sleep(180)  # 3分ごと

async def start_keep_alive():
    await keep_alive()

if __name__ == "__main__":
    asyncio.run(start_keep_alive())
