# About Me – Local AI Chatbot

A simple, fast, and fully functional local AI chatbot that answers questions about you using your LinkedIn profile as the single source of truth.

Everything runs locally on your machine except requests to the OpenAI API for chat generation.

---

## ✨ Features & Architecture

- **Zero-RAG Simplicity:** No vector databases, no embeddings, no LangChain, no Ollama, and no heavy frameworks. Reads directly from a single local Markdown file (`data/linkedin_profile.md`).
- **Flexible Profile Ingestion:**
  - **File Upload:** Upload PDF, DOCX, DOC, TXT, HTML, or MD files directly.
  - **Web URL Import:** Fetch and convert public profile pages. (If blocked by login walls/CAPTCHA, cleanly instructs you to upload).
  - **Local Parsing:** All file extraction happens locally on your machine (using `pypdf`, `python-docx`, and `BeautifulSoup`). OpenAI is **never** used for document conversion.
- **Strict Grounding:**
  - Answers strictly in first person (*"I am...", "I worked at..."*).
  - If information is not in your profile, replies exactly: **"My profile does not include that information."**
  - Displays the supporting Markdown section heading (e.g., `Source: Experience`, `Source: Skills`) alongside responses.
- **Session Chat History:** Maintains conversation context during the current chat session for fluid follow-up questions.
- **Sleek Vanilla Web Interface:** Built with pure HTML5, modern CSS3, and vanilla JavaScript. Features live Markdown preview, drag-and-drop file upload, typing indicators, suggested questions, and toast notifications.

---

## 📁 Project Structure

```text
linkedin-chatbot/
├── public/
│   ├── index.html       # Single-page interface
│   ├── style.css        # Sleek dark-mode design & animations
│   └── script.js        # Vanilla JS logic & API interaction
├── api/
│   └── main.py          # FastAPI application & extraction logic
├── data/
│   └── linkedin_profile.md  # Active profile knowledge base
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── .gitignore           # Git ignore configuration
└── README.md            # Documentation
```

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 installed.

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and set your OpenAI API key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
OPENAI_API_KEY=sk-proj-...your-actual-key...
OPENAI_MODEL=gpt-4o-mini
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
Start the FastAPI server:
```bash
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 🛠️ API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/profile` | Returns current profile status and raw Markdown. |
| `POST` | `/api/upload` | Uploads a file (`.pdf`, `.docx`, `.doc`, `.txt`, `.html`, `.md`) or submits a URL to extract and overwrite `data/linkedin_profile.md`. |
| `POST` | `/api/chat` | Accepts `{ "message": str, "history": [...] }`, sends profile context to OpenAI, and returns `{ "reply": str, "section_heading": str }`. |

---

## 🔒 Security & Privacy
- API keys are stored only in `.env` on your local backend and never exposed to the frontend.
- Files and Markdown profiles remain on your local disk in the `data/` folder.
