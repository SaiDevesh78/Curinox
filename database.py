import os
from dotenv import load_dotenv
import pymongo

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE")

client = pymongo.MongoClient(MONGODB_URI)
mydb = client[MONGODB_DATABASE]
ai_meds_data = mydb["AI_Medical_Data"]


def initialize_database():
    try:
        client.admin.command("ping")
        print("Connected to MongoDB successfully.")
    except Exception as e:
        print("MongoDB connection error:", e)


def save_scan(data: dict):
    # Pass a shallow copy so PyMongo does not alter the dict in-place with ObjectId
    doc = data.copy()
    result = ai_meds_data.insert_one(doc)
    return str(result.inserted_id)


def get_all_scans():
    documents = ai_meds_data.find().sort("_id", -1)
    scans = []
    for doc in documents:
        doc["_id"] = str(doc["_id"])
        scans.append(doc)
    return scans