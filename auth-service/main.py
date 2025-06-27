from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel , Field
import boto3
import os
import jwt
import bcrypt
import uuid 
from datetime import datetime, timedelta
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key 

app = FastAPI()

load_dotenv()

AWS_REGION     = os.getenv("AWS_REGION")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE") 
SECRET_KEY     = os.getenv("SECRET_KEY")
USERNAME_GSI = os.getenv("USERNAME_GSI")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)


class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str


def hashPass(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verifyPassword(plainpassword: str, hashedpassword: str) -> bool:
    return bcrypt.checkpw(plainpassword.encode("utf-8"), hashedpassword.encode("utf-8"))

def createJwt(user_id: str, username: str) -> str:
    expiration = datetime.now() + timedelta(days=1)
    payload = {
        "sub": username,
        "uid": user_id,
        "exp": expiration
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

@app.post("/register")
async def register(user: UserRegister):
    try:
        response = table.query(
            IndexName=USERNAME_GSI,
            KeyConditionExpression=Key('username').eq(user.username)
        )
        if response.get('Items'):
            raise HTTPException(400,"User with this username already exists")
    except Exception as e:
        raise HTTPException(500, f"Database query failed: {e}")

    hashPassword = hashPass(user.password)
    new_user_id = str(uuid.uuid4())

    table.put_item(
        Item={
            "id": new_user_id,
            "username": user.username,
            "password": hashPassword
        }
    )
    return {"message": "Registracija uspješna"}


@app.post("/login")
async def login(user: UserLogin):
    try:
        response = table.query(
            IndexName=USERNAME_GSI,
            KeyConditionExpression=Key('username').eq(user.username)
        )
        items = response.get('Items', [])
        if not items:
            raise HTTPException(401, "Neispravno korisničko ime")
    except Exception as e:
        raise HTTPException(500,f"Database query failed: {e}")
    
    user_item = items[0]
    storedPassword = user_item.get("password")
    if not storedPassword or not verifyPassword(user.password, storedPassword):
        raise HTTPException(401, "Neispravna lozinka")
    
    user_id = user_item.get("id")
    username = user_item.get("username")
    
    if not user_id:
        raise HTTPException(500, "User record is missing a permanent ID.")

    token = createJwt(user_id=user_id, username=username)
    return {"token": token}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run( app, host="0.0.0.0", port=8001, reload=True)