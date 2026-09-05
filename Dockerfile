FROM python:3.12-slim
WORKDIR /app
COPY server.py .
COPY static/ static/
RUN pip install --no-cache-dir fastapi uvicorn
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
