# Deploying Roast News to a VPS (Docker + Cloudflare Tunnel)

Roast News shares a VPS with other apps without touching their ports or proxy. A Cloudflare
Tunnel is the only way in: `cloudflared` connects *out* to Cloudflare, Cloudflare terminates
HTTPS for the domain, and no container publishes a host port.

```
visitor ─HTTPS─> Cloudflare ─tunnel─> cloudflared ─┬─ /api/*, /health → backend:8000 ──> db
                                                   └─ everything else  → frontend:80 (nginx, React build)
```

## 1. Cloudflare (once)

1. **Add the domain** to Cloudflare (Free plan); a registrar transfer is not needed. Point the domain's
   nameservers at the two Cloudflare gives you, and wait until the site shows **Active**.
   Delete any old `A` record for the apex; the tunnel creates its own record.
2. **Create the tunnel**: Zero Trust → Networks → Tunnels → Create tunnel → *Cloudflared*,
   name `roast-news`. Copy the **token** from the install command (the long string after
   `--token`). It is a secret.
3. **Public hostnames** (routes) on the tunnel, in this order:

   | # | Hostname | Path | Service |
   |---|---|---|---|
   | 1 | `roastmynews.sbs` | `^/(api/.*\|health)$` | `http://backend:8000` |
   | 2 | `roastmynews.sbs` | *(empty)* | `http://frontend:80` |

4. SSL/TLS → Edge Certificates: turn on **Always Use HTTPS**.

## 2. Server (once)

As the `deploy` user (in the `docker` group):

```bash
git clone https://github.com/rxbass/roast-news.git /opt/roast-news
cd /opt/roast-news
cp .env.example .env && chmod 600 .env
nano .env
```

Set at least:

| Variable | Value |
|---|---|
| `DOMAIN` | `roastmynews.sbs` (no `https://`) |
| `TUNNEL_TOKEN` | the tunnel token from step 1.2 |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `IP_HASH_SALT` | `openssl rand -hex 16` |
| `OPENAI_API_KEY` | your key |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | optional; blank disables Google sign-in |

`docker-compose.prod.yml` derives `ENVIRONMENT=production`, `FRONTEND_URL`, `GOOGLE_REDIRECT_URI`,
`CORS_ORIGINS`, `TRUSTED_PROXY_COUNT` and the frontend's API URL from `DOMAIN`.
The backend refuses to start in production with weak or `change-me` secrets.

## 3. Start / update

```bash
cd /opt/roast-news
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -s https://roastmynews.sbs/health     # {"status":"ok","database":"ok"}
docker image prune -f
```

Migrations run automatically when the backend starts.

## 4. Google sign-in (optional)

Google Cloud Console → OAuth client → authorised redirect URI
`https://<DOMAIN>/api/v1/auth/google/callback`.

## 5. Operations

```bash
alias rn='docker compose -f docker-compose.yml -f docker-compose.prod.yml'
rn logs -f backend cloudflared
rn exec -T db pg_dump -U roast roast_news | gzip > ~/roast_news_$(date +%F).sql.gz   # backup
```

Rate limits and the daily OpenAI cap are kept in memory and reset when the backend restarts.
Run a single backend instance (the default).
