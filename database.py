import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables from .env
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Curinox_Centeral_DB")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set in .env")

# Connect to MongoDB Atlas
client = MongoClient(MONGODB_URI)

# Select database
db = client[MONGODB_DATABASE]

# Select collection
scans_collection = db["scans"]


def initialize_database():
    """
    Verify that MongoDB Atlas is reachable.
    MongoDB creates the database and collection automatically
    when the first document is inserted.
    """
    client.admin.command("ping")


def save_scan(filename, expiry, month, year):
    """
    Save a medicine scan to MongoDB.
    """

    document = {
        "filename": filename,
        "expiry": expiry,
        "month": month,
        "year": year
    }

    result = scans_collection.insert_one(document)

    return str(result.inserted_id)


def get_all_scans():
    """
    Get all medicine scans, newest first.
    """

    documents = scans_collection.find().sort("_id", -1)

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