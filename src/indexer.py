import os
import hashlib
from pathlib import Path
import chromadb
import ast
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
from sentence_transformers import SentenceTransformer

# --- Clients ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Local embedding model — no API key, runs on your machine
# "all-MiniLM-L6-v2" is small, fast, and great for code similarity
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path="./data/chroma")
collection = chroma_client.get_or_create_collection(
    name="codebase",
    metadata={"hnsw:space": "cosine"}
)

def embed(text: str) -> list[float]:
    """
    Embed text locally using sentence-transformers.
    No API call, no cost, no rate limits.
    """
    return embedding_model.encode(text[:4000]).tolist()

# --- Chunking ---
def chunk_file(filepath: str, content: str) -> list[dict]:
    """
    For Python files: extract individual functions and classes as chunks.
    For other files: fall back to the whole file.
    """
    chunks = []

    if filepath.endswith(".py"):
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                # Extract functions and classes individually
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Get the source lines for just this function/class
                    start = node.lineno - 1
                    end = node.end_lineno
                    snippet = "\n".join(content.splitlines()[start:end])

                    if len(snippet.strip()) < 50:  # skip trivial ones
                        continue

                    chunk_id = hashlib.md5(
                        f"{filepath}:{node.name}:{snippet}".encode()
                    ).hexdigest()

                    chunks.append({
                        "id": chunk_id,
                        "text": f"File: {filepath}\nFunction: {node.name}\n\n{snippet}",
                        "metadata": {
                            "filepath": filepath,
                            "name": node.name,
                            "type": type(node).__name__
                        }
                    })
        except SyntaxError:
            pass  # fall through to whole-file fallback

    # Fallback: whole file (for non-Python or unparseable files)
    if not chunks:
        chunks.append({
            "id": hashlib.md5(f"{filepath}{content}".encode()).hexdigest(),
            "text": f"File: {filepath}\n\n{content}",
            "metadata": {"filepath": filepath, "name": "", "type": "file"}
        })

    return chunks

# --- Indexer ---
def index_directory(path: str, extensions: list[str] = [".py", ".ts", ".js"]):
    """
    Walk a directory, embed every matching file, store in ChromaDB.
    """
    root = Path(path)
    files = [f for f in root.rglob("*") if f.suffix in extensions]
    
    print(f"Found {len(files)} files to index...")

    for file in files:
        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) < 50:   # skip empty files
                continue

            chunks = chunk_file(str(file.relative_to(root)), content)

            for chunk in chunks:
                # Check if already indexed (avoid re-embedding unchanged files)
                existing = collection.get(ids=[chunk["id"]])
                if existing["ids"]:
                    continue

                embedding = embed(chunk["text"])

                collection.add(
                    ids=[chunk["id"]],
                    embeddings=[embedding],
                    documents=[chunk["text"]],
                    metadatas=[chunk["metadata"]]
                )
                print(f"  ✓ Indexed {chunk['metadata']['filepath']}")

        except Exception as e:
            print(f"  ✗ Skipped {file}: {e}")

    print(f"\nDone. Collection has {collection.count()} chunks.")

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    index_directory(path)

def get_collection_stats():
    count = collection.count()
    return {"total_chunks": count}


def search_by_filepath(filepath: str):
    results = collection.get(where={"filepath": filepath})
    return results
