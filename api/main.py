import os
import re
import io
import json
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
import docx
from openai import OpenAI

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PUBLIC_DIR = BASE_DIR / "public"
PROFILE_PATH = DATA_DIR / "linkedin_profile.md"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="LinkedIn Profile Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    reply: str
    section_heading: Optional[str] = None


class ProfileResponse(BaseModel):
    exists: bool
    markdown: str
    size_chars: int
    filename: Optional[str] = None


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    extracted = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted.append(text)
    return "\n\n".join(extracted)


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text_from_doc(file_bytes: bytes) -> str:
    # Try text/utf-8 or latin-1 extraction for plain/RTF-like doc, or raise helpful error
    try:
        decoded = file_bytes.decode("utf-8", errors="ignore")
        cleaned = re.sub(r"[^\x20-\x7E\n\r\t]", " ", decoded)
        words = [w for w in cleaned.split() if len(w) > 1]
        if len(words) > 50:
            return " ".join(words)
    except Exception:
        pass
    raise HTTPException(
        status_code=400,
        detail="Legacy .doc binary format cannot be safely parsed directly. Please save or export your profile as .docx or .pdf and upload.",
    )


def extract_text_from_html(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script and style elements
    for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        element.extract()
    
    # Check for body or main content
    target = soup.find("main") or soup.find("article") or soup.body or soup
    
    # Preserve headings and paragraphs
    lines = []
    for tag in target.find_all(["h1", "h2", "h3", "h4", "p", "li", "div"]):
        text = tag.get_text(separator=" ", strip=True)
        if not text:
            continue
        if tag.name == "h1":
            lines.append(f"\n# {text}\n")
        elif tag.name in ["h2", "h3"]:
            lines.append(f"\n## {text}\n")
        elif tag.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
    
    extracted = "\n".join(lines)
    return extracted if extracted.strip() else soup.get_text(separator="\n", strip=True)


def raw_text_to_markdown(raw_text: str, source_name: str = "") -> str:
    """
    Cleans and structures raw profile text into well-formatted Markdown
    preserving all experience, education, skills, dates, and achievements
    without inventing any missing facts.
    """
    raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    
    # If the text is already formatted markdown with headings, normalize and return
    if re.search(r"^##?\s+[A-Za-z]", raw_text, re.MULTILINE):
        # Already has markdown headings
        cleaned = re.sub(r"\n{3,}", "\n\n", raw_text).strip()
        return cleaned

    lines = [line.strip() for line in raw_text.split("\n")]
    lines = [l for l in lines if l]

    if not lines:
        return "# LinkedIn Profile\n\nNo textual content could be extracted."

    known_section_patterns = [
        (r"^(summary|about|about\s+me|professional\s+summary|profile)$", "## Summary"),
        (r"^(experience|work\s+experience|employment\s+history|professional\s+experience)$", "## Experience"),
        (r"^(education|academic\s+background|academics)$", "## Education"),
        (r"^(skills|top\s+skills|skills\s*&\s*expertise|technical\s+skills)$", "## Skills"),
        (r"^(certifications|licenses\s*&\s*certifications|certificates)$", "## Certifications"),
        (r"^(projects|personal\s+projects|featured\s+projects)$", "## Projects & Achievements"),
        (r"^(honors|awards|honors\s*&\s*awards|achievements)$", "## Honors & Awards"),
        (r"^(languages|language\s+proficiency)$", "## Languages"),
        (r"^(contact|contact\s+info|contact\s+information)$", "## Contact & Links"),
    ]

    md_output = []
    
    # Try identifying candidate's name from first line if short
    first_line = lines[0]
    if len(first_line) < 60 and not any(re.match(p[0], first_line, re.IGNORECASE) for p in known_section_patterns):
        md_output.append(f"# {first_line}\n")
        lines = lines[1:]
    else:
        md_output.append("# Profile\n")

    for line in lines:
        matched_section = False
        for pattern, header in known_section_patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                md_output.append(f"\n{header}\n")
                matched_section = True
                break
        if matched_section:
            continue

        # Detect bullet points or job role lines
        if line.startswith(("-", "•", "*", "–")):
            bullet_text = re.sub(r"^[-•*–]\s*", "", line)
            md_output.append(f"- {bullet_text}")
        elif re.search(r"\b(19\d\d|20\d\d)\b", line) and len(line) < 100:
            # Likely a date or title/company line
            md_output.append(f"*{line}*")
        else:
            md_output.append(line)

    structured = "\n".join(md_output)
    # Deduplicate excessive newlines
    structured = re.sub(r"\n{3,}", "\n\n", structured).strip()
    return structured


async def fetch_webpage_content(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in [401, 403, 429, 999] or "authwall" in str(resp.url).lower() or "login" in str(resp.url).lower():
                raise HTTPException(
                    status_code=400,
                    detail="The URL is protected by a login wall or bot challenge (typical for direct LinkedIn profile URLs). Please download or export your profile as a PDF, HTML, or TXT file and upload it directly.",
                )
            resp.raise_for_status()
            return resp.text
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to access the URL ({str(e)}). If this profile is protected or private, please upload the profile file directly.",
        )


def get_profile_context(profile_markdown: str, user_query: str) -> str:
    """
    For normal profiles, returns full markdown.
    For very large profiles (>12,000 chars), extracts header and highest-scoring relevant sections.
    """
    if len(profile_markdown) <= 12000:
        return profile_markdown

    # Split markdown into sections
    sections = re.split(r"(?=\n##\s+)", profile_markdown)
    if len(sections) <= 1:
        return profile_markdown[:12000]

    header_section = sections[0]
    other_sections = sections[1:]

    # Score each section based on keyword match
    query_tokens = set(re.findall(r"\w+", user_query.lower()))
    scored_sections = []

    for section in other_sections:
        section_tokens = set(re.findall(r"\w+", section.lower()))
        score = len(query_tokens.intersection(section_tokens))
        scored_sections.append((score, section))

    # Sort descending by score
    scored_sections.sort(key=lambda x: x[0], reverse=True)

    # Assemble context within ~12,000 chars
    selected = [header_section]
    current_len = len(header_section)

    for score, section in scored_sections:
        if current_len + len(section) < 12000:
            selected.append(section)
            current_len += len(section)

    return "\n\n".join(selected)


@app.get("/api/profile", response_model=ProfileResponse)
def get_profile():
    if PROFILE_PATH.exists():
        content = PROFILE_PATH.read_text(encoding="utf-8")
        return ProfileResponse(
            exists=True,
            markdown=content,
            size_chars=len(content),
            filename="linkedin_profile.md",
        )
    return ProfileResponse(exists=False, markdown="", size_chars=0)


@app.post("/api/upload")
async def upload_profile(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
):
    if not file and not url:
        raise HTTPException(
            status_code=400,
            detail="Please provide either a profile file or a valid URL.",
        )

    extracted_text = ""
    source_name = ""

    if file:
        filename = file.filename or "unknown"
        source_name = filename
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        allowed_exts = {"pdf", "doc", "docx", "txt", "html", "htm", "md"}

        if ext not in allowed_exts:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type .{ext}. Allowed types: PDF, DOC, DOCX, TXT, HTML, MD.",
            )

        content_bytes = await file.read()
        if len(content_bytes) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds the 15MB limit.",
            )

        try:
            if ext == "pdf":
                extracted_text = extract_text_from_pdf(content_bytes)
            elif ext == "docx":
                extracted_text = extract_text_from_docx(content_bytes)
            elif ext == "doc":
                extracted_text = extract_text_from_doc(content_bytes)
            elif ext in ["html", "htm"]:
                extracted_text = extract_text_from_html(content_bytes.decode("utf-8", errors="ignore"))
            elif ext in ["txt", "md"]:
                extracted_text = content_bytes.decode("utf-8", errors="ignore")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error extracting content from {filename}: {str(e)}",
            )

    elif url:
        source_name = url
        url = url.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(
                status_code=400,
                detail="Please provide a valid URL starting with http:// or https://",
            )
        html_content = await fetch_webpage_content(url)
        extracted_text = extract_text_from_html(html_content)

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No readable text could be extracted from the provided source.",
        )

    markdown_profile = raw_text_to_markdown(extracted_text, source_name)
    PROFILE_PATH.write_text(markdown_profile, encoding="utf-8")

    return {
        "success": True,
        "message": "Profile processed and saved to data/linkedin_profile.md successfully.",
        "markdown": markdown_profile,
        "source": source_name,
        "size_chars": len(markdown_profile),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_query = request.message.strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="User message cannot be empty.")

    if not PROFILE_PATH.exists():
        return ChatResponse(
            reply="My profile does not include that information. Please upload a LinkedIn profile first.",
            section_heading=None,
        )

    profile_text = PROFILE_PATH.read_text(encoding="utf-8")
    if not profile_text.strip():
        return ChatResponse(
            reply="My profile does not include that information. The current profile is empty.",
            section_heading=None,
        )

    load_dotenv(override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your_openai_api_key") or "your_openai_key" in api_key.lower():
        return ChatResponse(
            reply="⚠️ OpenAI API key is not configured. Please add your valid OPENAI_API_KEY to the .env file.",
            section_heading=None,
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    context_text = get_profile_context(profile_text, user_query)

    system_prompt = (
        "You are an AI representing the person described in the provided LinkedIn profile.\n"
        "You speak strictly in first person ('I', 'me', 'my').\n"
        "Answer naturally, briefly, and accurately based solely on the provided profile context.\n\n"
        "CRITICAL RULES:\n"
        "1. The provided profile context is your ONLY factual source.\n"
        "2. Never invent, guess, extrapolate, or assume unsupported personal or professional facts.\n"
        "3. If information is missing, ambiguous, or not stated in the profile, you MUST say exactly:\n"
        "'My profile does not include that information.'\n"
        "(Do not add apologies, assumptions, or extra commentary—use exactly this sentence).\n"
        "4. Identify the primary supporting Markdown section heading (e.g., 'Summary', 'Experience', 'Education', 'Skills', 'Certifications', 'Projects & Achievements', 'Languages', 'Contact & Links') that confirms your answer. If the answer is not in the profile, section_heading must be null.\n"
        "5. Respond strictly in valid JSON format:\n"
        "{\n"
        '  "reply": "<brief first-person answer>",\n'
        '  "section_heading": "<section name without # symbols, or null>"\n'
        "}\n\n"
        f"--- PROFILE CONTEXT ---\n{context_text}\n--- END PROFILE CONTEXT ---"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Include recent chat history
    if request.history:
        for item in request.history[-6:]:
            if item.role in ["user", "assistant"]:
                messages.append({"role": item.role, "content": item.content})

    messages.append({"role": "user", "content": user_query})

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=500,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        reply = parsed.get("reply", "My profile does not include that information.")
        section_heading = parsed.get("section_heading")
        return ChatResponse(reply=reply, section_heading=section_heading)

    except Exception as e:
        error_msg = str(e)
        if "AuthenticationError" in error_msg or "Incorrect API key" in error_msg or "invalid_api_key" in error_msg:
            return ChatResponse(
                reply="⚠️ Invalid OpenAI API key. Please check the `OPENAI_API_KEY` in your `.env` file.",
                section_heading=None,
            )
        if "RateLimitError" in error_msg or "insufficient_quota" in error_msg or "quota" in error_msg.lower():
            return ChatResponse(
                reply="⚠️ OpenAI API quota exceeded or rate limit reached. Please check your OpenAI account billing / credits.",
                section_heading=None,
            )
        if "response_format" in error_msg:
            # Fallback for models not supporting json_object
            try:
                client = OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=500,
                )
                text = (response.choices[0].message.content or "").strip()
                return ChatResponse(reply=text, section_heading=None)
            except Exception as e2:
                return ChatResponse(reply=f"⚠️ OpenAI error: {str(e2)}", section_heading=None)
        return ChatResponse(reply=f"⚠️ OpenAI error: {error_msg}", section_heading=None)


# Serve static frontend files
if PUBLIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
