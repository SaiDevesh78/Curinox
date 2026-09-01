import pymongo

Database_pass = "Koi4Ou9QN3p5TdMW"
Database_user = "Work_Group_User"
client = pymongo.MongoClient(f"mongodb+srv://{Database_user}:{Database_pass}@central-db.cc9nwzn.mongodb.net/?retryWrites=true&w=majority")
mydb = client["Curinox_Centeral_DB"]
user_data = mydb["User_Data"]
ai_meds_data = mydb["AI_Medical_Data"]
user_cabinet_data = mydb["User_Cabinet_Data"]

Name = input()
Password = input()
Gender = input()
DoB = input()
Address = input()
Phone_Number = input()
Email = input()
Activity = input()
table = user_data

def add_user_data(Name, Email, Password, Phone_Number, Gender, DoB, Address,  Activity, table):
    global new_userdata
    counter = 0
    for x in user_data.find({},{"_id": 1}):
        counter = counter+1
    counter = counter+1
    _id = f"User {counter}"
    new_userdata = {
                    "_id": _id,
                    "Name": Name,
                    "Email": Email,
                    "Password": Password,
                    "Phone Number": Phone_Number,
                    "Gender": Gender,
                    "DoB": DoB,
                    "Activity": Activity,
                    "Address": Address,
    }
    table.insert_one(new_userdata)
    
add_user_data(Name, Email, Password, Phone_Number, Gender, DoB, Address, Activity, table)