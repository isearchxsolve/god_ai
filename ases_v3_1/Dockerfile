FROM python:3.11-slim AS builder

WORKDIR /build
COPY agent_service/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/ases/.local/bin:$PATH

RUN groupadd --system ases && useradd --system --gid ases --create-home ases
WORKDIR /app
COPY --from=builder /root/.local /home/ases/.local
COPY --chown=ases:ases agent_service/ ./agent_service/
USER ases
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["uvicorn", "agent_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
