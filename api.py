from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import pymongo

load_dotenv()
MONGODB_URI1 = "mongodb+srv://Work_Group_User:Koi4Ou9QN3p5TdMW@central-db.cc9nwzn.mongodb.net/?retryWrites=true&w=majority"
MONGODB_URI2 = "mongodb+srv://samarthshetty010:OJpIVovdzk6pr0rg@curionixcluster.w7eyivy.mongodb.net/?retryWrites=true&w=majority"
MONGODB_DATABASE1 = "Curinox_Centeral_DB"
MONGODB_DATABASE2 = "Curinox_Centeral_DB"
client1 = pymongo.MongoClient(MONGODB_URI1)
client2 = pymongo.MongoClient(MONGODB_URI2)
mydb1 = client1[MONGODB_DATABASE1]
mydb2 = client2[MONGODB_DATABASE2]
user_data = mydb1["User_Data"]
reminder_data = mydb1["Reminder_Data"]
medical_cabinet_data = mydb2["Medical_Cabinet_Data"]#Add Coolection name like medical_cabient_data
medicine_data = mydb2["Medicine_Data"]#Add Coolection name like medicine_data this is for those 6 tablets u saved
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    elif password != password_test:
        return {"ok": False, "error": "Password is incorrect"}
    else:
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
    cabinet_item_id = f"cab_{medical_cabinet_data.count_documents({'user_id': user_id})+1}"
    data = {"user_id": user_id, "cabinet_item_id": cabinet_item_id, **data}
    medical_cabinet_data.insert_one(data)
    print("Received cabinet:", data)
    return {"ok": True}

#------------------------------------------------------------------------------------------

"""{
  "ok": true,
  "stage": "medicine_detection",
  "scan_session_id": "scan_123",
  "medicine_id": "MED001",
  "medicine_found": true,
  "confidence": 0.91,
  "next_step": "TURN_MEDICINE_OVER"
}"""

#Assuming that the code is already assigning a medicine_id and scan_id
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
#For next stage resend the scan and medicine_id for the backend to add that
    return {"ok": True, "medicine_id": data.get("medicine_id"), "scan_session_id": data.get("scan_session_id"), "message": "Medicine identified successfully. Please turn the medicine over for further processing."}

#------------------------------------------------------------------------------------------

"""{
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
    return {"ok": True, "medicine_id": data.get("medicine_id"), "scan_session_id": data.get("scan_session_id"), "expiry_date": data.get("expiry_date"), "message": "Expiry date identified successfully. Please confirm the details."}

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
    # Assuming that the medicine_id and expiry_date are already provided in the request body
    medicine_id = data.get("medicine_id")
    # Need the structure for this and what all you want to add to the cabinet
    # Here i am just getting the medicine name from ur db
    medicine_info = medicine_data.find_one({"medicine_id": medicine_id}, {"_id": 0, "tablet_name": 1, "generic_name": 1})
    scan_session_id = data.get("scan_session_id")
    expiry_date = data.get("expiry_date")
    user_id = data.get("user_id")
    data = {
        "user_id": user_id,
        "medicine_id": medicine_id,
        "scan_session_id": scan_session_id,
        "tablet_name": medicine_info.get("tablet_name"),
        "generic_name": medicine_info.get("generic_name"),
        "expiry_date": expiry_date,
    }
    medical_cabinet_data.insert_one(data)
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
            {"tablet_name": regex_pattern},
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

@app.put("/reminders/{reminder_id}")
def update_reminder(reminder_id: str, data: dict = Body(...)):
    if not reminder_id:
        return {"ok": False, "error": "reminder id is required"}
    user_id = data.get("user_id")
    if not user_id:
        return {"ok": False, "error": "user id is required"}
    """ 
    Things they can update for now:
    "tablet_name": "Vitamin D",
    "time": "08:00",
    "frequency": "daily"
    """
    tablet_name = data.get("tablet_name")
    time = data.get("time")
    frequency = data.get("frequency")
    update = {}
    if tablet_name:
        update["tablet_name"] = tablet_name
    if time:
        update["time"] = time
    if frequency:
        update["frequency"] = frequency
    if update:
        update = reminder_data.update_one(
            {"reminder_id": reminder_id, "user_id": user_id},
            {"$set": update})
    if update.matched_count == 0:
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