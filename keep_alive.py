import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

def keep_alive():
    while True:
        try:
            response = requests.get(RENDER_EXTERNAL_URL)
            print(f"keep alive request sent. status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending keep alive request: {e}")
        time.sleep(180)
        
if __name__ == "__main__":
    keep_alive()