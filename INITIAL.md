# INITIAL.md - Roast News Product Definition

> Paste any news URL and get a hilarious roast of it in Tanglish (Tamil + English).

---

## PRODUCT

### Name
Roast News

### Description
Roast News takes a news article URL, extracts the headline and story, and generates a funny,
savage-but-harmless roast in **Tanglish**: Tamil written in Latin script, mixed with English
(e.g. *"Enna da idhu, vera level mokka news!"*). Users pick a spice level (Mild / Medium /
Extra Spicy), get their roast instantly, and can copy it or share it to WhatsApp / X via a
permalink. Anyone can use it without an account. Signing in with Google is optional and
only adds a personal roast history.

The roast targets the **news and the situation**, never vulnerable people. A safety layer
refuses tragedies and sensitive topics with a playful Tanglish message instead of a roast.

### Target User
The general public, especially Tamil-speaking internet users who enjoy meme culture and
want to laugh at (and share) the day's headlines. No signup required.

### Type
- [x] SaaS (Software as a Service), free and public

---

## TECH STACK

### Backend
- [x] FastAPI + Python 3.11+

### Frontend
- [x] React + Vite + TypeScript

### Database
- [x] PostgreSQL + SQLAlchemy + Alembic

### Authentication
- [x] Anonymous by default + optional Google OAuth (JWT sessions)

### UI Framework
- [x] Chakra UI (+ Framer Motion for roast reveal animation)

### AI
- [x] OpenAI GPT (Chat Completions + Moderation API)

### Payments
- [ ] None (free product)

---

## MODULES

### Module 1: Authentication (Optional Google sign-in)

**Description:** Users can use the app anonymously. Optional Google sign-in links roasts
to a user so they can see their history. There is no email/password login.

**Models:**
- User: id, email (unique), full_name, avatar_url, google_id (unique), is_active, created_at, updated_at
- RefreshToken: id, user_id (FK), token_hash, expires_at, revoked, created_at

**API Endpoints:**
- GET  /api/v1/auth/google - Redirect to Google consent screen (sets `state` for CSRF)
- GET  /api/v1/auth/google/callback - Verify state, exchange code, upsert user, issue tokens
- POST /api/v1/auth/refresh - Rotate refresh token, return new access token
- POST /api/v1/auth/logout - Revoke refresh token
- GET  /api/v1/auth/me - Current user profile

**Frontend Pages / UI:**
- "Sign in with Google" button in navbar (no separate register page)
- /auth/callback - Handles OAuth redirect, stores session, returns to previous page
- User avatar menu: My Roasts, Sign out

---

### Module 2: Roast Generator (Core)

**Description:** The user submits a news URL and a spice level. The backend fetches the page
safely, extracts the article title and body, runs safety checks, and asks OpenAI for a
Tanglish roast. The roast is stored with a shareable permalink.

**Models:**
- Roast:
  - id: UUID (primary key, non-guessable, used in permalink)
  - user_id: int | null (FK → users.id, null for anonymous)
  - source_url: str (as submitted, max 2048)
  - url_hash: str (sha256 of normalized URL, indexed, used for caching)
  - source_domain: str (e.g. `thehindu.com`)
  - article_title: str
  - article_excerpt: str (first ~300 chars, for display/context only)
  - spice_level: enum `mild | medium | extra_spicy`
  - roast_text: str | null
  - status: enum `completed | refused | failed`
  - refusal_reason: str | null (e.g. `tragedy`, `moderation_flagged`, `unreadable_page`)
  - model: str (OpenAI model used)
  - client_ip_hash: str (salted hash, for rate limiting/abuse only, never raw IP)
  - created_at

**Services:**
- `scraper_service`: fetch URL with httpx (timeout 10s, max 2 MB, ≤3 redirects) and extract
  the main text with `trafilatura`. Applies SSRF protection (see Security).
- `safety_service`: OpenAI Moderation on article text **and** generated roast, plus a
  sensitive-topic check (death, disasters, accidents, sexual violence, minors, caste,
  religion/communal conflict, suicide). Sensitive → `refused` with a friendly message.
- `roast_service`: builds the prompt (system prompt with Tanglish style guide + spice level
  rules) and calls OpenAI. Caches by (url_hash, spice_level) for 24h.

**API Endpoints:**
- POST   /api/v1/roasts - Body `{ url, spice_level }` → 201 with Roast (or cached roast, 200)
- GET    /api/v1/roasts/{id} - Public permalink fetch
- GET    /api/v1/roasts/me - Paginated history of the signed-in user's roasts (auth required)
- DELETE /api/v1/roasts/{id} - Owner deletes their roast (auth required)

**Frontend Pages:**
- / - Home: URL input, spice level selector (🌶 / 🌶🌶 / 🌶🌶🌶), "Roast Pannu!" button,
  loading state with fun Tanglish messages, animated roast result card
- /roast/:id - Permalink page showing article title, source, spice, and roast, with share buttons
- /my-roasts - History list for signed-in users (protected)

**Roast Result Card actions:**
- Copy to clipboard (roast + permalink)
- Share to WhatsApp (`https://wa.me/?text=...`)
- Share to X (`https://twitter.com/intent/tweet?text=...`)
- "Roast another one" reset

---

## MVP SCOPE

### Must Have (MVP)
- [x] URL → Tanglish roast (scrape article + OpenAI generation)
- [x] Spice level selector (Mild / Medium / Extra Spicy)
- [x] Save every roast with a public permalink
- [x] Copy / share roast (clipboard, WhatsApp, X)
- [x] Rate limiting (anonymous per-IP + signed-in per-user)
- [x] Safety filter (moderation + sensitive-topic refusal)
- [x] Optional Google sign-in + "My Roasts" history

### Nice to Have (Post-MVP)
- [ ] Public roast feed / gallery with upvotes
- [ ] Shareable image cards (OG image per roast for rich WhatsApp/X previews)
- [ ] Roast length option (one-liner vs full roast)
- [ ] Admin panel to moderate/delete reported roasts
- [ ] Analytics dashboard (roasts/day, top news sources)
- [ ] "Report this roast" button
- [ ] Other languages (Hinglish, Manglish, Tenglish)
- [ ] Paid Pro tier (higher limits)

---

## ACCEPTANCE CRITERIA

### Authentication
- [ ] Anonymous users can generate roasts without signing in
- [ ] User can sign in with Google; OAuth `state` is verified
- [ ] JWT access + refresh tokens work, including refresh rotation and logout revocation
- [ ] /my-roasts redirects anonymous users to sign in
- [ ] Roasts created while signed in are linked to that user

### Roast Generator
- [ ] Submitting a valid news URL returns a Tanglish roast within ~15 seconds
- [ ] Mild, Medium and Extra Spicy produce noticeably different intensity
- [ ] Roast output is Tamil-in-Latin-script mixed with English (no Tamil script, no pure English)
- [ ] The same URL + spice within 24h returns the cached roast (no new OpenAI call)
- [ ] Invalid URLs, non-http(s) schemes, and private/internal IPs are rejected with 400
- [ ] Pages with no extractable article return a friendly 422 error
- [ ] Sensitive news (death, disaster, communal, etc.) returns `status: refused` with a playful refusal message, not a roast
- [ ] Generated roasts that fail moderation are never shown or stored as `completed`
- [ ] Each roast has a working /roast/:id permalink viewable by anyone
- [ ] Copy, WhatsApp share, and X share work on mobile and desktop
- [ ] Owners can delete their own roasts; others get 403/404

### Rate Limiting
- [ ] Anonymous: max 5 roasts per hour per IP → 429 with Tanglish message
- [ ] Signed-in: max 20 roasts per hour per user
- [ ] Global daily cap on OpenAI calls (configurable) protects the budget

### Quality
- [ ] All API endpoints documented in OpenAPI
- [ ] Backend test coverage 80%+ (OpenAI and HTTP fetching mocked)
- [ ] Frontend TypeScript strict mode passes
- [ ] Mobile-first responsive UI
- [ ] Docker builds and runs successfully

---

## SPECIAL REQUIREMENTS

### Security
- [x] Rate limiting on roast and auth endpoints (slowapi)
- [x] Input validation on all endpoints (Pydantic `HttpUrl`, max length 2048)
- [x] **SSRF prevention**: http/https only; resolve DNS and block private, loopback,
      link-local, and metadata IPs (e.g. 169.254.169.254); re-validate on every redirect
- [x] Fetch limits: 10s timeout, 2 MB max body, `text/html` only
- [x] SQL injection prevention (SQLAlchemy ORM only)
- [x] XSS prevention: roast and article text rendered as plain text, never as HTML
- [x] CSRF protection via OAuth `state` parameter
- [x] Prompt-injection hardening: article text passed as clearly delimited data and
      treated as untrusted; the system prompt forbids following instructions inside it
- [x] Raw IPs never stored (salted hash only)

### Content Safety
- [x] Roast the news, situation, and public figures' public actions, never private individuals
- [x] No slurs or attacks on caste, religion, gender, sexuality, disability, or appearance
- [x] Refuse tragedies (deaths, accidents, disasters, violence, suicide, crimes against minors)
- [x] Moderation check on both input article and output roast

### Integrations
- [x] OpenAI API (roast generation + moderation)
- [x] Google OAuth 2.0
- [ ] Email service (not needed)
- [ ] Payments (not needed)
- [ ] File uploads (not needed)

---

## AGENTS

> These agents build the product in parallel, coordinated by `agents/ORCHESTRATOR.md`:

| Agent | Role | Works On |
|-------|------|----------|
| DATABASE-AGENT | Creates all models and migrations | User, RefreshToken, Roast |
| BACKEND-AGENT | Builds API endpoints and services | Auth, scraper, safety, roast, rate limiting |
| FRONTEND-AGENT | Creates UI pages and components | Home, permalink, My Roasts, share actions |
| DEVOPS-AGENT | Sets up Docker, CI/CD, environments | Infrastructure (see `skills/DEPLOYMENT.md`) |

---

# READY?

```bash
/generate-prp INITIAL.md
```

Then:

```bash
/execute-prp PRPs/roast-news-prp.md
```
