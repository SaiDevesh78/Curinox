from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import pymongo

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE")

client = pymongo.MongoClient(MONGODB_URI)
mydb = client[MONGODB_DATABASE]
user_data = mydb["User_Data"]
reminder_data = mydb["Reminder_Data"]
medical_cabinet_data = mydb["Medical_Cabinet_Data"]
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

#------------------------------------------------------------------------------------------
"""{
  "email": "sam@example.com",
  "password": "securepassword",
  "name": "Sam",
  "age": 21,
  "height_cm": 175,
  "weight_kg": 68,
  "goal": "General wellness",
  "restrictions": []
}"""

@app.post("/signup-email-check")

def signup_email_check(data: dict = Body(...)):
    global email
    email = data.get("email")
    if email is None:
        return {"ok": False, "error": "Email is required"}
    elif user_data.find_one({"email": email}) != None:
        return {"ok": False, "error": "User with this email already exists"}
    else:
        return {"ok": True}

@app.post("/signup-password-check")

def signup_password_check(data: dict = Body(...)):
    global password
    password = data.get("password")
    if password is None:
        return {"ok": False, "error": "Password is required"}
    else:
        if len(password) < 8:
            return {"ok": False, "error": "Password must be at least 8 characters long"}
        elif not any(char.isdigit() for char in password):
            return {"ok": False, "error": "Password must contain at least one number"}
        elif not any(char.isupper() for char in password):
            return {"ok": False, "error": "Password must contain at least one uppercase letter"}
        elif not any(char.islower() for char in password):
            return {"ok": False, "error": "Password must contain at least one lowercase letter"}
        else:
            return {"ok": True}
        
@app.post("/signup-profile-creation")

def signup_profile_creation(data: dict = Body(...)):
    global user_id
    user_id = f"user_{user_data.count_documents({})+1}"
    data = {"user_id": user_id, "email": email, "password": password, **data}
    user_data.insert_one(data)
    print("Received profile:", data)
    return {"ok": True}

#------------------------------------------------------------------------------------------

"""{
  "email": "sam@example.com",
  "password": "securepassword",
}"""

@app.post("/login-email-check")

def login_email_check(data: dict = Body(...)):
    email = data.get("email")
    if email is None:
        return {"ok": False, "error": "Email is required"}
    else:
        return {"ok": True}

@app.post("/login-password-check")

def login_password_check(data: dict = Body(...)):
    email = data.get("email")
    password = data.get("password")
    user = user_data.find_one({"email": email}, {"email": 1, "password": 1, "user_id": 1, "_id": 0})
    password_test = user.get("password")
    global user_id
    user_id = user.get("user_id")
    if password is None:
        return {"ok": False, "error": "Password is required"}
    elif password != password_test:
        return {"ok": False, "error": "Password is inncorrect"}
    else:
        return {"ok": True}
        
#------------------------------------------------------------------------------------------
"""{
  "user_id": "user_1",
  "cabinet_item_id": "cab_1",
  "tablet_name": "Vitamin D",
  "time": "08:00",
  "frequency": "daily",
  "enabled": True
}"""

@app.post("/reminder")

def receive_reminder(data: dict = Body(...)):
    cabinet_items = medical_cabinet_data.find_one({"user_id": user_id, "tablet_name": data.get("tablet_name")})
    if cabinet_items is None:
        return {"ok": False, "error": "Cabinet item not found for the given tablet name"}
    else:
        cabinet_item_id = cabinet_items.get("cabinet_item_id")
        data = {"user_id": user_id, "cabinet_item_id": cabinet_item_id, **data}
        reminder_data.insert_one(data)
        print("Received reminder:", data)
        return {"ok": True}

#------------------------------------------------------------------------------------------
"""{
  "user_id": "user_1",
  "cabinet_item_id": "cab_1",
  "tablet_name": "Vitamin D",
  "generic_name": "Paracetamol",
  "expiry_date": "2027-04-30",
  "added_at": "2026-09-01T18:30:00Z"
}"""

@app.post("/cabinet")
def receive_cabinet(data: dict = Body(...)):
    cabinet_item_id = f"cab_{medical_cabinet_data.count_documents({'user_id': user_id})+1}"
    data = {"user_id": user_id, "cabinet_item_id": cabinet_item_id, **data}
    medical_cabinet_data.insert_one(data)
    print("Received cabinet:", data)
    return {"ok": True}

#------------------------------------------------------------------------------------------
"""{
  "user_id": "user_1",
  "cabinet_item_id": "cab_1",
  "medicine_found": true,
  "confidence": 0.91,
  "tablet_name": "Vitamin D",
  "generic_name": "Paracetamol",
  "expiry_date": "2027-04-30",
  "ocr_text": "DOLO 650 ... EXP 04/2027",
  "requires_confirmation": true
}"""
@app.post("/scan")
def receive_scan(data: dict = Body(...)):
    cabinet_item_id = f"cab_{medical_cabinet_data.count_documents({'user_id': user_id})+1}"
    data = {"user_id": user_id, "cabinet_item_id": cabinet_item_id, **data}
    medical_cabinet_data.insert_one(data)
    print("Received scan:", data)
    return {"ok": True}