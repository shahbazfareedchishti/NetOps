# NetOps

NetOps is a retrieval-augmented AI assistant for network operations topics, currently focused on Border Gateway Protocol (BGP). It ingests technical content from the web, splits it into searchable chunks, stores embeddings in a local Chroma vector database, and answers user questions in a Streamlit chat interface using a Groq-hosted LLM.

This repository is set up for local Python development and for containerized development on Red Hat Enterprise Linux compatible images. The included `Containerfile` uses Red Hat UBI 9 Minimal, while the current host development machine is `Fedora Linux 43 (Workstation Edition)`.

## What This Project Does

- Ingests a technical source URL into a local vector database
- Builds embeddings with `sentence-transformers/all-MiniLM-L6-v2`
- Retrieves relevant chunks with Chroma before answering questions
- Uses Groq + LangChain to generate grounded answers
- Stores Streamlit chat history in SQLite
- Runs as a non-root user inside a RHEL-compatible container

## Current Scope

Right now the app is optimized for BGP questions. The default ingestion target in `ingest.py` is:

- `https://en.wikipedia.org/wiki/Border_Gateway_Protocol`

You can extend it later to support more networking sources and broader NetOps documentation.

## Repository Structure

`app.py`

- Main Streamlit application
- Loads the vector database and Groq chat model
- Expands short queries to improve retrieval quality
- Retrieves context from Chroma before calling the LLM
- Persists conversation history in a local SQLite database

`core.py`

- Shared core utilities for the vector database
- Loads `pysqlite3` first on Linux if available
- Initializes Hugging Face embeddings lazily
- Opens the persistent Chroma store from `./vector_db`

`ingest.py`

- Data ingestion pipeline
- Fetches a URL with `UnstructuredURLLoader`
- Splits content into chunks with overlap
- Clears old vector DB contents before writing new chunks
- Stores embeddings and documents in Chroma

`test_query.py`

- Simple retrieval smoke test
- Verifies that the local vector DB exists and returns relevant chunks

`ui.py`

- Alternate Streamlit UI that expects a FastAPI backend at `http://localhost:8000/chat`
- This backend is not included in the current repository, so `ui.py` should be treated as an alternate or older frontend stub unless you add an API service yourself

`Containerfile`

- RHEL-compatible container build using Red Hat UBI 9 Minimal
- Installs Python 3.11, build dependencies, network tools, and a non-root runtime user
- Installs `pysqlite3-binary` to work around SQLite issues common in minimal UBI images
- Starts the Streamlit app by default

`requirements.txt`

- Python dependencies for LangChain, Chroma, Streamlit, Groq, FastAPI-related packages, and ingestion utilities

## Architecture

The main application flow is:

1. `ingest.py` downloads and chunks source content
2. Chunks are embedded and stored in `./vector_db`
3. `app.py` accepts a user question in Streamlit
4. The app expands the query for better retrieval on acronym-heavy prompts
5. Relevant chunks are fetched from Chroma
6. The retrieved context is sent to Groq through LangChain
7. The answer is displayed and the full chat is saved in SQLite

## Key Implementation Notes

### Retrieval and Query Expansion

`app.py` adds a few query variations for short or definition-style questions. For example, a question containing `BGP` may also be searched as `Border Gateway Protocol`. This improves retrieval for acronym-based prompts.

### Persistent Chat History

The Streamlit app stores sessions and messages in a SQLite database located under a writable runtime directory. The directory is resolved in this order:

1. `NETOPS_DATA_DIR`
2. `./.netops_data`
3. `~/.netops`
4. `/tmp/netops`

This makes the app easier to run both locally and inside containers.

### Vector Database

The vector store is persisted at:

- `./vector_db`

If the directory does not exist, the Streamlit app shows an error and asks you to run ingestion first.

## Requirements

- Python 3.11 recommended
- A Groq API key
- Internet access during ingestion and model/package download steps

## Environment Variables

Create a `.env` file or export the variables in your shell:

```env
GROQ_API_KEY=your_groq_api_key_here
NETOPS_DATA_DIR=/optional/custom/runtime/data/path
```

`GROQ_API_KEY`

- Required for answering questions in `app.py`

`NETOPS_DATA_DIR`

- Optional
- Controls where chat history and runtime state are stored

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Run the ingestion pipeline:

```bash
python ingest.py
```

Start the main app:

```bash
streamlit run app.py
```

Run the retrieval smoke test:

```bash
python test_query.py
```

## Container Development

This project includes a `Containerfile` designed for enterprise-friendly development and deployment.

### Base Image

The container is built from:

```text
registry.access.redhat.com/ubi9/ubi-minimal:latest
```

That means the runtime is based on Red Hat Universal Base Image 9, which is aligned with RHEL-style environments.

### What The Containerfile Configures

- Installs Python 3.11 and pip
- Installs compiler/build tooling such as `gcc`, `gcc-c++`, and `make`
- Installs `iputils` and `shadow-utils`
- Creates a dedicated non-root user: `netopsuser`
- Sets `/app` as the working directory
- Installs Python dependencies from `requirements.txt`
- Installs `pysqlite3-binary` to avoid SQLite compatibility issues on UBI
- Downloads the spaCy model `en_core_web_sm`
- Creates a writable runtime directory for app state
- Declares `/app/vector_db` as a volume
- Starts Streamlit on port `8501`

### Why RHEL And Fedora Matter Here

- The container runtime is RHEL-compatible because it uses UBI 9
- The host development environment is Fedora, which is a natural fit for building and testing UBI-based containers
- This setup makes it easy to develop on Fedora and ship to RHEL-like environments without changing the application code

### Current Host OS

The current machine used for development is:

- `Fedora Linux 43 (Workstation Edition)`
- Kernel: `6.19.9-200.fc43.x86_64`
- Architecture: `x86_64`

### Build And Run With Podman

Fedora commonly uses Podman, so this is the most natural workflow:

```bash
podman build -t netops .
podman run --rm -p 8501:8501 -e GROQ_API_KEY=$GROQ_API_KEY -v $(pwd)/vector_db:/app/vector_db netops
```

### Build And Run With Docker

If you prefer Docker:

```bash
docker build -t netops .
docker run --rm -p 8501:8501 -e GROQ_API_KEY=$GROQ_API_KEY -v $(pwd)/vector_db:/app/vector_db netops
```

## Suggested Workflow

For a clean first run:

1. Install dependencies
2. Set `GROQ_API_KEY`
3. Run `python ingest.py`
4. Start `streamlit run app.py`
5. Ask BGP-related questions in the UI

For container-based work on Fedora:

1. Build the image with Podman or Docker
2. Mount `./vector_db` into the container
3. Expose port `8501`
4. Pass `GROQ_API_KEY` into the container

## Known Gaps And Notes

- The current ingestion script targets one default BGP source URL
- `ui.py` expects a FastAPI backend, but no FastAPI server file exists in this repository right now
- `requirements.txt` includes `fastapi`, `uvicorn`, and `pydantic`, which suggests API work may be planned or was partially started
- `app.py` is the real working entry point today
- The container starts the Streamlit UI directly, not a FastAPI service

## Future Improvement Ideas

- Support multiple source URLs and document sets
- Add metadata and citation display for retrieved chunks
- Add a real FastAPI backend if API-based architecture is needed
- Separate ingestion, retrieval, and UI concerns into clearer modules
- Add automated tests beyond the simple retrieval smoke test

## Summary

This codebase is a compact BGP-focused NetOps assistant built with Streamlit, LangChain, Chroma, Hugging Face embeddings, and Groq. It supports local development, persists retrieval data and chat history, and is packaged for RHEL-style container environments through a UBI 9 `Containerfile`. Development is currently being done on Fedora Linux 43, which pairs well with the included container workflow.
