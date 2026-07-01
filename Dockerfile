# Img2Video - All-in-One Docker Image
# This Dockerfile builds all components into a single image

# Stage 1: Frontend Builder
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install && npm install @rollup/rollup-linux-x64-musl
COPY frontend/ ./
RUN npm run build

# Stage 2: Admin Builder
FROM node:20-alpine AS admin-builder
WORKDIR /admin
COPY admin/package*.json ./
RUN npm install && npm install @rollup/rollup-linux-x64-musl
COPY admin/ ./
RUN npm run build

# Stage 3: Python Backend
FROM python:3.11-slim AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ ./

# Copy frontend build
COPY --from=frontend-builder /frontend/dist /var/www/front

# Copy admin build
COPY --from=admin-builder /admin/dist /var/www/admin

# Copy nginx configuration
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/app.conf /etc/nginx/sites-available/app

# Create nginx sites
RUN mkdir -p /etc/nginx/sites-enabled && \
    ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app

# Copy supervisor configuration
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy startup script
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

# Expose ports
EXPOSE 8101 8102 8103

# Start all services
CMD ["/start.sh"]
