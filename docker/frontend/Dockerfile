# =============================================================================
# HORRORBOT Frontend - Dockerfile (multi-stage)
# =============================================================================
# Vue.js 3 + TypeScript + Tailwind CSS → nginx static server
#
# Build:  docker compose build frontend
# Run:    docker compose up -d frontend
# =============================================================================

# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci

COPY src/frontend/ .
RUN printf "VITE_API_URL=/api/v1\nVITE_APP_TITLE=HorrorBot\n" > .env
RUN npm run build

# ── Stage 2: Serve ───────────────────────────────────────────────────────────
FROM nginx:alpine

COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

RUN apk add --no-cache curl

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
    CMD curl -f http://localhost/ || exit 1
