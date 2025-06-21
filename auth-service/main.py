from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel , Field
import boto3
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

app = FastAPI()

load_dotenv()

AWS_REGION     = os.getenv("AWS_REGION")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")
SECRET_KEY     = os.getenv("SECRET_KEY")

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


def createJwt(username: str) -> str:
    expiration = datetime.now() + timedelta(days=1)
    payload = {"sub": username, "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

@app.post("/register")
async def register(user: UserRegister):
    existing = table.get_item(Key={"username": user.username})
    if "Item" in existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    hashPassword = hashPass(user.password)

    table.put_item(Item={"username": user.username, "password": hashPassword})
    return {"message": "Registracija uspješna"}


@app.post("/login")
async def login(user: UserLogin):
    result = table.get_item(Key={"username": user.username})
    if "Item" not in result:
        raise HTTPException(status_code=401, detail="Neispravno korisničko ime ")
    
    storedPassword = result["Item"]["password"]
    if not verifyPassword(user.password, storedPassword):
        raise HTTPException(status_code=401, detail="Neispravna lozinka")
    
    token = createJwt(user.username)
    return {"token": token}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run( app, host="0.0.0.0", port=8001, reload=True)