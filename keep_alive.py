import requests
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

async def keep_alive():
    while True:
        try:
            response = requests.get(RENDER_EXTERNAL_URL)
            print(f"keep alive request sent. status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending keep alive request: {e}")
        await asyncio.sleep(180)  # asyncio.sleepを使用

async def start_keep_alive():
    await keep_alive()

if __name__ == "__main__":
    asyncio.run(start_keep_alive())