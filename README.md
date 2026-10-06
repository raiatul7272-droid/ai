# RADHE

Python aur Streamlit par bana local AI chatbot. Yeh Gemini ya Groq ke saath
real-time streaming chat karta hai, aur conversations ko local SQLite database
(`chat_history.db`) mein save karta hai.

## Zaroori cheezein

- Python 3.10 ya uske baad ka version
- Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey)) ya
  Groq API key ([Groq Console](https://console.groq.com/keys))

## Windows par setup

PowerShell mein project folder khol kar:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` file khol kar apna provider aur API key set karein. Gemini ke liye:

```dotenv
CHAT_PROVIDER=gemini
GEMINI_API_KEY=apni_gemini_api_key_yahan
GEMINI_MODEL=gemini-2.5-flash
```

Groq ke liye `CHAT_PROVIDER=groq` aur `GROQ_API_KEY` set karein:

```dotenv
CHAT_PROVIDER=groq
GROQ_API_KEY=apni_groq_api_key_yahan
GROQ_MODEL=llama-3.3-70b-versatile
```

Key ko quotes mein likhne ki zaroorat nahi hai. `.env` file ko share ya commit
na karein; yeh `.gitignore` mein hai.

## App chalana

```powershell
streamlit run app.py
```

Terminal mein dikhaye gaye local URL ko browser mein kholein. Chat sidebar se
nayi conversation shuru, purani conversation kholein, ya current conversation
delete karein. Chats SQLite database mein save hoti hain aur browser session ke
owner ID se isolate hoti hain.

## GitHub par publish aur Streamlit Community Cloud deploy

1. Project ko GitHub repository mein push karein. `.env` aur `chat_history.db`
   `.gitignore` mein hain; in files ko GitHub par upload na karein.
2. [Streamlit Community Cloud](https://share.streamlit.io/) par GitHub se sign
   in karke **Create app** chunein.
3. Repository, branch, aur main file path `app.py` select karke deploy karein.
4. App ke **Settings → Secrets** mein apne provider ke secrets set karein,
   jaise Gemini ke liye:

   ```toml
   CHAT_PROVIDER = "gemini"
   GEMINI_API_KEY = "apni_gemini_api_key"
   GEMINI_MODEL = "gemini-2.5-flash"
   ```

   Groq ke liye `CHAT_PROVIDER = "groq"` aur `GROQ_API_KEY` set karein.
   API key ko source code ya public repository mein kabhi na daalein.

Yeh public app har active browser session ki chats ko alag rakhta hai. Session
badalne ya refresh hone par purani chat dobara dikhai na de sakti hai. Streamlit
Community Cloud par local SQLite file permanent storage nahi hai; reliable,
cross-session chat history ke liye managed database aur user authentication
zaroori hain. Public deployment se pehle Streamlit Cloud Secrets mein API key
set karein.

## Mac/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Local run ke liye `.env` mein provider aur uski API key bharna zaroori hai.
