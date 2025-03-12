# Discord出席管理Bot

このBotは、Discordサーバーでの出席管理を効率化するためのBotです。

## 機能

* 特定のメッセージへのリアクションによる出席登録
* 毎日の出席ロール自動削除
* 出席記録のチャンネルへの送信
* 管理コマンド（出席ロール削除など）

## 必要な環境

* Python 3.8以上
* discord.pyライブラリ
* python-dotenvライブラリ
* scheduleライブラリ
* Git

## 導入方法

1.  **リポジトリをクローン:**

    ```bash
    git clone https://github.com/GauntBurrito114/bot_project
    cd リポジトリ名
    ```

2.  **仮想環境の作成 (推奨):**

    ```bash
    python -m venv venv
    venv\Scripts\activate

3.  **必要なライブラリのインストール:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **.envファイルの作成:**

    * `.env.example`をコピーして`.env`ファイルを作成し、必要な環境変数を設定します。

        ```
        DISCORD_TOKEN=あなたのBotトークン
        debug_channel_id=デバッグ用チャンネルID
        attendance_confirmation_channel_id=出席確認メッセージを送信するチャンネルID
        attendance_record_channel_id=出席記録を送信するチャンネルID
        attendance_role_id=出席ロールID
        MESSAGE_ID=出席確認メッセージID
        ```

5.  **Botの起動:**

    ```bash
    python e-sport_bot.py
    ```

## 環境変数の設定

* `DISCORD_TOKEN`: Discord Botのトークン。
* `debug_channel_id`: デバッグ情報を送信するチャンネルのID。
* `attendance_confirmation_channel_id`: 出席確認メッセージを送信するチャンネルのID。
* `attendance_record_channel_id`: 出席記録を送信するチャンネルのID。
* `attendance_role_id`: 出席ロールのID。
* `MESSAGE_ID`: 出席確認メッセージのID。

## 使用方法

1.  Botをサーバーに招待します。
2.  `.env`ファイルに必要な情報を設定します。
3.  `bot.py`を実行してBotを起動します。
4.  指定されたチャンネルに出席確認メッセージが投稿されます。
5.  ユーザーはメッセージに指定されたリアクションを行うことで出席登録ができます。
6.  毎日指定された時間に出席ロールが自動的に削除されます。