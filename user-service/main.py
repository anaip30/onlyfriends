import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import boto3
import jwt

load_dotenv()

AWS_REGION     = "eu-north-1"
DYNAMODB_TABLE = "OnlyFriendUser"
SECRET_KEY     = "onlyfriends-secret"

app = FastAPI()

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table    = dynamodb.Table(DYNAMODB_TABLE)

bearer = HTTPBearer()

class UserProfile(BaseModel):
    name: str
    age: int
    city: str
    interests: list[str]

def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    token = creds.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("uid")
        if user_id is None:
            raise HTTPException(401,"Tokenu nedostaje korisnički ID ")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

@app.get("/users/{user_id}")
async def get_user(user_id: str, current_user_id_from_token: str = Depends(get_current_user_id)):
    try:
        resp = table.get_item(Key={"id": user_id})
        if "Item" not in resp:
            raise HTTPException(404, "User nije pronaden")
        return resp["Item"]
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")

@app.put("/users/{user_id}")
async def update_user_profile(user_id: str, data: UserProfile, current_user_id_from_token: str = Depends(get_current_user_id)):
    if user_id != current_user_id_from_token:
        raise HTTPException(403, "Nije ovlašteno ažurirati ovaj profil")
    resp = table.get_item(Key={"id": user_id})
    if "Item" not in resp:
        raise HTTPException(404, "Korisnik nije nađen")

    table.update_item(
        Key={"id": user_id},
        UpdateExpression="SET #nm = :n, age = :a, city = :c, interests = :i",
        ExpressionAttributeNames={"#nm": "name"},
        ExpressionAttributeValues={
            ":n": data.name,
            ":a": data.age,
            ":c": data.city,
            ":i": data.interests,
        }
    )
    return {"message": "Profile updated"}

@app.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user_id_from_token: str = Depends(get_current_user_id)):
    if user_id != current_user_id_from_token:
        raise HTTPException(403, "Ne možes obrisat acc")

    resp = table.get_item(Key={"id": user_id})
    if "Item" not in resp:
        raise HTTPException(404, "Korisnik nije pronaden")

    table.delete_item(Key={"id": user_id})

    return {"message": f"User with ID '{user_id}' deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)