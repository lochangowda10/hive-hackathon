# ---- Stage 1: build the frontend -----------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime serving API + built frontend ----------------
FROM python:3.12-slim
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /fe/dist /app/frontend/dist

# SQLite lives on a volume so accounts/chats survive restarts
ENV DATABASE_URL=sqlite:////data/swinglens.db
RUN mkdir -p /data
VOLUME /data

EXPOSE 8000
# $PORT respected for hosts like Render / HF Spaces; defaults to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
