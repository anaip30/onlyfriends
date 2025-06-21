import os
from typing import List
from contextlib import asynccontextmanager

from dotenv import load_dotenv
import boto3
import jwt
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from weaviate import Client  

app = FastAPI(
    title="Recommendation Service",
    version="1.0",
    description="Generiranje preporuka koristeći Transformer embedding i Weaviate."
)

load_dotenv()


AWS_REGION         = os.getenv("AWS_REGION")
DYNAMODB_TABLE     = os.getenv("DYNAMODB_TABLE")
SECRET_KEY         = os.getenv("SECRET_KEY")
WEAVIATE_URL       = os.getenv("WEAVIATE_URL", "http://localhost:8080")


bearer_scheme = HTTPBearer()


dynamodb      = boto3.resource("dynamodb", region_name=AWS_REGION)
table         = dynamodb.Table(DYNAMODB_TABLE)

embedding_model: SentenceTransformer | None = None
weaviate_client: Client | None               = None

class UserProfileWithScore(BaseModel):
    name: str
    age: int
    city: str
    interests: List[str]
    score: float


def get_current_username(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> str:
    token = creds.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.on_event("startup")
def startup_event():
    global embedding_model, weaviate_client

    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    weaviate_client = Client(url=WEAVIATE_URL)

    schema = {
        "class": "UserProfile",
        "vectorizer": "none",
        "properties": [
            {"name": "name",      "dataType": ["string"]},
            {"name": "age",       "dataType": ["int"]},
            {"name": "city",      "dataType": ["string"]},
            {"name": "interests", "dataType": ["text"]}
        ]
    }
    try:
        weaviate_client.schema.create_class(schema)
    except:
        pass





@app.get(
    "/recommend",
    response_model=List[UserProfileWithScore],
    summary="Dohvati preporuke za prijavljenog korisnika"
)
async def recommend(
    topFriends: int = 5,
    username:   str = Depends(get_current_username)
):
    if embedding_model is None or weaviate_client is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    resp = table.get_item(Key={"username": username})
    if "Item" not in resp:
        raise HTTPException(status_code=404, detail="User profile not found")
    item = resp["Item"]

    text = (f"age: {item['age']}; city: {item['city']}; "
            f"interests: {', '.join(item['interests'])}")

    user_vec = embedding_model.encode(text).tolist()

    raw_query = f"""
    {{
      Get {{ UserProfile(
        nearVector: {{ vector: {user_vec}, limit: {topFriends + 1} }}
      ) {{ name age city interests _additional {{ certainty }} }} }}
    }}
    """
    try:
        result = weaviate_client.graphql.raw(raw_query)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Weaviate query failed: {e}")

    hits = result.get("data", {}).get("Get", {}).get("UserProfile", [])
    recs: List[UserProfileWithScore] = []
    for obj in hits:
        if obj.get("name") == item.get("name") and obj.get("age") == item.get("age"):
            continue
        recs.append(UserProfileWithScore(
            name=obj.get("name"),
            age=obj.get("age"),
            city=obj.get("city"),
            interests=obj.get("interests", "").split(", "),
            score=obj.get("_additional", {}).get("certainty", 0.0)
        ))
        if len(recs) >= topFriends:
            break
    return recs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
