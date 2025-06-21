from dotenv import load_dotenv
import boto3
import json
import os
from pydantic import BaseModel
from typing import List

load_dotenv()

AWS_REGION     = os.getenv("AWS_REGION")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")
SECRET_KEY     = os.getenv("SECRET_KEY")

class UserProfile(BaseModel):
    name: str
    age: int
    city: str
    interests: List[str]

field = ['name', 'age', 'city', 'interests']

def fetchAndSaveAllItemVectors():

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table    = dynamodb.Table(DYNAMODB_TABLE) 
    
    items = []
    response = table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
  
    if not items:
        print("Tablica je prazna ili scan nije vratio ništa.")
        return
    
    profiles = []
    for raw in items:
        try:
            profile = UserProfile(**raw)
            profiles.append(profile)
        except Exception as e:
            print(f"Preskačem nevaljani item {raw!r}: {e}")

    if not profiles:
        print("Nije parsiran nijedan validan profil.")
        return

    fields = list(UserProfile.__fields__.keys())

    valuesMatrix = []
    for p in profiles:
        d = p.dict()
        row = []
        for f in fields:
            val = d[f]
            row.append(val)
        valuesMatrix.append(row)

    out = {
        "fields": fields,
        "values": valuesMatrix
    }
    outDir = os.path.join(os.path.dirname(__file__), 'public', 'data')
    os.makedirs(outDir, exist_ok=True)
    out_path = os.path.join(outDir, 'user_profiles_vectors.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Vektori korisničkih profila spremljeni u {out_path}")

if __name__ == "__main__":



    fetchAndSaveAllItemVectors()