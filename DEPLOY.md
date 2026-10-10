# Deploying Roast News to a VPS (Hostinger, Docker)

One domain, automatic HTTPS. Caddy is the only public service:

```
Internet ──443──> caddy ──/api/*, /health──> backend:8000 ──> db:5432
                        └──everything else──> frontend:80 (nginx, React build)
```

## 1. Prerequisites

- A Hostinger VPS (Ubuntu 22.04/24.04, 2 GB RAM or more recommended), with SSH access.
- A domain (or subdomain), e.g. `roast.example.com`, with an **A record pointing to the VPS IP**.
  Check with `nslookup roast.example.com` before continuing; Caddy needs it to get a certificate.

## 2. Server setup (once)

```bash
ssh root@<VPS_IP>

# Docker Engine + compose plugin (skip if you chose Hostinger's "Docker" OS template)
curl -fsSL https://get.docker.com | sh

# Firewall: SSH + web only
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw --force enable

git clone https://github.com/rxbass/roast-news.git /opt/roast-news
cd /opt/roast-news
```

## 3. Production `.env` (on the server only, never committed)

```bash
cp .env.example .env
nano .env
```

Set at least:

| Variable | Value |
|---|---|
| `DOMAIN` | `roast.example.com` (no `https://`) |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `IP_HASH_SALT` | `openssl rand -hex 16` |
| `OPENAI_API_KEY` | your key |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | optional; blank disables Google sign-in |

`docker-compose.prod.yml` sets `ENVIRONMENT=production`, `FRONTEND_URL`, `GOOGLE_REDIRECT_URI`,
`CORS_ORIGINS`, `TRUSTED_PROXY_COUNT` and the frontend's API URL from `DOMAIN`, so those don't need editing.
The backend refuses to start in production with weak or `change-me` secrets.

`chmod 600 .env`

## 4. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl https://roast.example.com/health      # {"status":"ok","database":"ok"}
```

Migrations run automatically when the backend starts.

## 5. Google sign-in (optional)

In Google Cloud Console → OAuth client → add the authorised redirect URI
`https://<DOMAIN>/api/v1/auth/google/callback`.

## 6. Updating

```bash
cd /opt/roast-news
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker image prune -f
```

## 7. Operations

```bash
# Logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend caddy

# Database backup
docker compose exec -T db pg_dump -U roast roast_news | gzip > ~/roast_news_$(date +%F).sql.gz
```

Rate limits and the daily OpenAI cap are kept in memory, so they reset when the backend restarts.
Run a single backend instance (the default).
