import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "chat_history.db"
SYSTEM_PROMPT = (
    "You are a helpful, thoughtful AI assistant. Reply in the same language as "
    "the user's latest message unless they ask for another language."
)

load_dotenv(BASE_DIR / ".env")

st.set_page_config(
    page_title="Astra AI Chat",
    page_icon="✦",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root { color-scheme: dark; }
      .stApp {
        background: radial-gradient(ellipse at 50% -18%, #20264a 0, #10131d 42%, #0b0d13 100%);
        color: #edf0fa;
      }
      [data-testid="stHeader"] { background: transparent; }
      [data-testid="stSidebar"] {
        background: rgba(13, 16, 25, .96);
        border-right: 1px solid rgba(255,255,255,.08);
      }
      [data-testid="stChatMessage"] {
        background: rgba(255,255,255,.035);
        border: 1px solid rgba(255,255,255,.055);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        margin-bottom: .75rem;
      }
      [data-testid="stChatInput"] {
        border: 1px solid rgba(151, 139, 255, .35);
        border-radius: 16px;
      }
      .hero { padding: 1.6rem 0 .8rem; text-align: center; }
      .hero h1 {
        font-size: 2.3rem;
        letter-spacing: -.06em;
        margin: 0;
        background: linear-gradient(100deg, #f6f4ff, #aaa1ff 65%, #78d7e9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .hero p { color: #969bad; margin-top: .45rem; }
      .stButton > button {
        border-radius: 10px;
        border-color: rgba(255,255,255,.1);
        background: rgba(255,255,255,.045);
      }
      .stButton > button:hover {
        border-color: #9287ff;
        color: #c9c3ff;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(owner_id):
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                owner_id TEXT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                    ON DELETE CASCADE
            );
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(conversations)")
        }
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE conversations ADD COLUMN owner_id TEXT")
        connection.execute(
            "UPDATE conversations SET owner_id = ? WHERE owner_id IS NULL",
            (owner_id,),
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_owner_updated "
            "ON conversations (owner_id, updated_at DESC)"
        )


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_conversation(owner_id):
    conversation_id = str(uuid.uuid4())
    timestamp = now_utc()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO conversations (id, owner_id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, owner_id, "Nayi chat", timestamp, timestamp),
        )
    return conversation_id


def list_conversations(owner_id):
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, title FROM conversations WHERE owner_id = ? "
            "ORDER BY updated_at DESC",
            (owner_id,),
        ).fetchall()


def get_messages(conversation_id, owner_id):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT messages.role, messages.content
            FROM messages
            JOIN conversations ON conversations.id = messages.conversation_id
            WHERE messages.conversation_id = ? AND conversations.owner_id = ?
            ORDER BY messages.id
            """,
            (conversation_id, owner_id),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def save_message(conversation_id, owner_id, role, content):
    timestamp = now_utc()
    with get_connection() as connection:
        owned_conversation = connection.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND owner_id = ?",
            (conversation_id, owner_id),
        ).fetchone()
        if owned_conversation is None:
            raise RuntimeError("Yeh chat is browser session ki nahi hai.")
        connection.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, timestamp),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ? AND owner_id = ?",
            (timestamp, conversation_id, owner_id),
        )
        if role == "user":
            message_count = connection.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()[0]
        else:
            message_count = 0
        if role == "user" and message_count == 1:
            connection.execute(
                "UPDATE conversations SET title = ? WHERE id = ? AND owner_id = ?",
                (
                    content.replace("\n", " ").strip()[:42] or "Nayi chat",
                    conversation_id,
                    owner_id,
                ),
            )


def delete_conversation(conversation_id, owner_id):
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM conversations WHERE id = ? AND owner_id = ?",
            (conversation_id, owner_id),
        )


def stream_gemini(messages, api_key, model):
    from google import genai

    client = genai.Client(api_key=api_key)
    contents = [
        {
            "role": "user" if message["role"] == "user" else "model",
            "parts": [{"text": message["content"]}],
        }
        for message in messages
    ]
    response = client.models.generate_content_stream(
        model=model,
        contents=contents,
        config={"system_instruction": SYSTEM_PROMPT},
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


def stream_groq(messages, api_key, model):
    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *[
                {"role": message["role"], "content": message["content"]}
                for message in messages
            ],
        ],
        stream=True,
    )
    for chunk in response:
        text = chunk.choices[0].delta.content
        if text:
            yield text


def get_reply_stream(messages):
    provider = get_setting("CHAT_PROVIDER", "gemini").lower()
    if provider == "gemini":
        api_key = get_setting("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY ko `.env` ya Streamlit Cloud ke Secrets mein set karein."
            )
        model = get_setting("GEMINI_MODEL", "gemini-2.5-flash")
        return stream_gemini(messages, api_key, model)
    if provider == "groq":
        api_key = get_setting("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY ko `.env` ya Streamlit Cloud ke Secrets mein set karein."
            )
        model = get_setting("GROQ_MODEL", "llama-3.3-70b-versatile")
        return stream_groq(messages, api_key, model)
    raise RuntimeError("CHAT_PROVIDER ki value `gemini` ya `groq` honi chahiye.")


def get_setting(name, default=""):
    environment_value = os.getenv(name)
    if environment_value and environment_value.strip():
        return environment_value.strip()
    try:
        secret_value = st.secrets.get(name, default)
    except StreamlitSecretNotFoundError:
        secret_value = default
    return str(secret_value).strip()


if "owner_id" not in st.session_state:
    st.session_state.owner_id = str(uuid.uuid4())

owner_id = st.session_state.owner_id
initialize_database(owner_id)

if "conversation_id" not in st.session_state:
    existing = list_conversations(owner_id)
    st.session_state.conversation_id = (
        existing[0]["id"] if existing else create_conversation(owner_id)
    )

with st.sidebar:
    st.markdown("## ✦ Astra AI")
    st.caption("Aapki chats is browser session tak private hain.")
    if st.button("＋  Nayi chat", use_container_width=True):
        st.session_state.conversation_id = create_conversation(owner_id)
        st.rerun()

    st.markdown("---")
    st.markdown("**Recent chats**")
    conversations = list_conversations(owner_id)
    for conversation in conversations:
        label = conversation["title"][:36]
        if st.button(
            label,
            key=f"conversation-{conversation['id']}",
            use_container_width=True,
            type="primary"
            if conversation["id"] == st.session_state.conversation_id
            else "secondary",
        ):
            st.session_state.conversation_id = conversation["id"]
            st.rerun()

    st.markdown("---")
    if st.button("🗑️  Is chat ko delete karein", use_container_width=True):
        delete_conversation(st.session_state.conversation_id, owner_id)
        conversations = list_conversations(owner_id)
        st.session_state.conversation_id = (
            conversations[0]["id"] if conversations else create_conversation(owner_id)
        )
        st.rerun()

st.markdown(
    '<div class="hero"><h1>✦ Astra AI</h1>'
    "<p>Aapka personal AI assistant — kuch bhi poochhein.</p></div>",
    unsafe_allow_html=True,
)

chat_messages = get_messages(st.session_state.conversation_id, owner_id)
if not chat_messages:
    st.info("Namaste! Aaj main aapki kis tarah madad kar sakta hoon?")

for message in chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Apna message yahan likhein...")
if prompt and prompt.strip():
    user_message = prompt.strip()
    save_message(
        st.session_state.conversation_id, owner_id, "user", user_message
    )
    with st.chat_message("user"):
        st.markdown(user_message)

    messages_for_model = get_messages(st.session_state.conversation_id, owner_id)
    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(get_reply_stream(messages_for_model))
            if not isinstance(reply, str) or not reply.strip():
                raise RuntimeError("AI provider ne khaali response diya.")
            save_message(
                st.session_state.conversation_id, owner_id, "assistant", reply
            )
        except Exception as error:
            st.error(f"AI response laane mein dikkat hui: {error}")
