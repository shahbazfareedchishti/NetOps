from core import get_vector_db

def run_test():
    print("[Test] Verifying retrieval from NetOps Brain...")
    
    db = get_vector_db()
    
    if db is None:
        print("[Error] Database not found. Please run ingest.py first.")
        return

    query = "What is the function of a BGP Keepalive message?"
    print(f"[Query]: {query}")

    # Search for the top 2 most relevant chunks
    results = db.similarity_search(query, k=2)

    if not results:
        print("[Test] No results found. The database might be empty or corrupted.")
    else:
        print(f"[Test] Found {len(results)} relevant matches:\n")
        for i, doc in enumerate(results):
            print(f"--- Match {i+1} ---")
            # Displaying a snippet of the content
            print(doc.page_content[:450] + "...")
            print("\n")

if __name__ == "__main__":
    run_test()