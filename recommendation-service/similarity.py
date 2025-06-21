import json
from sentence_transformers import SentenceTransformer
from typing import Any, List

with open('public/data/user_profiles_vectors.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fields: List[str] = data['fields']       
values_matrix: List[List[Any]] = data['values']

def profile_to_text(fields: List[str], values: List[Any]) -> str:
    parts = []
    for field, val in zip(fields, values):
        if isinstance(val, list):
            val_str = ', '.join(val)
        else:
            val_str = str(val)
        parts.append(f"{field}: {val_str}")
    return "; ".join(parts)

sentences = [profile_to_text(fields, row) for row in values_matrix]

model = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(sentences)    

from sklearn.metrics.pairwise import cosine_similarity
similarities = cosine_similarity(embeddings, embeddings)

print(f"Encoded {len(sentences)} profiles into shape {embeddings.shape}")
print("Similarity matrix:")
print(similarities)