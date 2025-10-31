import os
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
import chromadb
from chromadb.config import Settings

# Pydantic models not required inside agent file (we already validated at FastAPI layer)

class VectorizerAgent:
    def __init__(self, persist_directory: str = "/app/data/chroma_db", chunk_size: int = 500, chunk_overlap: int = 50):
        self.persist_directory = persist_directory
        os.makedirs(self.persist_directory, exist_ok=True)

        # Chromadb client (using default local persistence)
        self.client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=self.persist_directory))

        # Sentence transformer model for embeddings (local)
        self.embed_model = SentenceTransformer("all-MiniLM-L6-v2")

        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def _chunk_files(self, files: List[Dict]) -> List[Dict]:
        """Return list of chunks with metadata"""
        chunks = []
        for f in files:
            text = f.get("content", "")
            path = f.get("path", "unknown")
            # Split into chunks
            pieces = self.splitter.split_text(text)
            for i, p in enumerate(pieces):
                chunks.append({
                    "text": p,
                    "metadata": {"path": path, "chunk_index": i}
                })
        return chunks

    def vectorize(self, repo_name: str, files: List[Dict]):
        # Prepare collection name unique per repo
        collection_name = repo_name.replace("/", "_").replace(".", "_")

        # Create / get collection
        if collection_name in [c.name for c in self.client.list_collections()]:
            collection = self.client.get_collection(name=collection_name)
        else:
            collection = self.client.create_collection(name=collection_name)

        # Chunk files
        chunks = self._chunk_files(files)
        if not chunks:
            return {"status": "no_chunks"}

        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        ids = [f"{collection_name}_{i}" for i in range(len(texts))]

        # Create embeddings (numpy arrays)
        embeddings = self.embed_model.encode(texts, show_progress_bar=False)
        # Chromadb expects list of vectors
        embeddings_list = [list(map(float, vec)) for vec in embeddings]

        # Upsert into collection
        collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings_list)

        # Persist
        self.client.persist()

        return {"status": "success", "chunks_added": len(texts)}

    def search(self, repo_name: str, query: str, k: int = 3):
        collection_name = repo_name.replace("/", "_").replace(".", "_")
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception:
            return []

        # embed the query
        q_emb = self.embed_model.encode([query])[0]
        q_emb_list = list(map(float, q_emb))
        results = collection.query(query_embeddings=[q_emb_list], n_results=k, include=["documents", "metadatas", "distances"])
        out = []
        for i in range(len(results["documents"][0])):
            out.append({
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": float(results["distances"][0][i])
            })
        return out
