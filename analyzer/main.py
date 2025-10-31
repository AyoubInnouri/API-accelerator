import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import AnalyzerAgent
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Analyzer Agent")

VECTORIZER_HOST = os.getenv("VECTORIZER_HOST", "http://vectorizer:8001")
VECTORIZER_API = os.getenv("VECTORIZER_API", "/vectorize")

agent = AnalyzerAgent(vectorizer_url=VECTORIZER_HOST + VECTORIZER_API)

class AnalyzePayload(BaseModel):
    repo_url: str

@app.post("/analyze")
def analyze(payload: AnalyzePayload):
    if not payload.repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")
    res = agent.analyze_and_push(repo_url=payload.repo_url)
    return res

@app.post("/push_to_vectorizer")
def push_to_vectorizer(payload: dict):
    # Direct push helper: {"repo_name": "...", "files": [{"path":"", "content":""}, ...]}
    return agent.push_to_vectorizer(payload)
