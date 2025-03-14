FROM python:3.11-alpine

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "server.py"]