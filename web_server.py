import os
from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def hello():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))  # Render では PORT が環境変数で渡される
    app.run(host="0.0.0.0", port=port)

def start_web_server():
    thread = threading.Thread(target=run_flask)
    thread.daemon = True  # メインスレッド終了時に自動終了
    thread.start()

if __name__ == "__main__":
    start_web_server()
