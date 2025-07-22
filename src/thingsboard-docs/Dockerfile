FROM python:3.11-slim

WORKDIR /app

# Copy the OpenAPI specification and Python files
COPY openapi-spec.json .
COPY thingsboard-docs.py .
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir -e .

# Set the entry point
ENTRYPOINT ["python", "thingsboard-docs.py"] 