import os
import shutil
from core import DB_DIR, get_embeddings
from langchain_community.document_loaders import UnstructuredURLLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

def ingest_data(url):
    print(f"[Ingest] Starting ingestion for: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    loader = UnstructuredURLLoader(urls=[url], headers=headers)
    docs = loader.load()

    # 'docs' is a list of Document objects.
    if not docs or len(docs[0].page_content) < 500:
        print("[Error] Failed to retrieve sufficient content or blocked by website.")
        return

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_documents(docs)

    print(f"[Ingest] Successfully split into {len(chunks)} chunks.")
    
    # Clean old data to prevent pollution from previous failed runs
    if os.path.exists(DB_DIR):
        for item in os.listdir(DB_DIR):
            item_path = os.path.join(DB_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
        print(f"[Ingest] Cleared old database contents at {DB_DIR}")

    print(f"[Ingest] Storing chunks in {DB_DIR}...")
    Chroma.from_documents(
        documents=chunks, 
        embedding=get_embeddings(), 
        persist_directory=DB_DIR
    )
    print("[Ingest] Process complete. Vector database updated.")

if __name__ == "__main__":
    target = "https://en.wikipedia.org/wiki/Border_Gateway_Protocol"
    ingest_data(target)
