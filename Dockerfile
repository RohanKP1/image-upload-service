FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy and install requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# The command now targets 'main:app' since main.py is in the root of WORKDIR
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
