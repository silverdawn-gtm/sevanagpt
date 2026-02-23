FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download model at build time so container starts fast
RUN python -c "\
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; \
name = 'ai4bharat/indictrans2-en-indic-dist-200M'; \
AutoTokenizer.from_pretrained(name, trust_remote_code=True); \
AutoModelForSeq2SeqLM.from_pretrained(name, trust_remote_code=True)"

# Copy application code
COPY app/ app/

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
