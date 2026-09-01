import os
from dotenv import load_dotenv
import pymongo

# Load environment variables from .env
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE")

client = pymongo.MongoClient(MONGODB_URI)
mydb = client[MONGODB_DATABASE]
user_data = mydb["User_Data"]
ai_meds_data = mydb["AI_Medical_Data"]
user_cabinet_data = mydb["User_Cabinet_Data"]

def save_scan(filename, expiry, month, year):
    document = {
        "filename": filename,
        "expiry": expiry,
        "month": month,
        "year": year
    }

    ai_meds_data.insert_one(document)

def get_all_scans():
    documents = ai_meds_data.find().sort("_id", -1)

    scans = []

    for document in documents:
        scans.append({
            "id": str(document["_id"]),
            "filename": document.get("filename"),
            "expiry": document.get("expiry"),
            "month": document.get("month"),
            "year": document.get("year")
        })

    return scans