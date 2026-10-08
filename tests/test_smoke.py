import io
import sys
from pathlib import Path
import docx
from pypdf import PdfWriter
from fastapi.testclient import TestClient

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from api.main import app, raw_text_to_markdown, get_profile_context

client = TestClient(app)


def test_static_files():
    print("Testing static file routes...")
    r = client.get("/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "Profile Bot" in r.text or "Active Knowledge Base" in r.text

    r = client.get("/style.css")
    assert r.status_code == 200
    assert "--bg-main" in r.text

    r = client.get("/script.js")
    assert r.status_code == 200
    assert "fetchCurrentProfile" in r.text
    print("[OK] Static routes verified.")


def test_get_profile():
    print("Testing GET /api/profile...")
    r = client.get("/api/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["exists"] is True
    assert "Alex Rivera" in data["markdown"]
    assert data["size_chars"] > 100
    print(f"[OK] GET /api/profile returned {data['size_chars']} characters.")


def test_upload_txt_file():
    print("Testing POST /api/upload with TXT file...")
    sample_text = (
        "Jane Doe\n"
        "Lead Data Scientist\n\n"
        "Summary\n"
        "Passionate about deep learning and computer vision with 6 years experience.\n\n"
        "Experience\n"
        "Senior ML Engineer at AI Labs from 2021 to Present.\n"
        "- Built recommendation systems with 10M DAU.\n\n"
        "Education\n"
        "MS in Data Science from Stanford University (2020).\n\n"
        "Skills\n"
        "Python, PyTorch, TensorFlow, Scikit-learn, SQL\n"
    )
    files = {"file": ("jane_doe_profile.txt", sample_text.encode("utf-8"), "text/plain")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert "## Summary" in data["markdown"]
    assert "## Experience" in data["markdown"]
    assert "## Education" in data["markdown"]
    assert "## Skills" in data["markdown"]
    print("[OK] TXT upload and markdown structure verified.")


def test_upload_docx_file():
    print("Testing POST /api/docx file...")
    doc = docx.Document()
    doc.add_heading("Marcus Vance", 0)
    doc.add_paragraph("Summary")
    doc.add_paragraph("Principal Cloud Architect with 12 years of AWS experience.")
    doc.add_paragraph("Experience")
    doc.add_paragraph("Cloud Architect at SkyNetics 2018-2024")
    doc.add_paragraph("Education")
    doc.add_paragraph("BS Computer Engineering at Georgia Tech")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    files = {"file": ("marcus.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert "Marcus Vance" in data["markdown"]
    print("[OK] DOCX upload verified.")


def test_upload_pdf_file():
    print("Testing POST /api/upload with PDF...")
    # Generate minimal valid PDF using pypdf
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    pdf_bytes.seek(0)

    # Empty pdf should return 400 with helpful error
    files = {"file": ("empty.pdf", pdf_bytes.getvalue(), "application/pdf")}
    r = client.post("/api/upload", files=files)
    assert r.status_code == 400
    assert "No readable text" in r.json()["detail"]
    print("[OK] PDF handling & validation verified.")


def test_chat_endpoint_key_validation():
    print("Testing POST /api/chat with placeholder API key...")
    payload = {"message": "What is your current job?"}
    r = client.post("/api/chat", json=payload)
    assert r.status_code == 200
    data = r.json()
    # When api key is placeholder, returns informative message rather than crashing
    assert "OpenAI API key is not configured" in data["reply"] or "My profile does not include" in data["reply"]
    print("[OK] Chat endpoint handled configuration safely.")


def test_restore_default_profile():
    print("Restoring default sample profile...")
    default_text = (
        "# Alex Rivera\n"
        "**Senior Full-Stack & AI Engineer** | San Francisco, CA | alex.rivera@example.com\n\n"
        "## Summary\n"
        "Passionate software engineer with over 7 years of experience architecting distributed systems.\n\n"
        "## Experience\n"
        "### Senior AI Platform Engineer | CloudNova Inc.\n"
        "*March 2022 – Present | San Francisco, CA*\n"
        "- Designed and deployed internal retrieval and inference microservices.\n\n"
        "## Education\n"
        "### Bachelor of Science in Computer Science\n"
        "*The University of Texas at Austin | Graduated May 2017*\n\n"
        "## Skills\n"
        "- **Languages:** Python, TypeScript, JavaScript, SQL\n\n"
        "## Certifications\n"
        "- **AWS Certified Solutions Architect – Associate** (2022)\n\n"
        "## Projects & Achievements\n"
        "- **LocalChat AI:** Open-source offline documentation search bot with 1,200+ GitHub stars.\n\n"
        "## Languages\n"
        "- **English:** Native / Bilingual\n"
        "- **Spanish:** Professional working proficiency\n"
    )
    profile_path = BASE_DIR / "data" / "linkedin_profile.md"
    profile_path.write_text(default_text, encoding="utf-8")
    print("[OK] Default profile restored.")


if __name__ == "__main__":
    test_static_files()
    test_get_profile()
    test_upload_txt_file()
    test_upload_docx_file()
    test_upload_pdf_file()
    test_chat_endpoint_key_validation()
    test_restore_default_profile()
    print("\nALL SMOKE TESTS PASSED!")

