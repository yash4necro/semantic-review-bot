# Semantic Code Review Bot

A CLI tool that indexes a codebase using vector embeddings, then retrieves semantically similar past functions as context for LLM-generated code reviews.

Instead of sending a raw diff to an LLM, this bot first searches the codebase for the most similar code your team has written before — and grounds the review in that real context.

> **Phase 1 capstone project** — part of a 40-week AI/ML learning roadmap.

---

## How it works

```
Your codebase
      ↓
[ Indexer ]    Parse every function via AST → embed locally → store in ChromaDB
      ↓
New diff / PR comes in
      ↓
[ Retriever ]  Embed the diff → cosine search → filter by distance threshold
      ↓
[ Reviewer ]   Inject (diff + similar context) → Groq LLM → streamed review
      ↓
Terminal output
```

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.10+ | |
| Embeddings | `sentence-transformers` | Runs locally — no API key, no cost, no rate limits |
| Embedding model | `all-MiniLM-L6-v2` | ~90MB, downloads once, fast inference |
| Vector DB | `ChromaDB` | Runs fully on disk, zero setup |
| LLM inference | Groq API (`llama-3.3-70b-versatile`) | Fast, generous free tier |
| Environment | WSL2 / Linux | |

---

## Project structure

```
semantic-review-bot/
├── src/
│   ├── indexer.py      # Reads repo, chunks by function (AST), embeds, stores in ChromaDB
│   ├── retriever.py    # Embeds query, cosine search, formats context block for LLM
│   ├── reviewer.py     # Assembles prompt + context, streams Groq LLM review
│   └── main.py         # CLI entry point — file flag + git diff pipe support
├── data/
│   └── chroma/         # ChromaDB persisted vector store (auto-created, gitignored)
├── .env                # API keys — never commit this
├── .gitignore
└── README.md
```

---

## Setup from scratch

### 1. Navigate to the project

```bash
# Keep everything in WSL native filesystem — not /mnt/c
cd ~/semantic-review-bot
```

### 2. Create and activate the virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

> **Important:** Run `source venv/bin/activate` every time you open a new terminal.
> Your prompt should show `(venv)` when active.

### 3. Install dependencies

```bash
pip install groq chromadb gitpython python-dotenv rich sentence-transformers
```

### 4. Add your Groq API key

Create `.env` in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get a free key at: https://console.groq.com

### 5. Verify everything installed correctly

```bash
python3 -c "import chromadb, groq, sentence_transformers; print('All good')"
```

---

## Usage

### Step 1 — Index a codebase

Point the indexer at any Python repo. It parses every function and class using Python's `ast` module, embeds each one individually, and stores them in ChromaDB.

```bash
python3 src/indexer.py /path/to/repo
```

**Example — index Flask:**
```bash
git clone https://github.com/pallets/flask.git ~/flask-test
python3 src/indexer.py ~/flask-test
# Expected output: ~1,300+ chunks indexed
```

> Re-running the indexer is safe — it skips already-indexed chunks using content hashing.
> To re-index from scratch: `rm -rf data/chroma`

---

### Step 2 — Test retrieval (optional sanity check)

```bash
python3 src/retriever.py "handle HTTP routing and URL rules"
python3 src/retriever.py "raise exception when request fails"
python3 src/retriever.py "database connection pooling"
```

**Distance guide:**
```
✅  < 0.5    very similar — strong context match
🟡  0.5–0.7  related — useful context
🔴  > 0.7    weak match — filtered out before reaching the LLM
```

---

### Step 3 — Run a code review

```bash
# Review a specific file
python3 src/main.py --diff path/to/yourfile.py

# Pipe a git diff (most useful workflow)
git diff | python3 src/main.py

# Review your last commit
git show | python3 src/main.py

# Review changes since last commit
git diff HEAD~1 | python3 src/main.py
```

---

## Module status

| Module | What it does | Status |
|---|---|---|
| `indexer.py` | AST-chunk repo → embed locally → store in ChromaDB | ✅ Complete |
| `retriever.py` | Embed query → cosine search → filter + format context | ✅ Complete |
| `reviewer.py` | Prompt assembly + context injection + streaming Groq review | ✅ Complete |
| `main.py` | CLI: `--diff` file flag + git diff stdin pipe | ✅ Complete |

---

## Key design decisions

**Function-level chunking over file-level**
Embedding entire files produces blurry, averaged vectors — retrieval quality is poor. Chunking by individual function gives focused embeddings. On Flask: 77 file-chunks → 1,346 function-chunks. Distances dropped from ~0.73 to ~0.56 on the same query. Better chunking beat switching to a fancier model.

**Local embeddings over an API**
Groq doesn't support embedding models (LLM inference only). `sentence-transformers` locally is faster for bulk indexing, free, works offline, and has no rate limits. Use APIs for what they're good at — inference at scale. Use local models for what they're good at — bulk, offline, cost-sensitive workloads.

**Cosine similarity over euclidean distance**
We care about the *direction* of a vector (its meaning), not its length. Cosine similarity captures this. A short and a long function doing the same thing score as similar under cosine — they wouldn't under euclidean distance.

**Streaming LLM output**
`stream=True` on the Groq call means output starts printing almost immediately, token by token. Without it, you wait 8–10 seconds staring at a blank terminal. Always stream in user-facing applications.

**Distance threshold at 0.7**
Anything above 0.7 is filtered out before reaching the LLM. It's noise, not signal. The context window is limited — every weak match injected is space wasted.

---

## Troubleshooting

**`Found 0 files to index`**
- Confirm the path exists: `ls /your/path`
- On WSL: avoid `~/Users/...` — use `/home/yourusername/...` instead
- The indexer only picks up `.py`, `.ts`, `.js` by default — check your repo has these

**`venv` not found / missing imports after reopening terminal**
- Your venv deactivated. Run: `source venv/bin/activate`
- Your prompt should show `(venv)` when active

**`model not found` error from Groq**
- Groq does not support embedding models — that's expected
- `sentence-transformers` handles all embeddings locally
- Groq is only used for LLM inference in `reviewer.py`

**Retrieval returning wrong or unrelated results**
- Check your chunk count: `python3 -c "import chromadb; c = chromadb.PersistentClient('./data/chroma'); print(c.get_collection('codebase').count())"`
- If under 200 for a medium repo, chunking fell back to file-level — re-index: `rm -rf data/chroma && python3 src/indexer.py /path/to/repo`

**`No input received` when piping git diff**
- Your repo may not have a baseline commit yet — run `git add . && git commit -m "initial"` first
- Then make a change and run `git diff | python3 src/main.py`

**HuggingFace / BertModel warnings on every run**
- These are harmless. The HF warning is about rate limits for unauthenticated downloads (model is already cached locally). The BertModel warning is an architectural mismatch that doesn't affect output. Ignore both.

---

*Last updated: All four modules complete · Phase 1 capstone shipped*