import os
from typing import List
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import boto3
import jwt
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sentence_transformers import SentenceTransformer
from weaviate.client import WeaviateClient
from weaviate.connect.base import ConnectionParams
from weaviate.classes.query import MetadataQuery
from weaviate.classes.config import Configure, Property, DataType

load_dotenv()

AWS_REGION              = os.getenv("AWS_REGION")
DYNAMODB_TABLE          = os.getenv("DYNAMODB_TABLE")
SECRET_KEY              = os.getenv("SECRET_KEY")
WEAVIATE_HOST           = os.getenv("WEAVIATE_HOST")
WEAVIATE_HTTP_PORT      = int(os.getenv("WEAVIATE_HTTP_PORT"))
WEAVIATE_GRPC_PORT      = int(os.getenv("WEAVIATE_GRPC_PORT"))

bearer = HTTPBearer()

def get_current_user_info(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("uid")
        username = payload.get("sub")
        if not user_id or not username:
            raise HTTPException(401, "Tokenu nedostaju obavezni korisnički podaci (uid, sub))")
        return {"id": user_id, "username": username}
    except jwt.PyJWTError:
        raise HTTPException(401, "Nevažeći ili istekao token")

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    if not all([AWS_REGION, DYNAMODB_TABLE]):
        raise RuntimeError("AWS_REGION i DYNAMODB_TABLE moraju biti postavljeni u okruženju")
    
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    app.state.user_table = dynamodb.Table(DYNAMODB_TABLE)

    conn_params = ConnectionParams.from_params(
        http_host=WEAVIATE_HOST,
        http_port=WEAVIATE_HTTP_PORT,
        http_secure=False,
        grpc_host=WEAVIATE_HOST,
        grpc_port=WEAVIATE_GRPC_PORT,
        grpc_secure=False,
    )
    client = WeaviateClient(connection_params=conn_params)
    client.connect()
    if not client.is_ready():
        raise RuntimeError("Ne mogu se povezati s Weaviateom")
    app.state.weaviate_client = client

    if not client.collections.exists("Users"):
      client.collections.create(
        name="Users",
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            Property(name="username", data_type=DataType.TEXT),
            Property(name="name", data_type=DataType.TEXT),
            Property(name="age", data_type=DataType.INT),
            Property(name="city", data_type=DataType.TEXT),
            Property(name="interests", data_type=DataType.TEXT_ARRAY),
        ],
     )
      print(" Klasa Users kreirana!")
    else:
      print(" Klasa Users već postoji.")

    yield

    print("Ne mogu se povezati s Weaviateom")
    client.close()


app = FastAPI(lifespan=lifespan)

@app.get("/recommendations")
def get_recommendations(
    request: Request,
    current_user: dict = Depends(get_current_user_info) 
):
    current_user_id = current_user["id"]
    current_username = current_user["username"]

    try:
        resp = request.app.state.user_table.get_item(Key={"id": current_user_id})
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")

    item = resp.get("Item")
    if not item:
        raise HTTPException(404, "Korisnički profil nije pronađen u DynamoDB-u")

    text = (
        f"age: {item.get('age', 0)}; "
        f"city: {item.get('city', '')}; "
        f"interests: {', '.join(item.get('interests', []))}"
    )
    vec = request.app.state.embedding_model.encode(text).tolist()

    client: WeaviateClient = request.app.state.weaviate_client
    collection = client.collections.get("Users")

    try:
        query_resp = collection.query.near_vector(
            near_vector=vec,
            limit=10,
            return_metadata=MetadataQuery(distance=True)
        )
    except Exception as e:
        raise HTTPException(502, f"Weaviate query failed: {e}")

    recs = []
    for obj in query_resp.objects:
        props = obj.properties
        if props.get("username") == current_username:
            continue

        distance = obj.metadata.distance
        if distance is None:
            continue

        similarity = 1 - distance
        match_percentage = max(0, similarity * 100)

        recs.append({
            "username":  props.get("username"),
            "name":      props.get("name"),
            "age":       props.get("age"),
            "city":      props.get("city"),
            "interests": props.get("interests"),
            "match_percentage": round(match_percentage, 2)
        })

    return {"recommendations": recs}