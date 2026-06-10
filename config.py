import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if ADMIN_ID == 0:
    raise ValueError("ADMIN_ID не задан")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан (нужна строка подключения к PostgreSQL)")