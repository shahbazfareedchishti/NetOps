import streamlit as st
from core import get_vector_db
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import os
import uuid
import sqlite3
from pathlib import Path
import tempfile
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def resolve_data_dir():
    """
    Chooses a writable directory for runtime data.
    """
    candidates = []
    env_dir = os.getenv("NETOPS_DATA_DIR")

    if env_dir:
        candidates.append(Path(env_dir).expanduser())

    candidates.extend([
        Path(__file__).resolve().parent / ".netops_data",
        Path.home() / ".netops",
        Path(tempfile.gettempdir()) / "netops",
    ])

    last_error = None

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.touch(exist_ok=True)
            probe.unlink()
            return candidate
        except OSError as exc:
            last_error = exc

    raise RuntimeError("No writable directory is available for chat history.") from last_error


DATA_DIR = resolve_data_dir()
DB_PATH = DATA_DIR / "chat_history.db"


def connect_history_db():
    return sqlite3.connect(str(DB_PATH), timeout=30)


def expand_search_queries(question):
    """
    Adds a few query variants so short acronym questions retrieve stronger intro chunks.
    """
    normalized = question.strip()
    lowered = normalized.lower()
    queries = [normalized]

    if "bgp" in lowered and "border gateway protocol" not in lowered:
        queries.append(normalized.replace("BGP", "Border Gateway Protocol").replace("bgp", "Border Gateway Protocol"))
        queries.append("Border Gateway Protocol definition purpose routing")

    if lowered.startswith(("what is", "explain", "define", "overview of")):
        queries.append(f"{normalized} definition overview")

    unique_queries = []
    seen = set()
    for query in queries:
        cleaned = query.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_queries.append(cleaned)

    return unique_queries


def retrieve_context(db, question, max_chunks=6):
    """
    Retrieves a broader, de-duplicated context set for the LLM.
    """
    collected_docs = []
    seen_content = set()

    for query in expand_search_queries(question):
        try:
            docs = db.max_marginal_relevance_search(query, k=4, fetch_k=12)
        except Exception:
            docs = db.similarity_search(query, k=4)

        for doc in docs:
            content = doc.page_content.strip()
            if not content or content in seen_content:
                continue

            seen_content.add(content)
            collected_docs.append(doc)

            if len(collected_docs) >= max_chunks:
                return collected_docs

    return collected_docs

def init_history_db():
    conn = connect_history_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_message(session_id, role, content):
    conn = connect_history_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Ensure session row exists
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?)",
        (session_id, now)
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, now)
    )
    conn.commit()
    conn.close()

def load_session_messages(session_id):
    conn = connect_history_db()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in rows]

def get_all_sessions():
    conn = connect_history_db()
    rows = conn.execute(
        "SELECT s.session_id, s.created_at, m.content FROM sessions s "
        "LEFT JOIN messages m ON s.session_id = m.session_id AND m.id = ("
        "  SELECT MIN(id) FROM messages WHERE session_id = s.session_id AND role='user'"
        ") ORDER BY s.created_at DESC"
    ).fetchall()
    conn.close()
    return rows  # (session_id, created_at, first_user_message)

def delete_all_sessions():
    conn = connect_history_db()
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()

init_history_db()

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="NetOps Co-Pilot", layout="wide", page_icon="📡")

# ── Load Brain (cached) ───────────────────────────────────────────────────────
@st.cache_resource
def init_brain():
    db = get_vector_db()
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", groq_api_key=os.getenv("GROQ_API_KEY"))
    prompt = ChatPromptTemplate.from_template("""
    You are an expert Network Operations AI Co-Pilot.
    Answer using ONLY the following technical context.
    Give the most helpful direct answer you can from the retrieved material.
    For definition or overview questions, start with a concise 2-4 sentence explanation.
    If the context supports a useful answer, do not add disclaimers like "the context is not comprehensive enough."
    Only say information is missing when the retrieved context cannot answer the user's core question.
    Prefer a confident summary over a hesitant refusal when the context contains the main facts.

    Context:
    {context}

    Question:
    {question}
    """)
    return db, llm, prompt

db, llm, prompt = init_brain()

if not db:
    st.error("Vector database is offline or empty. Run ingest.py first.")
    st.stop()

# ── Session State ─────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Sidebar: Chat History ─────────────────────────────────────────────────────
with st.sidebar:
    st.title("📡 NetOps Co-Pilot")
    st.markdown("---")

    if st.button("New Conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.subheader("Past Conversations")
    sessions = get_all_sessions()
    if not sessions:
        st.caption("No history yet.")
    else:
        for sid, created_at, first_msg in sessions:
            label = first_msg[:40] + "..." if first_msg and len(first_msg) > 40 else (first_msg or "Empty session")
            caption = created_at[:16] if created_at else ""
            if st.button(f"💬 {label}", key=sid, help=caption, use_container_width=True):
                st.session_state.session_id = sid
                st.session_state.messages = load_session_messages(sid)
                st.rerun()

    st.markdown("---")
    if st.button("🗑️ Clear All History", use_container_width=True):
        delete_all_sessions()
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

# ── Main Chat UI ──────────────────────────────────────────────────────────────
st.title("NetOps AI Co-Pilot")
st.caption("Ask me anything about Border Gateway Protocol (BGP).")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_question := st.chat_input("E.g., What is a BGP Keepalive message?"):
    st.chat_message("user").markdown(user_question)
    st.session_state.messages.append({"role": "user", "content": user_question})
    save_message(st.session_state.session_id, "user", user_question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing network documentation..."):
            results = retrieve_context(db, user_question, max_chunks=6)
            context_text = "\n\n".join([doc.page_content for doc in results])

            chain = prompt | llm
            response = chain.invoke({
                "context": context_text,
                "question": user_question
            })

            answer = response.content
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            save_message(st.session_state.session_id, "assistant", answer)
