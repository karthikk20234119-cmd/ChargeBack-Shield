# Production Frontend Multi-Stage Dockerfile — Chargeback Shield Task 8.2
# Stage 1: Build React/Vite application
# Stage 2: Serve static production assets with unprivileged NGINX

# Stage 1: Build static bundle
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package descriptors
COPY package*.json ./

# Install npm dependencies
RUN npm ci

# Copy frontend source files
COPY . .

# Build production bundle
RUN npm run build

# Stage 2: Serve with minimal NGINX
FROM nginx:alpine-slim AS runner

# Copy custom NGINX configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy production static assets from Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose internal frontend port (80)
EXPOSE 80

# Local web availability health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

# Start NGINX in foreground
CMD ["nginx", "-g", "daemon off;"]
