import sys

try:
    import pysqlite3 as sqlite3  # type: ignore
except ModuleNotFoundError:
    sqlite3 = None
else:
    sys.modules["sqlite3"] = sqlite3

import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configuration
DB_DIR = "./vector_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

print("[Core] NetOps brain module loaded.")

_embeddings = None


def get_embeddings():
    """
    Lazily loads the embedding model so imports stay lightweight and resilient.
    """
    global _embeddings

    if _embeddings is None:
        print("[Core] Loading embedding model...")
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        print("[Core] Embedding model ready.")

    return _embeddings

def get_vector_db():
    """
    Returns the existing ChromaDB instance if it exists.
    """
    if not os.path.exists(DB_DIR):
        print("[Core] Warning: Vector database directory not found.")
        return None
    
    return Chroma(
        persist_directory=DB_DIR, 
        embedding_function=get_embeddings()
    )

print("[Core] Brain Ready.")
