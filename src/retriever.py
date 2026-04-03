import os
import chromadb
from sentence_transformers import SentenceTransformer

# Same model as indexer — this is non-negotiable
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path="./data/chroma")
collection = chroma_client.get_collection("codebase")


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    Given any code string or plain English description,
    return the top_k most similar functions from the indexed codebase.
    """
    # Embed the query using the same model we used during indexing
    query_embedding = embedding_model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    # Reshape ChromaDB's response into something clean to work with
    matches = []
    for i in range(len(results["ids"][0])):
        matches.append({
            "id":       results["ids"][0][i],
            "filepath": results["metadatas"][0][i].get("filepath", ""),
            "name":     results["metadatas"][0][i].get("name", ""),
            "type":     results["metadatas"][0][i].get("type", ""),
            "distance": round(results["distances"][0][i], 4),
            "content":  results["documents"][0][i]
        })

    # Sort by distance ascending — most similar first
    matches.sort(key=lambda x: x["distance"])
    return matches


def format_context(matches: list[dict], max_chars: int = 3000) -> str:
    """
    Format retrieved matches into a context block for the LLM prompt.
    Respects a character budget so we don't blow the context window.
    """
    context_parts = []
    total_chars = 0

    for match in matches:
        # Skip weak matches — not worth adding noise to the prompt
        if match["distance"] > 0.7:
            continue

        snippet = (
            f"--- Similar code (distance: {match['distance']}) ---\n"
            f"File: {match['filepath']}"
            + (f" | Function: {match['name']}" if match['name'] else "")
            + f"\n\n{match['content']}\n"
        )

        if total_chars + len(snippet) > max_chars:
            break

        context_parts.append(snippet)
        total_chars += len(snippet)

    if not context_parts:
        return "No similar code found in the codebase."

    return "\n".join(context_parts)


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "handle HTTP routing"

    print(f'\nQuery: "{query}"')
    print("=" * 60)

    matches = retrieve(query, top_k=5)
    for m in matches:
        status = "✅" if m["distance"] < 0.5 else "🟡" if m["distance"] < 0.7 else "🔴"
        print(f'{status}  [{m["distance"]}]  {m["filepath"]}  →  {m["name"]}()')

    print("\n--- Formatted context block (what the LLM will see) ---\n")
    print(format_context(matches))