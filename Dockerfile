# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OPENAI_API_KEY=""
ENV SLACK_WEBHOOK_URL=""

# Set working directory inside container
WORKDIR /app

# Install system dependencies if any are needed (e.g. git for package building)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY src/ ./src/
COPY data/ ./data/
COPY prompts/ ./prompts/
COPY dashboard.py .

# Create output directories for reports
RUN mkdir -p reports

# Default entry point runs the CLI evaluation runner
ENTRYPOINT ["python", "-m", "src.run"]

# Example usage instructions:
# docker build -t model-evaluator .
# docker run --env OPENAI_API_KEY="your-key" --env SLACK_WEBHOOK_URL="your-webhook" model-evaluator --prompt prompts/v1.yaml
