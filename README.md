# Sales & Marketing AI Analyst

> AI-аналитик маркетинга и продаж для румынского SMB на базе MEFI CRM.

Платформа собирает данные из MEFI CRM, рекламных систем (Meta, Google, TikTok Ads) и веб-аналитики (GA4, Search Console), строит дашборды и **раз в день генерирует AI-инсайты** через Claude Sonnet 4.5 — с конкретным планом действий на румынском языке.

**Status:** 🚧 In development (Pre-MVP)
**Pilot client:** Sofa Belle (premium furniture, Romania)

---

## Quick Links

- 📖 [SPEC.md](./SPEC.md) — Full product specification
- 🎯 [PRODUCT.md](./PRODUCT.md) — Whose cabinet this is, and what it promises
- 🎨 [DESIGN.md](./DESIGN.md) — Tokens, themes and the rules behind them
- 🤖 [CLAUDE.md](./CLAUDE.md) — Instructions for Claude Code
- 🏗️ [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — System architecture
- 💻 [docs/STACK.md](./docs/STACK.md) — Tech stack details
- 📋 [docs/CONVENTIONS.md](./docs/CONVENTIONS.md) — Coding conventions
- 🏠 [docs/SOFABELLE.md](./docs/SOFABELLE.md) — Pilot client context
- 🔌 [docs/INTEGRATIONS.md](./docs/INTEGRATIONS.md) — External integrations
- 🔒 [SECURITY.md](./SECURITY.md) — Security & GDPR policy

---

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose v2
- Python 3.11+ (for local development without Docker)
- Node.js 20+ and pnpm 10+ for frontend development. Which pnpm you get is not
  your choice to make: `frontend/package.json` declares it under
  `packageManager`, and pnpm 10 switches itself to that version on every
  command — including downwards, for repositories still on 9. So any pnpm 10+
  will do, however you install it (`npm i -g pnpm`, `corepack enable pnpm`,
  brew). Pinning the version by hand in three places is how this project ended
  up running three of them.
- An Anthropic API key
- (Eventually) Access to: MEFI API, Meta Business Manager, Google Ads, TikTok for Business, GA4, Search Console

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/granici-web-dev/sales-marketing-ai-analyst
cd sales-marketing-ai-analyst

# Copy environment variables
cp .env.example .env
# Fill in the values in .env (see comments in the file)

# Generate secrets
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
python3 -c "from cryptography.fernet import Fernet; print(f'FERNET_KEY={Fernet.generate_key().decode()}')" >> .env

# Start all services
docker compose up -d

# Run database migrations
docker compose exec backend alembic upgrade head

# Link the client to its engine tenant — without this nobody can log in
docker compose exec backend python -m app.cli tenants list
docker compose exec backend python -m app.cli tenants link <slug> <engine-tenant-uuid>
```

### Linking a client

Identity comes from the engine (assistwidget); the analyst has no login of its
own. A client reaches the cabinet only once `tenants.engine_tenant_id` points at
their engine tenant, and nothing sets that automatically — an analyst tenant with
no CRM sync is an empty cabinet, and creating one on first login would let
somebody in to guess whether it is broken.

Get the engine tenant id with `npm run client list` in the engine repository,
then:

```bash
python -m app.cli tenants list                      # who is linked, who is not
python -m app.cli tenants link <slug> <uuid>        # link
python -m app.cli tenants link <slug> <uuid> --force  # move an existing link
python -m app.cli tenants unlink <slug>             # revoke access
```

The command refuses to point one engine tenant at two clients, and refuses to
move an existing link without `--force`: a moved link sends whoever logs in next
into somebody else's data. On startup the backend logs how many tenants are
still unlinked — a client who cannot log in should be visible before they call.

The application will be available at:

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API docs (Swagger):** http://localhost:8000/docs

---

## Development

See [CLAUDE.md](./CLAUDE.md) for detailed development commands and conventions.

### Working with Claude Code

This project uses [GSD (Get Shit Done)](https://github.com/gsd-build/get-shit-done) — a spec-driven development system for Claude Code.

```bash
# Install GSD (once per machine)
npx get-shit-done-cc@latest

# Start Claude Code with GSD enabled
claude --dangerously-skip-permissions

# Initialize project planning (first time)
/gsd-new-project

# Work on a phase
/gsd-discuss-phase 1
/gsd-plan-phase 1
/gsd-execute-phase 1
/gsd-verify-work 1
/gsd-ship 1
```

The full specification is in [SPEC.md](./SPEC.md). GSD will read it and create the planning artifacts (`PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `CONTEXT.md`).

---

## Project Structure

```
sales-marketing-ai-analyst/
├── SPEC.md                  # Full product specification
├── CLAUDE.md                # Claude Code instructions
├── README.md                # This file
├── SECURITY.md              # GDPR/security policy
├── .env.example
├── docker-compose.yml
├── docker-compose.prod.yml
│
├── docs/                    # Detailed documentation
│   ├── ARCHITECTURE.md
│   ├── STACK.md
│   ├── CONVENTIONS.md
│   ├── SOFABELLE.md
│   └── INTEGRATIONS.md
│
├── backend/                 # Python FastAPI backend
├── worker/                  # Celery workers (если выделим отдельно)
├── frontend/                # Next.js frontend
├── infra/                   # Infrastructure configs
└── tests/                   # E2E tests
```

---

## Roadmap

The product is built **iteratively**:

| Iteration      | Scope                                                       | Status     |
| -------------- | ----------------------------------------------------------- | ---------- |
| **MVP1**       | MEFI only — Sales Dashboard + basic Marketing + AI Insights | ⏳ Planned |
| **MVP2**       | + Meta Ads + Google Ads + TikTok Ads                        | ⏳ Future  |
| **MVP3**       | + GA4 + Google Search Console                               | ⏳ Future  |
| **Production** | Multi-tenant, billing, Romanian hosting                     | ⏳ Future  |

See [SPEC.md section 2](./SPEC.md#2-roadmap-по-итерациям) for details.

---

## License

Proprietary. All rights reserved.

---

## Contact

[Your contact info here]
