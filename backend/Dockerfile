FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry>=2.0.0,<3"

WORKDIR /app
COPY README.md ./
COPY backend/pyproject.toml backend/poetry.lock ./backend/

WORKDIR /app/backend
RUN poetry install --only main --no-root --no-ansi

COPY backend/src ./src
RUN poetry install --only main --no-ansi

EXPOSE 8000
CMD ["uvicorn", "tradenet_chat.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
