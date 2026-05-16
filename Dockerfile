# Hugging Face Spaces — Docker SDK build for the AgriFlow FastAPI backend.
#
# Why this exists:
#   HF Spaces (Docker SDK) builds + runs this container; the resulting public
#   URL is what the Vercel dashboard hits via NEXT_PUBLIC_API_URL and what
#   Twilio's WhatsApp Sandbox webhook points at.
#
# Port contract:
#   HF Spaces expects the app to listen on 7860 by default. We honour that.
#
# Secrets (set in the Space's "Settings → Variables and secrets" UI, never here):
#   GEMINI_API_KEY        — from aistudio.google.com
#   TWILIO_ACCOUNT_SID    — Twilio console
#   TWILIO_AUTH_TOKEN     — Twilio console
#   TWILIO_WHATSAPP_FROM  — whatsapp:+14155238886 (sandbox) or your number
#   MOCK_MODE=true        — start here; flip to false once Gemini/Twilio keys are set.

FROM python:3.12-slim

# Avoid stale .pyc + force unbuffered stdout for clean HF log streaming.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

WORKDIR /app

# Install dependencies first so layer is cacheable when source changes.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Now copy the rest of the project.
COPY . .

# HF Spaces routes external traffic to this port.
EXPOSE 7860

# Same entrypoint Render would have used, just on port 7860 instead of $PORT.
CMD ["uvicorn", "whatsapp_bot.server:app", "--host", "0.0.0.0", "--port", "7860"]
