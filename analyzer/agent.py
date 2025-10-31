import os
import tempfile
import git
from typing import List, Dict
import requests
from dotenv import load_dotenv

load_dotenv()

class AnalyzerAgent:
    def __init__(self, vectorizer_url: str = "http://vectorizer:8001/vectorize"):
        self.vectorizer_url = vectorizer_url
        self.repos_dir = "/app/repos"
        os.makedirs(self.repos_dir, exist_ok=True)

        # interesting file extensions to extract
        self.file_exts = (".java", ".py", ".js", ".ts", ".yaml", ".yml", ".json", ".md")

    def _clone_repo(self, repo_url: str) -> str:
        """Clone into a temp folder (or reuse if exists)"""
        name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        path = os.path.join(self.repos_dir, name)
        if os.path.exists(path):
            # perform a pull
            try:
                repo = git.Repo(path)
                repo.remotes.origin.pull()
            except Exception:
                # if something goes wrong, reclone
                tmpdir = tempfile.mkdtemp(prefix="repo_")
                git.Repo.clone_from(repo_url, tmpdir)
                path = tmpdir
        else:
            git.Repo.clone_from(repo_url, path)
        return path

    def _collect_files(self, repo_path: str) -> List[Dict]:
        collected = []
        for root, _, files in os.walk(repo_path):
            for f in files:
                if f.lower().endswith(self.file_exts):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read()
                            # lightweight filter: skip very small files
                            if len(content.strip()) > 10:
                                collected.append({"path": os.path.relpath(fp, repo_path), "content": content})
                    except Exception:
                        continue
        return collected

    def push_to_vectorizer(self, payload: dict):
        # basic proxy
        resp = requests.post(self.vectorizer_url, json=payload, timeout=60)
        return {"status": resp.status_code, "resp": resp.json()}

    def analyze_and_push(self, repo_url: str):
        repo_path = self._clone_repo(repo_url)
        files = self._collect_files(repo_path)
        repo_name = os.path.basename(repo_path.rstrip("/"))
        if not files:
            return {"status": "no_files_found", "repo": repo_name}

        payload = {"repo_name": repo_name, "files": files}
        try:
            resp = requests.post(self.vectorizer_url, json=payload, timeout=120)
            if resp.status_code == 200:
                return {"status": "ok", "repo": repo_name, "vectorizer": resp.json()}
            else:
                return {"status": "vectorizer_error", "code": resp.status_code, "body": resp.text}
        except Exception as e:
            return {"status": "error", "error": str(e)}
