from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def hello():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def start_web_server():
    threading.Thread(target=run_flask).start()

if __name__ == "__main__":
    start_web_server()