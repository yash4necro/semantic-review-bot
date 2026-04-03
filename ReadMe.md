# Semantic Code Review Bot

A CLI tool that indexes a codebase using vector embeddings, then uses semantic similarity to surface relevant past code as context for LLM-generated code reviews.

> **Phase 1 capstone project** — part of a 40-week AI/ML learning roadmap.

---

## How it works

```
Your codebase
      ↓
[ Indexer ]   Parse every function via AST → embed → store in ChromaDB
      ↓
New PR diff comes in
      ↓
[ Retriever ] Embed the diff → find semantically similar past functions
      ↓
[ Reviewer ]  Send (diff + context) → Groq LLM → code review output
      ↓
CLI output
```

---

## Stack

| Layer | Tool |
|---|---|
| Language | Python 3.10+ |
| Embeddings | `sentence-transformers` — runs locally, no API key |
| Embedding model | `all-MiniLM-L6-v2` (~90MB, downloads once) |
| Vector DB | `ChromaDB` — runs on disk, no server needed |
| LLM inference | `Groq` API (fast, generous free tier) |
| Environment | WSL2 / Linux |

---

## Project structure

```
semantic-review-bot/
├── src/
│   ├── indexer.py      # Reads repo, chunks by function, embeds, stores in ChromaDB
│   ├── retriever.py    # Takes a query, returns similar functions from ChromaDB
│   ├── reviewer.py     # Assembles prompt + context, calls Groq, returns review
│   └── main.py         # CLI entry point — wires everything together
├── data/
│   └── chroma/         # ChromaDB persisted vector store (auto-created, gitignored)
├── .env                # Your API keys (never commit this)
├── .gitignore
└── README.md
```

---

## Setup from scratch

### 1. Clone / navigate to the project

```bash
# If on WSL, keep everything in Linux-native filesystem (not /mnt/c)
cd ~
# mkdir semantic-review-bot && cd semantic-review-bot  # if starting fresh
cd semantic-review-bot
```

### 2. Create and activate the virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

> You'll need to re-run `source venv/bin/activate` every time you open a new terminal.  
> Your prompt should show `(venv)` when it's active.

### 3. Install dependencies

```bash
pip install groq chromadb gitpython python-dotenv rich sentence-transformers
```

### 4. Add your API key

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get a free key at: https://console.groq.com

### 5. Verify setup

```bash
python3 -c "import chromadb, groq, sentence_transformers; print('All good')"
```

---

## Usage

### Index a codebase

Point the indexer at any Python repo. It will chunk every function/class using AST parsing and store embeddings in ChromaDB.

```bash
python3 src/indexer.py /path/to/repo
```

**Example — index Flask:**
```bash
git clone https://github.com/pallets/flask.git ~/flask-test
python3 src/indexer.py ~/flask-test
# Expected: ~1300+ chunks indexed
```

> Re-running the indexer is safe — it skips already-indexed files using content hashing.  
> To re-index from scratch: `rm -rf data/chroma`

### Test retrieval

```bash
python3 src/retriever.py "handle HTTP routing and URL rules"
python3 src/retriever.py "raise exception when request fails"
```

**Distance guide:**
```
✅  < 0.5   very similar
🟡  0.5–0.7  related
🔴  > 0.7   loosely related / noise
```

### Run a code review *(coming soon)*

```bash
python3 src/main.py --diff path/to/file.py
# or pipe a diff directly:
git diff HEAD~1 | python3 src/main.py
```

---

## Module status

| Module | What it does | Status |
|---|---|---|
| `indexer.py` | AST-chunk repo → embed → store in ChromaDB | ✅ Done |
| `retriever.py` | Embed query → find similar functions | ✅ Done |
| `reviewer.py` | Prompt assembly + Groq LLM call | ⬜ Pending |
| `main.py` | CLI entry point, wires all three | ⬜ Pending |

---

## Key decisions & lessons learned

**Why function-level chunking?**  
Embedding entire files produces blurry, averaged vectors — retrieval quality is poor. Chunking by individual function gives focused embeddings that match queries accurately. Flask went from 77 file-chunks to 1,346 function-chunks, and distances dropped from ~0.73 to ~0.56.

**Why local embeddings instead of an API?**  
Groq doesn't support embedding models (LLM inference only). `sentence-transformers` running locally is faster, free, works offline, and has no rate limits — better for the indexing use case anyway.

**Why ChromaDB?**  
Zero setup. Runs entirely on disk as a local file store. No Docker, no account, no server. Perfect for a project like this. In production you'd swap it for pgvector or Pinecone.

**WSL2 path gotcha:**  
`~` in WSL expands to `/home/yourusername`, not `C:\Users\yourname`. Keep all project files in `/home/...` (WSL native), not `/mnt/c/...`. The Windows filesystem bridge is slower and causes subtle path bugs.

---

## Troubleshooting

**`Found 0 files to index`**
- Check your path: run `ls /your/path` to confirm it exists
- On WSL, avoid `~/Users/...` — use `/home/yourusername/...` or `/mnt/c/Users/...`
- The indexer only picks up `.py`, `.ts`, `.js` by default

**`venv not found` / missing imports after reopening terminal**
- Your venv deactivated. Run: `source venv/bin/activate`

**`model not found` error from Groq**
- Groq does not support embedding models — use `sentence-transformers` locally for embeddings
- Groq is only used for LLM inference (the Reviewer step)

**ChromaDB returns wrong/unrelated results**
- Check your chunk count: if it's under 100, chunking may have fallen back to file-level
- Try clearing and re-indexing: `rm -rf data/chroma && python3 src/indexer.py /path/to/repo`

---

*Last updated: Indexer ✅ · Retriever ✅ · Reviewer ⬜ · CLI ⬜*