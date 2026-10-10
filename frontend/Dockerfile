# syntax=docker/dockerfile:1

# ---------- Stage 1: build static assets ----------
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Vite inlines VITE_* env vars at build time
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ---------- Stage 2: serve with nginx ----------
FROM nginx:alpine AS runtime

# The image renders /etc/nginx/templates/*.template into conf.d at startup, substituting
# defined env vars (only API_ORIGIN here; nginx's own $uri/$csp are left alone).
ARG VITE_API_URL=http://localhost:8000
ENV API_ORIGIN=${VITE_API_URL}
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
