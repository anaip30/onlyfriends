from dotenv import load_dotenv
import boto3, weaviate
import os
import uuid
from pydantic import BaseModel
from typing import List
from weaviate.client import WeaviateClient
from weaviate.connect.base import ConnectionParams
from sentence_transformers import SentenceTransformer

load_dotenv()

AWS_REGION     = os.getenv("AWS_REGION", "eu-north-1")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "users")
WEAVIATE_HOST  = os.getenv("WEAVIATE_HOST", "localhost")
WEAVIATE_PORT  = int(os.getenv("WEAVIATE_HTTP_PORT"))
GRPC_PORT      = int(os.getenv("WEAVIATE_GRPC_PORT"))

conn = ConnectionParams.from_params(
    http_host=WEAVIATE_HOST,
    http_port=WEAVIATE_PORT,
    http_secure=False,
    grpc_host=WEAVIATE_HOST,
    grpc_port=GRPC_PORT,
    grpc_secure=False
)
client = WeaviateClient(connection_params=conn)

print("Spajanje na Weaviate")
client.connect()

print("Ucitavanje modela.")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Hvatanje podataka")
dynamo = boto3.resource("dynamodb", region_name=AWS_REGION)
table  = dynamo.Table(DYNAMODB_TABLE)
items  = []
resp = table.scan()
items.extend(resp["Items"])
while "LastEvaluatedKey" in resp:
    resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
    items.extend(resp["Items"])

print(f"Found {len(items)} users in DynamoDB.")

coll = client.collections.get("Users")
print("Importanje u Weaviate.")
usersAddedCount = 0
with coll.batch.fixed_size(64) as batch:
    for it in items:
        requiredKeys = ["username", "name", "age", "city", "interests"]
        if not all(key in it for key in requiredKeys):
            print(f"⚠️  Preskačem korisnika jer mu nedostaju podaci: {it.get('username', 'Nepoznat username')}")
            continue

        text = f"age: {it['age']}; city: {it['city']}; interests: {', '.join(it['interests'])}"
        vec  = model.encode(text).tolist()
        user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, it["username"]))

        batch.add_object(
            properties={
                "username":  it["username"],
                "name":      it["name"],
                "age":       int(it["age"]),
                "city":      it["city"],
                "interests": it["interests"],
            },
            vector=vec,
            uuid=user_uuid,
        )
        usersAddedCount += 1

print(f" Ubačeno {usersAddedCount} od {len(items)} pronađenih korisnika.")
client.close()