FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY web_server/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

WORKDIR /app/web_server

EXPOSE 5000

CMD ["python", "server.py"]