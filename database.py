import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import pymongo

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
CENTRAL_DB_NAME = os.getenv("MONGODB_DATABASE", "Curinox_Centeral_DB")
MEDICINE_DB_NAME = os.getenv("MEDICINE_DATABASE", "Curionix")

client = pymongo.MongoClient(MONGODB_URI)

# Connect to both database namespaces on Atlas
central_db = client[CENTRAL_DB_NAME]
medicine_db = client[MEDICINE_DB_NAME]

# Expose collections
medicine_master = medicine_db["Medicine_Master"]
medical_cabinet_data = central_db["Medical_Cabinet_Data"]
scan_sessions = central_db["Scan_Sessions"]


def initialize_database():
    try:
        client.admin.command("ping")
        print("Connected to MongoDB successfully.")
    except Exception as e:
        print("MongoDB connection error:", e)


def search_medicines_in_db(query: str):
    q = (query or "").strip()
    if not q:
        return []
    regex = {"$regex": q, "$options": "i"}
    cursor = medicine_master.find(
        {
            "$or": [
                {"brand_name": regex},
                {"aliases": regex},
                {"search_keywords": regex},
            ],
            "active": {"$ne": False},
        },
        {"_id": 0},
    )
    return list(cursor)


def get_medicine_by_id(medicine_id: str):
    return medicine_master.find_one({"medicine_id": medicine_id}, {"_id": 0})


def find_medicine_by_label(label: str):
    q = (label or "").strip()
    if not q:
        return None
    regex = {"$regex": f"^{q}$", "$options": "i"}
    return medicine_master.find_one(
        {
            "$or": [
                {"brand_name": regex},
                {"aliases": regex},
                {"search_keywords": regex},
            ],
            "active": {"$ne": False},
        },
        {"_id": 0},
    )


def create_scan_session(medicine_data: dict) -> str:
    session_id = str(uuid.uuid4())
    doc = {
        "scan_session_id": session_id,
        "medicine": medicine_data,
        "expiry_date": None,
        "status": "MEDICINE_IDENTIFIED",
        "created_at": datetime.now(timezone.utc),
    }
    scan_sessions.insert_one(doc)
    return session_id


def get_scan_session(session_id: str):
    return scan_sessions.find_one({"scan_session_id": session_id}, {"_id": 0})


def update_scan_session_expiry(session_id: str, expiry_date: str):
    scan_sessions.update_one(
        {"scan_session_id": session_id},
        {"$set": {"expiry_date": expiry_date, "status": "EXPIRY_DETECTED"}},
    )


def mark_session_consumed(session_id: str):
    scan_sessions.update_one(
        {"scan_session_id": session_id},
        {"$set": {"status": "CONFIRMED"}},
    )


def create_cabinet_item(user_id: str, medicine_id: str, expiry_date: str):
    cabinet_item_id = f"CAB-{uuid.uuid4().hex[:8].upper()}"
    doc = {
        "cabinet_item_id": cabinet_item_id,
        "user_id": user_id,
        "medicine_id": medicine_id,
        "expiry_date": expiry_date,
        "quantity": 1,
        "reminder_settings": {},
        "date_added": datetime.now(timezone.utc).isoformat(),
    }
    medical_cabinet_data.insert_one(doc)
    return cabinet_item_id