import os
from typing import List
from dotenv import load_dotenv
import boto3
import jwt
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


load_dotenv()

AWS_REGION     = os.getenv("AWS_REGION")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")
SECRET_KEY     = os.getenv("SECRET_KEY")


app = FastAPI()
bearer = HTTPBearer()

def verifyToken(
    creds: HTTPAuthorizationCredentials = Depends(bearer)
) -> str:
    token = creds.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table    = dynamodb.Table(DYNAMODB_TABLE)

@app.get("/search/city/{city}",dependencies=[Depends(verifyToken)])
async def searchByCity(city: str):
    resp = table.scan(
        FilterExpression="city = :c",
        ExpressionAttributeValues={":c": city}
    )
    items = resp.get("Items", [])
    if not items:
        raise HTTPException(status_code=404, detail="No users in this city")
    return {"users": items}

@app.get("/search/age/{min_age}/{max_age}",dependencies=[Depends(verifyToken)])
async def searchByAge(min_age: int, max_age: int):
    resp = table.scan()
    items = resp.get("Items", [])
    users = [u for u in items if min_age <= u.get("age", 0) <= max_age]
    if not users:
        raise HTTPException(status_code=404, detail="No users in this age range")
    return {"users": users}

@app.get("/search/interests",dependencies=[Depends(verifyToken)])
async def searchByInterests(
    interests: List[str] = Query(..., description="Lista interesa za pretragu")
):
    resp = table.scan()
    items = resp.get("Items", [])
    users = [
        u for u in items
        if isinstance(u.get("interests"), list) and any(i in u["interests"] for i in interests)
    ]
    if not users:
        raise HTTPException(status_code=404, detail="No users with these interests")
    return {"users": users}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run( app, host="0.0.0.0", port=8004, reload=True)
