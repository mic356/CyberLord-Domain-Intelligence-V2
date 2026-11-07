FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    whatweb \
    git \
    ca-certificates \
    openssl \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/testssl/testssl.sh.git /opt/testssl.sh \
    && ln -s /opt/testssl.sh/testssl.sh /usr/local/bin/testssl.sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py .

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180 worker:app"]