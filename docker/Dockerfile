# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS javascript
FROM python:3.12-slim-bookworm

# Dependencies belong to the image, never to a copied virtual environment.
COPY --from=javascript /usr/local/bin/node /usr/local/bin/node
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      cp /etc/ssl/certs/ca-certificates.crt /tmp/izzi-original-ca; \
      cat /run/secrets/proxy_ca >> /etc/ssl/certs/ca-certificates.crt; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends ffmpeg libstdc++6 ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -f /tmp/izzi-original-ca ]; then \
      cp /tmp/izzi-original-ca /etc/ssl/certs/ca-certificates.crt; rm /tmp/izzi-original-ca; \
    fi
WORKDIR /app
COPY requirements-capture.txt /tmp/requirements-capture.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir -r /tmp/requirements-capture.txt 'yt-dlp[default]' \
    && python -m pip check
COPY . /app
ARG IZZI_BRANCH=WebUI
# Associate the copied source with its upstream commit; fail on mismatched source.
RUN --mount=type=secret,id=proxy_ca \
    set -eu; git init -b "$IZZI_BRANCH" \
    && git config core.filemode false \
    && git config core.autocrlf input \
    && git remote add origin https://github.com/YuriMladenov/izzi.git \
    && if [ -f /run/secrets/proxy_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/proxy_ca > /tmp/izzi-git-ca; \
      export GIT_SSL_CAINFO=/tmp/izzi-git-ca; fi; \
    git fetch --depth=1 origin "$IZZI_BRANCH" \
    && git reset --mixed FETCH_HEAD && git diff --exit-code \
    && rm -f /tmp/izzi-git-ca
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 IZZI_CAPTURE_HOST=0.0.0.0
RUN mkdir -p archive state captures /root/.mitmproxy vendor/geogebra \
    && python -c 'import mitmproxy, yt_dlp, yt_dlp_ejs; import server' \
    && node --version && ffmpeg -version > /dev/null
EXPOSE 8765 8877
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD ["python", "-c", "import urllib.request; r=urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8765/__ui__/izzi-logo.svg',timeout=5); assert r.status==200 and b'<svg' in r.read()"]
# SIGINT runs the server's finally block and stops its owned capture/download jobs.
STOPSIGNAL SIGINT
CMD ["python", "-u", "docker/entrypoint.py"]
