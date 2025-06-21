import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import boto3
import jwt


load_dotenv()

AWS_REGION     = os.getenv("AWS_REGION")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")
SECRET_KEY     = os.getenv("SECRET_KEY")


app = FastAPI()

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table    = dynamodb.Table(DYNAMODB_TABLE)

bearer = HTTPBearer()


class UserProfile(BaseModel):
    name: str
    age: int
    city: str
    interests: list[str]

def getCurrentUser(
    creds: HTTPAuthorizationCredentials = Depends(bearer)
) -> str:
    token = creds.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")

@app.get( "/users/{userId}", dependencies=[Depends(getCurrentUser)])

async def getUser(userId: str):
    resp = table.get_item(Key={"username": userId})
    if "Item" not in resp:
        raise HTTPException(404, "User not found")
    return resp["Item"]


@app.put("/users/{userId}",dependencies=[Depends(getCurrentUser)])

async def updateUserProfiil(userId: str, data: UserProfile):
    resp = table.get_item(Key={"username": userId})
    if "Item" not in resp:
        raise HTTPException(404, "User not found")

    table.update_item(
        Key={"username": userId},
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)