# CLAUDE.md - Movie Roast Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** Movie Roast (movieroast.live)
**Description:** Search any movie (TMDB, Tamil films first) and get a funny Tanglish (Tamil + English) roast of it with a reaction GIF (GIPHY). Free and public; Google sign-in is optional.
**History:** started as "Roast News" (news URL -> roast); pivoted to movies on 2026-10-10. INITIAL.md and PRPs/ describe the original news version.
**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TypeScript
- Database: PostgreSQL + SQLAlchemy + Alembic
- Auth: Anonymous by default + optional Google OAuth (JWT)
- UI: Chakra UI + Framer Motion
- AI: OpenAI GPT (generation + Moderation API), default model gpt-4.1
- Data: TMDB API (movie search + details), GIPHY API (reaction GIFs, optional)

---

## Project Structure

```
movie-roast/
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
│   │   │   ├── movies.py            # GET /movies/search
│   │   │   └── roasts.py
│   │   ├── services/
│   │   │   ├── tmdb_client.py       # ONLY module that calls TMDB (search, details, TTL cache)
│   │   │   ├── gif_client.py        # ONLY module that calls GIPHY (never raises)
│   │   │   ├── llm_client.py        # ONLY module that calls OpenAI
│   │   │   ├── safety_service.py    # Sensitive-film check + output moderation
│   │   │   ├── roast_service.py     # Orchestration + caching
│   │   │   └── prompts/
│   │   │       └── roast_system.md  # Tanglish style guide, spice rules, GIF moods
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
│   │   ├── components/   # movie/ (MovieSearch, MoviePoster), roast/ (RoastForm, RoastCard, RoastGifBox, ...)
│   │   ├── pages/        # HomePage, RoastPage, MyRoastsPage, AuthCallbackPage
│   │   ├── hooks/        # useRoast, useMovieSearch, useAuth
│   │   ├── services/     # api.ts, roastService.ts, movieService.ts, authService.ts
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
    Load the movie from TMDB, run safety checks, and generate a Tanglish roast.

    Args:
        db: Database session
        data: Roast request (tmdb_id, spice_level)
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

// API JSON is snake_case and the types mirror it exactly (see src/types/roast.ts).
interface Movie {
  tmdb_id: number;
  title: string;
  year: number | null;
  original_language: string;
  poster_url: string | null;
}

interface Roast {
  id: string;
  movie: Movie;
  spice_level: SpiceLevel;
  roast_text: string | null;
  gif: { url: string; page_url: string } | null;
  status: RoastStatus;
  refusal_reason: string | null;
  created_at: string;
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
- ❌ Never call OpenAI, TMDB or GIPHY outside `llm_client` / `tmdb_client` / `gif_client`
- ❌ Never call OpenAI directly from routers - go through `roast_service` / `safety_service`
- ❌ Never store raw client IPs - salted hash only
- ❌ Never log API keys or full prompts

### Frontend
- ❌ Never use `any` type
- ❌ Never leave console.log in production
- ❌ Never skip error handling in async operations (handle 400 / 422 / 429 / refused)
- ❌ Never use inline styles - use Chakra UI props/theme
- ❌ Never render roast or movie text with `dangerouslySetInnerHTML`

---

## Module-Specific Rules

### Authentication Module
- Login is **optional**. Roast endpoints must work for anonymous users.
- Use `get_optional_user` on public endpoints and `get_current_user` on protected ones.
- No email/password auth; Google OAuth is the only sign-in method.

### Roast Generator Module
- Input is a TMDB movie id (`POST /api/v1/roasts {tmdb_id, spice_level}`), picked via `GET /api/v1/movies/search?q=`
- Search ranking: exact title > title prefix > other; ties broken Tamil > other Indian languages > rest
- `spice_level` must be one of: `mild`, `medium`, `extra_spicy`
- `status` must be one of: `completed`, `refused`, `failed`
- Roast IDs are UUIDs (permalinks must not be enumerable)
- `user_id` is nullable (anonymous roasts); only the owner may delete a roast
- Cache: the same `(tmdb_id, spice_level)` within 24h returns the existing completed roast
- Roast rows snapshot the movie (title, year, language, poster path) and the GIF (url + GIPHY page)
- Generation uses Structured Outputs: `{refuse, lines[4-6], gif_mood}`; `gif_mood` is one of `llm_client.GIF_MOODS`
- GIFs are decoration: GIPHY failures or a missing key just mean no GIF; always credit GIPHY in the UI
- Credit TMDB in the UI ("uses the TMDB API but is not endorsed or certified by TMDB")

### Tanglish Style Rules (for prompts)
- Output = Tamil words in **Latin script** mixed naturally with English. Never Tamil script, never pure English.
- Use common slang naturally: *enna da, semma, vera level, mokka, ayyo, machan, scene-u, gethu, kalaai*.
- Spice levels:
  - **mild**: light teasing, friendly uncle-at-tea-shop energy
  - **medium**: sarcastic, meme-style punchlines
  - **extra_spicy**: savage, but still no slurs, abuse, or personal attacks
- Roast the **movie**: plot, logic holes, tropes, runtime, tagline, and cast/crew's *on-screen work* only.
- Never joke about anyone's looks, family, personal life, caste, religion, politics, or fans.

### Content Safety Rules
- Before generation, a classifier refuses films that dramatize a REAL tragedy (disasters, massacres,
  terror attacks, real victims' deaths) or centre on suicide, sexual violence, harm to children,
  caste, or religious/communal conflict. Fictional action/crime/war/horror is fine.
- The model can also refuse (`refuse: true`); the roast is moderated (OpenAI Moderation) after generation.
- Refusals return a playful Tanglish message (e.g. *"Idhu roast panna vendiya padam illa machan 🙏"*).
- TMDB text is crowd-edited **untrusted input**: wrap it in `<movie>` delimiters and instruct the
  model to ignore any instructions inside it. Adult titles are excluded from search and roasts.

### Rate Limiting
- Anonymous: 5 roasts / hour / IP. Signed-in: 20 roasts / hour / user. Search: 60 / minute.
- Global daily OpenAI call cap via `DAILY_ROAST_LIMIT`.
- 429 responses include a funny Tanglish message and a `Retry-After` header.

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Use plural nouns for resources: `/roasts`
- Return appropriate HTTP status codes:
  - 200: Success (incl. cached roast)
  - 201: Created
  - 400: Bad Request
  - 401: Unauthorized
  - 403: Forbidden (not owner)
  - 404: Not Found (roast, or unknown/adult TMDB id)
  - 422: Unprocessable (validation, or too little TMDB info to roast)
  - 429: Too Many Requests
  - 502: Upstream failure (TMDB or OpenAI)

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
DATABASE_URL=postgresql://user:password@localhost:5432/roast_news  # DB name kept from v1

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
OPENAI_MODEL=gpt-4.1

# TMDB (required) / GIPHY (optional)
TMDB_API_KEY=your-tmdb-v3-key-or-v4-read-token
GIPHY_API_KEY=
RATE_LIMIT_SEARCH=60/minute

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

# Tests (OpenAI, TMDB, GIPHY must be mocked)
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
fix(search): rank exact title matches first
refactor(auth): extract optional user dependency
test(safety): add refusal cases for real-tragedy films
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
