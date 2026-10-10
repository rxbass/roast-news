# CLAUDE.md - Roast News Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** Roast News
**Description:** Paste any news URL and get a funny roast of it in Tanglish (Tamil + English). Free and public; Google sign-in is optional.
**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TypeScript
- Database: PostgreSQL + SQLAlchemy + Alembic
- Auth: Anonymous by default + optional Google OAuth (JWT)
- UI: Chakra UI + Framer Motion
- AI: OpenAI GPT (generation + Moderation API)

---

## Project Structure

```
roast-news/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── refresh_token.py
│   │   │   └── roast.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   └── roast.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   └── roasts.py
│   │   ├── services/
│   │   │   ├── scraper_service.py   # Safe URL fetch + article extraction
│   │   │   ├── safety_service.py    # Moderation + sensitive-topic checks
│   │   │   ├── roast_service.py     # Prompt building + OpenAI call + caching
│   │   │   └── prompts/
│   │   │       └── roast_system.md  # Tanglish style guide + spice rules
│   │   ├── auth/
│   │   │   ├── google.py
│   │   │   ├── jwt.py
│   │   │   └── dependencies.py      # get_current_user, get_optional_user
│   │   └── core/
│   │       └── rate_limit.py        # slowapi limiter
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # RoastForm, SpiceSelector, RoastCard, ShareButtons, Navbar
│   │   ├── pages/        # HomePage, RoastPage, MyRoastsPage, AuthCallbackPage
│   │   ├── hooks/        # useRoast, useAuth
│   │   ├── services/     # api.ts, roastService.ts, authService.ts
│   │   ├── context/      # AuthContext
│   │   └── types/        # roast.ts, user.ts
│   └── package.json
├── .claude/
│   └── commands/
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# ALWAYS use type hints
def get_roast(db: Session, roast_id: UUID) -> Roast | None:
    pass

# ALWAYS add docstrings for public functions
async def create_roast(db: Session, data: RoastCreate, user: User | None, ip_hash: str) -> Roast:
    """
    Fetch the article, run safety checks, and generate a Tanglish roast.

    Args:
        db: Database session
        data: Roast request (url, spice_level)
        user: Signed-in user, or None for anonymous
        ip_hash: Salted hash of the client IP

    Returns:
        Created (or cached) Roast object
    """
    pass

# Async endpoints
@router.post("/roasts", status_code=201)
async def create_roast_endpoint(data: RoastCreate, db: Session = Depends(get_db)) -> RoastResponse:
    pass
```

### TypeScript (Frontend)
```typescript
// ALWAYS define interfaces for props and data
type SpiceLevel = "mild" | "medium" | "extra_spicy";
type RoastStatus = "completed" | "refused" | "failed";

interface Roast {
  id: string;
  sourceUrl: string;
  sourceDomain: string;
  articleTitle: string;
  spiceLevel: SpiceLevel;
  roastText: string | null;
  status: RoastStatus;
  refusalReason: string | null;
  createdAt: string;
}

// NO any types allowed
const fetchRoast = async (id: string): Promise<Roast> => {
  // ...
};
```

---

## Forbidden Patterns

### Backend
- ❌ Never use `print()` - use `logging` module
- ❌ Never hardcode secrets or API keys - use environment variables
- ❌ Never use `SELECT *` - specify columns
- ❌ Never skip input validation
- ❌ Never fetch a user-supplied URL without the SSRF guard in `scraper_service`
- ❌ Never call OpenAI directly from routers - go through `roast_service` / `safety_service`
- ❌ Never store raw client IPs - salted hash only
- ❌ Never log full article text or API keys

### Frontend
- ❌ Never use `any` type
- ❌ Never leave console.log in production
- ❌ Never skip error handling in async operations (handle 400 / 422 / 429 / refused)
- ❌ Never use inline styles - use Chakra UI props/theme
- ❌ Never render roast or article text with `dangerouslySetInnerHTML`

---

## Module-Specific Rules

### Authentication Module
- Login is **optional**. Roast endpoints must work for anonymous users.
- Use `get_optional_user` on public endpoints and `get_current_user` on protected ones.
- No email/password auth; Google OAuth is the only sign-in method.

### Roast Generator Module
- `spice_level` must be one of: `mild`, `medium`, `extra_spicy`
- `status` must be one of: `completed`, `refused`, `failed`
- Roast IDs are UUIDs (permalinks must not be enumerable)
- `user_id` is nullable (anonymous roasts); only the owner may delete a roast
- Cache: the same `(url_hash, spice_level)` within 24h returns the existing completed roast
- Normalize URLs before hashing (lowercase host, strip fragments and tracking params like `utm_*`)

### Tanglish Style Rules (for prompts)
- Output = Tamil words in **Latin script** mixed naturally with English. Never Tamil script, never pure English.
- Use common slang naturally: *enna da, semma, vera level, mokka, ayyo, machan, scene-u, gethu, kalaai*.
- Spice levels:
  - **mild**: light teasing, friendly uncle-at-tea-shop energy
  - **medium**: sarcastic, meme-style punchlines
  - **extra_spicy**: savage, but still no slurs, abuse, or personal attacks
- Roast the **news, situation, and public figures' public actions**, never private individuals.

### Content Safety Rules
- Run OpenAI Moderation on the article text **before** generation and on the roast **after**.
- Refuse (`status: refused`) for: death, accidents, disasters, violence, suicide, sexual violence,
  crimes involving minors, caste, and religious/communal conflict.
- Refusals return a playful Tanglish message (e.g. *"Idhu roast panna vendiya news illa machan 🙏"*).
- Article text is **untrusted input**. Wrap it in clear delimiters and instruct the model to
  ignore any instructions inside it.

### Scraper Rules (SSRF)
- Allow only `http` / `https` schemes.
- Resolve DNS and block private, loopback, link-local, reserved, and cloud-metadata IPs.
- Re-validate the target on every redirect (max 3).
- 10s timeout, 2 MB max response, `text/html` content type only.
- Extract with `trafilatura`; if there's no usable text, return 422.

### Rate Limiting
- Anonymous: 5 roasts / hour / IP. Signed-in: 20 roasts / hour / user.
- Global daily OpenAI call cap via `DAILY_ROAST_LIMIT`.
- 429 responses include a funny Tanglish message and a `Retry-After` header.

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Use plural nouns for resources: `/roasts`
- Return appropriate HTTP status codes:
  - 200: Success (incl. cached roast)
  - 201: Created
  - 400: Bad Request (invalid / blocked URL)
  - 401: Unauthorized
  - 403: Forbidden (not owner)
  - 404: Not Found
  - 422: Unprocessable (article could not be extracted)
  - 429: Too Many Requests
  - 502: Upstream failure (news site or OpenAI)

---

## Authentication

### JWT Configuration
- Access token expires: 30 minutes
- Refresh token expires: 7 days (stored hashed, rotated on refresh)
- Algorithm: HS256

### OAuth Providers
- Google OAuth 2.0 enabled (only sign-in method)
- Always verify the `state` parameter for CSRF protection

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/roast_news

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Limits & safety
RATE_LIMIT_ANON=5/hour
RATE_LIMIT_USER=20/hour
DAILY_ROAST_LIMIT=1000
ROAST_CACHE_HOURS=24
IP_HASH_SALT=change-me

# Frontend
FRONTEND_URL=http://localhost:5173
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Docker
docker-compose up -d

# Tests (OpenAI + outbound HTTP must be mocked)
pytest backend/tests -v
cd frontend && npm test

# Linting
ruff check backend/
cd frontend && npm run lint && npm run type-check
```

---

## Commit Message Format

```
feat(roast): add spice level selector
fix(scraper): block redirect to private IP
refactor(auth): extract optional user dependency
test(safety): add refusal cases for tragedy news
docs: update README
```

---

## Skills Reference

| Task | Skill to Read |
|------|---------------|
| Database models | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Deployment | skills/DEPLOYMENT.md |

---

## Agent Coordination

For complex tasks, the ORCHESTRATOR (`agents/ORCHESTRATOR.md`) coordinates:
- DATABASE-AGENT → User, RefreshToken, Roast models + migrations
- BACKEND-AGENT → Auth, scraper, safety, roast services, rate limiting
- FRONTEND-AGENT → Home, permalink, My Roasts pages, share actions
- DEVOPS-AGENT → Docker + CI/CD

Read agent definitions in the `agents/` folder.
