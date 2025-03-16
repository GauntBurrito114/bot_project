#botを落とさないための処理

from flask import Flask
from threading import Thread
app = Flask('')

#ルートディレクトリにアクセスした時の処理
@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()