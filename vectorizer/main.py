import os
from fastapi import FastAPI, HTTPException, Request, Query
from pydantic import BaseModel
from agent import VectorizerAgent
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Vectorizer Agent")

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "/app/data/chroma_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))

agent = VectorizerAgent(persist_directory=CHROMA_DIR, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

class FileItem(BaseModel):
    path: str
    content: str

class VectorizePayload(BaseModel):
    repo_name: str
    files: list[FileItem]

@app.post("/vectorize")
async def vectorize(payload: VectorizePayload):
    if not payload.files:
        raise HTTPException(status_code=400, detail="No files provided")
    result = agent.vectorize(repo_name=payload.repo_name, files=payload.files)
    return result

@app.get("/search")
async def search(repo_name: str = Query(...), q: str = Query(...), k: int = Query(3)):
    results = agent.search(repo_name=repo_name, query=q, k=k)
    return {"results": results}
