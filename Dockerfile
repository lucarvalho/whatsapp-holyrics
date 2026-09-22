FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.deno/bin:${PATH}"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
        unzip && \
    rm -rf /var/lib/apt/lists/*

# Instala o Deno
RUN curl -fsSL https://deno.land/install.sh | sh

# Instala Python + yt-dlp com EJS
RUN pip install --no-cache-dir \
        fastapi \
        uvicorn \
        python-multipart \
        jinja2 \
        "yt-dlp[default]"

WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
