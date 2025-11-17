import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import create_document
from schemas import Enquiry
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI(title="Grandiflora Garden Services API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "ok", "service": "Grandiflora Garden Services API"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


class EnquiryRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    service: Optional[str] = None
    message: Optional[str] = None
    suburb: Optional[str] = None


def send_email_notification(enquiry: EnquiryRequest):
    to_email = os.getenv("ENQUIRY_TO_EMAIL", "jessie@grandifloragardenservices.co.nz")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_email = os.getenv("SMTP_FROM", to_email)

    subject = f"New Garden Service Enquiry from {enquiry.name}"
    body = f"""
A new enquiry has been submitted on the website.

Name: {enquiry.name}
Email: {enquiry.email}
Phone: {enquiry.phone or '-'}
Service: {enquiry.service or '-'}
Suburb: {enquiry.suburb or '-'}

Message:
{enquiry.message or '-'}

--
Grandiflora Garden Services Website
"""

    # If SMTP not configured, skip sending (but don't fail the request)
    if not smtp_host or not smtp_user or not smtp_pass:
        return {
            "sent": False,
            "reason": "SMTP not configured in environment. Stored enquiry in database.",
        }

    try:
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())

        return {"sent": True}
    except Exception as e:
        return {"sent": False, "reason": str(e)[:200]}


@app.post("/api/enquiries")
async def create_enquiry(payload: EnquiryRequest):
    try:
        # Save to database first
        doc_id = create_document("enquiry", payload.model_dump())

        # Try to send email notification
        email_status = send_email_notification(payload)

        return {
            "success": True,
            "id": doc_id,
            "email": email_status,
            "message": "Thanks! Your enquiry has been submitted. We'll be in touch shortly.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit enquiry: {str(e)[:200]}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
