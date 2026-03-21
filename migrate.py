import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("Xato: MONGO_URI .env faylida topilmadi!")
    exit()

print("MongoDB ga ulanilmoqda...")
client = MongoClient(MONGO_URI)
db = client.film_bot

if os.path.exists("admins.txt"):
    print("Adminlarni ko'chirish...")
    with open("admins.txt", "r") as f:
        admins = [int(line.strip()) for line in f if line.strip().isdigit()]
        db.config.update_one({"_id": "admins"}, {"$set": {"list": admins}}, upsert=True)

if os.path.exists("channels.txt"):
    print("Kanallarni ko'chirish...")
    with open("channels.txt", "r", encoding="utf-8") as f:
        channels = [line.strip() for line in f if line.strip()]
        db.config.update_one({"_id": "channels"}, {"$set": {"list": channels}}, upsert=True)

if os.path.exists("kino.txt"):
    print("Asosiy data ko'chirish...")
    with open("kino.txt", "r", encoding="utf-8") as f:
        data = json.load(f)
        db.data.update_one({"_id": "main_data"}, {"$set": {"data": data}}, upsert=True)

print("✅ Barcha ma'lumotlar muvaffaqiyatli MongoDB ga o'tkazildi!")
