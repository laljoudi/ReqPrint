# syntax=docker/dockerfile:1

# ---------- Stage 1: build the React frontend ----------
FROM node:20-slim AS frontend
WORKDIR /frontend

# Install dependencies first (better caching)
COPY frontend/package*.json ./
RUN npm install

# Copy the rest of the frontend and build it -> produces /frontend/dist
COPY frontend/ ./
RUN npm run build


# ---------- Stage 2: the Python app (final image) ----------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Non-privileged user (security best practice)
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install -r requirements.txt

# Copy the backend source code
COPY . .

# Bring in the built React files from Stage 1
COPY --from=frontend /frontend/dist ./frontend/dist

# Make sure the app files are owned by the non-root user
RUN chown -R appuser /app
USER appuser

EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]