# Production image: builds the frontend and serves it together with the API.
# See SECURITY.md for the runtime flags this image should be started with.

FROM node:22-slim AS frontend
WORKDIR /app
COPY shared ./shared
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
COPY shared ./shared
COPY --from=frontend /app/frontend/dist ./frontend/dist
RUN useradd --system --uid 10001 --no-create-home codeviz
USER 10001
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
