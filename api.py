from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
import pymongo
import uuid

load_dotenv()

MONGODB_URI1 = f"mongodb+srv://{os.getenv('MONGODB_USER1')}:{os.getenv('MONGODB_PASSWORD1')}@central-db.cc9nwzn.mongodb.net/?retryWrites=true&w=majority"
MONGODB_URI2 = f"mongodb+srv://{os.getenv('MONGODB_USER2')}:{os.getenv('MONGODB_PASSWORD2')}@curionixcluster.w7eyivy.mongodb.net/"
MONGODB_DATABASE1 = os.getenv('MONGODB_DATABASE1')
MONGODB_DATABASE2 = os.getenv('MONGODB_DATABASE2')
client1 = pymongo.MongoClient(MONGODB_URI1)
client2 = pymongo.MongoClient(MONGODB_URI2)
mydb1 = client1[MONGODB_DATABASE1]
mydb2 = client2[MONGODB_DATABASE2]
user_data = mydb1["User_Data"]
reminder_data = mydb1["Reminder_Data"]
missed_reminder = mydb1["Missed_Reminder_Data"]
medical_cabinet_data = mydb1["User_Cabinet_Data"]
temp_data = mydb1["Temp_Data"]
temp_data.create_index("created_at", expireAfterSeconds=300)
medicine_data = mydb2["Medicine_Master"]
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

#------------------------------------------------------------------------------------------
# HEALTH CHECK (I ADDED FOR FUN)
#------------------------------------------------------------------------------------------

@app.get("/")
def root_health_check():
    return {"status": "online", "system": "Curinox API"}

#------------------------------------------------------------------------------------------
# USER SIGNUP AND LOGIN API PART FROM HERE
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

@app.post("/signup-check")
def signup_check(data: dict = Body(...)):
    email = data.get("email")
    password = data.get("password")

    if email is None:
        return {"ok": False, "error": "Email is required"}
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
        elif user_data.find_one({"email": email}) != None:
            return {"ok": False, "error": "User with this email already exists"}
        else:
            password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            data = {"user_id": user_id, "email": email, "password": password}
            user_data.insert_one(data)
            data.pop("_id", None)
            return {"ok": True,  "user_id":user_id}

#------------------------------------------------------------------------------------------

@app.post("/new-user-data")
def new_user_data(data: dict = Body(...)):
    name = data.get("name")
    age = data.get("age")
    height = data.get("height")
    weight = data.get("weight")
    goal = data.get("goal")
    user_id = data.get("user_id")
    if not user_id: 
        return {"ok": False, "error": "user_id is not found in the request body"}
    newdata = {"name": name, "age": age, "height": height, "weight": weight, "goal": goal}
    user_data.update_one({"user_id": user_id}, {"$set": newdata})
    return {"ok": True, "message": "User data added successfully"}

#------------------------------------------------------------------------------------------

"""{
  "email": "sam@example.com",
  "password": "securepassword",
}"""

@app.post("/login-check")

def login_password_check(data: dict = Body(...)):
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return {"ok": False, "error": "Email and password are required"}
    
    user = user_data.find_one({"email": email}, {"email": 1, "password": 1, "user_id": 1, "_id": 0})
    
    if user is None:
        return {"ok": False, "error": "User with this email does not exist"}
    
    password_test = user.get("password")

    if password is None:
        return {"ok": False, "error": "Password is required"}
    if not bcrypt.checkpw(password.encode('utf-8'), password_test.encode('utf-8')):
        return {"ok": False, "error": "Password is incorrect"}

    return {"ok": True, "user_id": user.get("user_id")}

#------------------------------------------------------------------------------------------

@app.post("/get-user-data")
# NOTE THIS IS DIFFERENT NO JSON
def get_user_data(user_id: str):
    if not user_id:
        return {"ok": False, "error": "user_id is required"}
    profile = user_data.find_one({"user_id": user_id}, {"_id": 0})
    if profile is None:
        return {"ok": False, "error": "User not found"}
    reminders = list(reminder_data.find({"user_id": user_id}, {"_id": 0}))
    cabinet_items = list(medical_cabinet_data.find({"user_id": user_id}, {"_id": 0}))
    return {
        "ok": True,
        "profile": profile,
        "reminders": reminders,
        "medical_cabinet": cabinet_items
    }

#------------------------------------------------------------------------------------------

@app.post("/logout")
def logout():
    # This is justt name sake as our api is statless
    return {"ok": True, "message": "Logged out successfully"}

#------------------------------------------------------------------------------------------
# MEMBER ADDITON INTO FAMILY
#------------------------------------------------------------------------------------------

@app.post("/family-code-generation")
def family_code_generation(data: dict = Body(...)):
    user_id = data.get("user_id")
    if not user_id:
        return  {"ok": False, "error": "user_id Not Given"}
    code = uuid.uuid4().hex[:5]
    content = {
        "user_id": user_id,
        "member": None,
        "code": code,
        "verified": False,
        "created_at": datetime.now(timezone.utc)
    }
    temp_data.insert_one(content)
    return {"ok": True, "message": "Code Generated, Please add from other device", "code": code}

#------------------------------------------------------------------------------------------

@app.post("/family-code-validation")
def family_code_vailidation(data: dict = Body(...)):
    user_id = data.get("user_id")
    code = data.get("code")
    if not user_id or not code:
        return {"ok": False, "error": "user_id and code are required"}
    testcode = temp_data.find_one({"code": code}, {"_id": 0, "code": 1})
    if not testcode:
        return {"ok": False, "error": "Code Not Found or Expired"}
    if code == testcode.get("code"):
        verified = {"verified": True, "member": user_id, "created_at": datetime.now(timezone.utc)}
    else:
        verified = {"verified": False}
    temp_data.update_one({"code": code}, {"$set": verified})
    return {"ok": True, "message": "You have been added"}

#------------------------------------------------------------------------------------------

@app.get("/family-code-status")
def family_code_status(user_id: str):
    if not user_id:
        return {"ok": False, "error": "user_id is required"}
    testcode = temp_data.find_one({"user_id": user_id}, {"_id": 0, "verified": 1, "member": 1})
    if not testcode:
        return {"ok": False, "error": "Code Not Found or Expired"}
    if testcode.get("verified") == True:
        member = {"member":testcode.get("member")}
        if member:
            user_data.update_one({"user_id": user_id}, {"$set": member})
            temp_data.delete_one({"user_id": user_id})
            return {"ok": True, "message": "Member Added Sucessfully"}
        else:
            return {"ok": False, "error": "Member User ID not found"}
    else:
        return {"ok": False, "error": "Member has not accepted your request yet"}

#------------------------------------------------------------------------------------------

@app.get("/reminder-member-data")
def reminder_member_data(user_id: str):
    if not user_id:
        return {"ok": False, "error": "user_id is required"}
    member = user_data.find_one({"user_id": user_id}, {"_id": 0, "member": 1})
    if not member:
        return {"ok": False, "error": "member_id not found"}
    member = member.get("member")
    missed_data = missed_reminder.find_one({"user_id": member}, {"_id":0})
    if not missed_data:
        return {"ok": False, "message": "Member has no missed medicins"}
    return {"ok": True, "missed_reminders": missed_data}

#------------------------------------------------------------------------------------------
# MEDICAL CABINET API PART FROM HERE
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
    user_id = data.get("user_id")
    if not user_id:
        return {"ok": False, "error": "user_id is not found in the request body"}
    cabinet_item_id = f"cab_{uuid.uuid4().hex[:5]}"
    data = {"user_id": user_id, "cabinet_item_id": cabinet_item_id, **data}
    medical_cabinet_data.insert_one(data)
    return {"ok": True}

#------------------------------------------------------------------------------------------

"""{
  "user_id: user_id,
  "ok": true,
  "stage": "medicine_detection",
  "scan_session_id": "scan_123",
  "medicine_id": "MED001",
  "medicine_found": true,
  "confidence": 0.91,
  "next_step": "TURN_MEDICINE_OVER"
}"""

@app.post("/scan/medicine")
def scan_medicine(data: dict = Body(...)):
    if data.get("ok") is not True:
        return {"ok": False, "error": "Object detection failed, Please Retry"}
    if data.get("stage") != "medicine_detection":
        return {"ok": False, "error": "Invalid stage, Please Retry"}
    if data.get("medicine_found") is not True:
        return {"ok": False, "error": "Medicine not found in scan, Please Retry"}
    if data.get("confidence") < 0.8:
        return {"ok": False, "error": "Medicine identification is uncertain. Please reposition the medicine and try again"}
    medicine_id = data.get("medicine_id")
    scan_session_id = data.get("scan_session_id")
    user_id = data.get("user_id")
    temp_data.insert_one({"created_at": datetime.now(timezone.utc), "user_id":user_id, "medicine_id": medicine_id, "scan_session_id": scan_session_id})
    return {"ok": True, "message": "Medicine identified successfully. Please turn the medicine over for further processing."}

#------------------------------------------------------------------------------------------

"""{
  "user_id": user_id
  "ok": true,
  "stage": "expiry_detection",
  "scan_session_id": "scan_123" -- same as the previous scan session id,
  "medicine_id": "MED001" -- same as the previous medicine id,
  "expiry_found": true,
  "confidence": 0.91,
  "expiry_date": "2027-04-30",
  "ocr_text": "EXP 04/2027",
  "next_step": "CONFIRM"
}"""

@app.post("/scan/expiry")
def scan_expiry(data: dict = Body(...)):
    if data.get("ok") is not True:
        return {"ok": False, "error": "Expiry detection failed, Please Retry"}
    if data.get("stage") != "expiry_detection":
        return {"ok": False, "error": "Invalid stage, Please Retry"}
    if data.get("expiry_found") is not True:
        return {"ok": False, "error": "Expiry date not found in scan, Please Retry"}
    if data.get("confidence") < 0.8:
        return {"ok": False, "error": "Expiry date identification is uncertain. Please reposition the medicine and try again"}
    user_id = data.get("user_id")
    scan_session_id = data.get("scan_session_id")
    data_temp = {"expiry_date": data.get("expiry_date"), "created_at": datetime.now(timezone.utc)}
    if not scan_session_id or not user_id:
        return {"ok": False, "error": "scan_session_id and user_id are required"}
    test = temp_data.update_one({"user_id": user_id, "scan_session_id": scan_session_id}, {"$set": data_temp})
    if test.matched_count == 0:
        return {"ok": False, "error": "Scan session expired or not found"}
    return {"ok": True, "message": "Expiry date identified successfully. Please confirm the details."}

#------------------------------------------------------------------------------------------

"""
{
    "ok": true,
    "stage": "confirmation",
    "scan_session_id": "scan_123" -- same as the previous scan session id,
    "medicine_id": "MED001" -- same as the previous medicine id,
    "confirmation_status": true,
    "expiry_date": "2027-04-30"
}
"""

@app.post("/scan/confirmation")
def scan_confirmation(data: dict = Body(...)):
    if data.get("ok") is not True:
        return {"ok": False, "error": "Confirmation Canclled, Please Retry"}
    if data.get("stage") != "confirmation":
        return {"ok": False, "error": "Invalid stage, Please Retry"}
    if data.get("confirmation_status") is not True:
        return {"ok": False, "error": "Confirmation status is false, Please Retry"}
    user_id = data.get("user_id")
    if not user_id:
        return {"ok": False, "error": "user_id is required"}
    scan_session_id = data.get("scan_session_id")
    if not scan_session_id:
        return {"ok": False, "error": "scan_session_id is required"}
    data_temp = temp_data.find_one({"user_id": user_id, "scan_session_id": scan_session_id}, {"_id": 0})
    if not data_temp:
        return {"ok": False, "error": "session is not found or expired"}
    medicine_id = data_temp.get("medicine_id")
    medicine_info = medicine_data.find_one({"medicine_id": medicine_id}, {"_id": 0, "brand_name": 1})
    if medicine_info:
        brand_name = medicine_info.get("brand_name") 
    else: 
        brand_name = "Unknown"
    expiry_date = data_temp.get("expiry_date")
    cabinet_iteam_id = f"cab_{uuid.uuid4().hex[:5]}"
    data = {
        "user_id": user_id,
        "medicine_id": medicine_id,
        "cabinet_item_id": cabinet_iteam_id,
        "brand_name": brand_name,
        "expiry_date": expiry_date,
    }
    medical_cabinet_data.insert_one(data)
    temp_data.delete_one({"user_id": user_id, "scan_session_id": scan_session_id})
    return {"ok": True, "message": "Medicine details confirmed and updated successfully."}

#------------------------------------------------------------------------------------------

@app.get("/cabinet")
# mention user id in the url itself
def get_cabinet(user_id: str):
    meds = list(medical_cabinet_data.find({"user_id": user_id}, {"_id": 0}))
    return {"ok": True, "cabinet_items": meds}

#------------------------------------------------------------------------------------------

@app.put("/cabinet/{cabinet_item_id}")
# Assuming that your giving cabinet id (we have to)
def update_cabinet_item(cabinet_item_id: str,data: dict = Body(...)):
    # Ensure to send user id or else cooked
    user_id = data.get("user_id")
    # Only for expiry dates for now
    expiry_date = data.get("expiry_date")
    if not cabinet_item_id:
        return {"ok": False, "error": "cabinet_item_id is required"}
    if expiry_date is None:
        return {"ok": False, "error": "expiry_date is required"}
    if not user_id:
        return {"ok": False, "error": "user_id is required"}
    meds = medical_cabinet_data.update_one(
        {"cabinet_item_id": cabinet_item_id, "user_id": user_id},
        {"$set": {"expiry_date": expiry_date}}
    )
    if meds.matched_count == 0:
        return {"ok": False, "error": "Cabinet item not found"}
    return {"ok": True, "message": "Cabinet updated successfully"}

#------------------------------------------------------------------------------------------

@app.delete("/cabinet/{cabinet_item_id}")
# IN THE URL UR SUPPOSED TO GIV USER ID AND CABINET ID 
# examples: http://10.0.2.2:8000/cabinet/$cabinetItemId?user_id=$userId
def delete_cabinet_item(cabinet_item_id: str, user_id: str):
    if not cabinet_item_id:
        return {"ok": False, "error": "cabinet_item_id is required"}
    if not user_id:
        return {"ok": False, "error": "user_id is required"}
    meds = medical_cabinet_data.delete_one({"cabinet_item_id": cabinet_item_id, "user_id": user_id})
    if meds.deleted_count == 0:
        return {"ok": False, "error": "Cabinet item not found"}
    return {"ok": True, "message": "Cabinet item deleted successfully"}

#------------------------------------------------------------------------------------------

@app.get("/medicines/search")
def search_medicines(query: str):
    if not query:
        return {"ok": False, "error": "Search content is required"}
    regex_pattern = {"$regex": query, "$options": "i"}
    results = list(medicine_data.find({
        "$or": [
            {"brand_name": regex_pattern},
            {"generic_name": regex_pattern},
            {"search_keywords": regex_pattern}
        ]
    }, {"_id": 0}))
    return {"ok": True, "results": results}

#------------------------------------------------------------------------------------------

# This is once the user clicks on one of the 6 tablets after their inital search
@app.get("/medicines/{medicine_id}")
def get_medicine(medicine_id: str):
    # This is only for those 6 tablets you told about
    medicine = medicine_data.find_one({"medicine_id": medicine_id}, {"_id": 0})
    if medicine is None:
        return {"ok": False, "error": "Medicine not found"}
    return {"ok": True, "medicine": medicine}

#------------------------------------------------------------------------------------------
# REMINDER API PART FROM HERE
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
    user_id = data.get("user_id")
    cabinet_item_id = data.get("cabinet_item_id")
    if not user_id: 
        return {"ok": False, "error": "user id is not found in the request body"}
    if not cabinet_item_id:
        return {"ok": False, "error": "cabinet item id is not found in the request body"}
    cabinet_items = medical_cabinet_data.find_one({"user_id": user_id, "cabinet_item_id": cabinet_item_id})
    if cabinet_items is None:
        return {"ok": False, "error": "Cabinet item not found for the given cabinet item ID"}
    rem_id = f"rem_{reminder_data.count_documents({'user_id': user_id})+1}"
    data = {"user_id": user_id, "cabinet_item_id": cabinet_item_id, "reminder_id": rem_id, **data}
    reminder_data.insert_one(data)
    return {"ok": True, "message": "Reminder added successfully", "reminder_id": rem_id}

#------------------------------------------------------------------------------------------

@app.get("/reminders")
# mention user id in the url itself
def get_reminders(user_id: str):
    if not user_id:
        return {"ok": False, "error": "user id is required"}
    rems = list(reminder_data.find({"user_id": user_id}, {"_id": 0}))
    # For now im just sending all the data, we can specify what we want after testing
    return {"ok": True, "reminders": rems}

#------------------------------------------------------------------------------------------

@app.post("/reminders-update")
def reminder_update(data: dict = Body(...)):
    user_id = data.get("user_id")
    cabinet_id = data.get("cabinet_item_id")
    taken = data.get("taken") # Give True if taken False if not
    if not user_id or not cabinet_id:
        return {"ok": False, "error": "user_id or cabinet_id is required"}
    if taken == False:
        missed_reminder.update_one({"user_id": user_id}, {"$push": {"Missed_Reminders":{"cabinet_item_id": cabinet_id, "Date_Time": datetime.now(timezone.utc), "taken": False}}}, upsert=True)
        return {"ok": True, "taken": False}
    else:
        return {"ok": True, "taken": True}

#------------------------------------------------------------------------------------------

@app.put("/reminders/{reminder_id}")
def update_reminder(reminder_id: str, data: dict = Body(...)):
    if not reminder_id:
        return {"ok": False, "error": "reminder id is required"}
    user_id = data.get("user_id")
    if not user_id:
        return {"ok": False, "error": "user id is required"}
    """ 
    Things they can update for now:
    "brand_name": "Vitamin D",
    "time": "08:00",
    "frequency": "daily"
    """
    brand_name = data.get("brand_name")
    time = data.get("time")
    frequency = data.get("frequency")
    update = {}
    if brand_name:
        update["brand_name"] = brand_name
    if time:
        update["time"] = time
    if frequency:
        update["frequency"] = frequency
    if update:
        result = reminder_data.update_one(
            {"reminder_id": reminder_id, "user_id": user_id},
            {"$set": update})
        if result.matched_count == 0:
            return {"ok": False, "error": "Reminder not found"}
    
    reminder = reminder_data.find_one({"reminder_id": reminder_id, "user_id": user_id}, {"_id": 0})
    # If u want to show user the updated reminder i have also sent that back just in case
    return {"ok": True, "message": "Reminder updated successfully", "reminder": reminder}

#------------------------------------------------------------------------------------------

@app.delete("/reminders/{reminder_id}")
# IN THE URL UR SUPPOSED TO GIV USER ID AND CABINET ID
# examples: http://10.0.2.2:8000/cabinet/$cabinetItemId?user_id=$userId
def delete_reminder(reminder_id: str, user_id: str):
    if not user_id:
        return {"ok": False, "error": "user id is required"}
    if not reminder_id:
        return {"ok": False, "error": "reminder id is required"}
    result = reminder_data.delete_one({"reminder_id": reminder_id, "user_id": user_id})
    if result.deleted_count == 0:
        return {"ok": False, "error": "Reminder not found"}
        
    return {"ok": True, "message": "Reminder deleted successfully"}