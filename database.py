# database.py
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """
    リクエストごとに新しいデータベース接続を確立して返します。
    PyMySQLを使用し、Azure Database for MySQLへの接続を想定しています。
    """
    try:
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME"),
            port=int(os.environ.get("DB_PORT", 3306)),
            # PyMySQLではカーソルをDictCursorにすることで、
            # カラム名をキーとする辞書形式で結果を取得できます。
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            # Azureに接続するための推奨SSL設定
            ssl_verify_cert=True,
            ssl_verify_identity=True
        )
        # print("--- データベース接続成功！ ---") # ログが大量になるためコメントアウト推奨
        return conn
    except pymysql.Error as e:
        print(f"!!!!!! データベース接続エラー !!!!!!!: {e}")
        return None