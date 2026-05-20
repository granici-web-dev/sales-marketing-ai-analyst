# Security and Privacy Policy

> This document describes security practices and GDPR compliance for the Sales & Marketing AI Analyst platform.

## 1. Data Classification

The platform processes the following types of data:

### Customer PII (highest sensitivity)
- Customer names, phone numbers, email addresses
- Call transcripts and summaries
- Sales conversation history

**Origin:** From client's MEFI CRM (the client is the Data Controller)
**Our role:** Data Processor under GDPR Art. 28

### Business data (high sensitivity)
- Revenue, deal sizes, conversion rates
- Ad spend across Meta/Google/TikTok
- Salesperson performance metrics

### Operational data (medium sensitivity)
- API credentials (OAuth tokens, API keys)
- User accounts of our platform
- System logs (without PII)

### Public data (low sensitivity)
- Aggregated benchmarks (future, anonymized)
- Documentation, marketing materials

---

## 2. GDPR Compliance

### Legal basis
- We act as **Data Processor**, our clients act as **Data Controllers**.
- A signed **Data Processing Agreement (DPA)** is required with every client before processing their data.

### Data residency
- All data is stored on servers physically located in the European Union:
  - Production: Hetzner (Germany) or Unihost (Romania)
  - Backups: same region as production
- No data leaves the EU.

### Retention
- Customer data is retained while the client's subscription is active.
- Upon subscription termination: hard delete within 90 days.
- Audit logs retained for 1 year (no customer PII in audit logs).

### Right to be forgotten
- API endpoint: `DELETE /api/v1/tenants/{tenant_id}/customer-data?phone=...`
- The endpoint immediately removes all records matching the given customer identifier.
- Action is logged in `audit_log` (which contains no customer PII itself).

### Data Subject Access Requests
- Clients (Data Controllers) handle DSAR requests from their customers.
- We provide clients with a CSV export of all data we hold about a given customer.

### Sub-processors
- Anthropic (Claude API) — for AI insights generation
  - Note: We send aggregated business metrics only, NEVER customer PII or call transcripts
- Sentry — error tracking (no PII in error reports)
- Hetzner / Unihost — hosting

A list of all sub-processors will be maintained in `docs/SUBPROCESSORS.md` (to be created).

---

## 3. Technical Security Measures

### Encryption
- **In transit:** TLS 1.3 mandatory for all endpoints (Caddy + Let's Encrypt)
- **At rest:**
  - Disk-level encryption (LUKS) on production servers
  - API credentials in DB encrypted with Fernet (AES-128)
  - PostgreSQL connections over TLS

### Authentication
- User authentication: JWT with RS256 in production, HS256 in development
- Tokens expire in 24 hours, refresh tokens in 30 days
- Password requirements: minimum 12 characters, argon2id hashing
- No password reuse, no common passwords (zxcvbn check)

### Authorization
- Role-based access control: `owner`, `analyst`, `admin`
- Multi-tenant isolation enforced at SQLAlchemy event listener level
- Every DB query MUST filter by `tenant_id` (enforced at code review)

### API security
- Rate limiting on all public endpoints (default: 60 req/min per IP)
- CORS strictly configured (only frontend domain allowed)
- CSP headers via Caddy
- SQL injection prevention via SQLAlchemy ORM (no raw queries except in audited places)
- Pydantic validation on all inputs

### Secrets management
- All secrets in environment variables (never in code)
- `.env` files never committed to git
- Pre-commit hook `gitleaks` to catch accidental secret commits
- Production secrets managed via Docker secrets or external secret manager

### Logging
- Structured JSON logs via `structlog`
- **No PII in logs ever** — automated tests verify this
- Sensitive fields filtered: phone numbers, emails, names, transcripts, credentials
- Logs retained for 30 days

### Monitoring
- Sentry for error tracking (PII scrubbed before send)
- Health checks on all services
- Alerts for: failed integrations, anomalous error rates, slow queries

---

## 4. Sub-processor: Anthropic Claude API

When generating AI insights, we send the following to Anthropic:
- Aggregated metrics (counts, sums, averages, percentages)
- Detected problem descriptions (without customer PII)
- Business context (industry, company size — not customer data)

We **DO NOT** send:
- Customer names, phone numbers, emails
- Individual call transcripts or summaries
- Any individual customer's data

Anthropic's data processing terms: https://www.anthropic.com/legal/aup
- API requests are not used to train models (by default for API customers)
- Anthropic acts as our Sub-processor

---

## 5. Incident Response

### Detection
- Sentry alerts for unhandled exceptions
- Failed login attempts monitored
- Anomalous API usage triggers alerts

### Response
- Severity 1 (data breach): within 1 hour
- Severity 2 (service down): within 4 hours
- Severity 3 (degraded service): within 24 hours

### GDPR breach notification
- If a personal data breach occurs: notify clients (Data Controllers) within 72 hours
- Clients then notify their data subjects as required by law

---

## 6. Reporting a Security Issue

If you discover a security vulnerability, please **DO NOT** open a public GitHub issue.

Instead, email: **security@[your-domain].com** (replace with your actual email)

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Your contact information

We aim to respond within 48 hours.

---

## 7. Compliance Checklist (for production launch)

- [ ] DPA template prepared by legal counsel
- [ ] DPA signed with every client before processing their data
- [ ] All servers physically in EU
- [ ] TLS 1.3 active on all endpoints
- [ ] LUKS encryption on production disks
- [ ] All API credentials encrypted in DB (Fernet)
- [ ] No PII in logs (verified by automated tests)
- [ ] Audit log functional and reviewed
- [ ] Right to be forgotten endpoint tested
- [ ] Sub-processors documented in `docs/SUBPROCESSORS.md`
- [ ] Privacy Policy published on website
- [ ] Terms of Service published
- [ ] Cookie policy (for marketing website, if applicable)
- [ ] Data Protection Impact Assessment (DPIA) completed
- [ ] Incident response procedure documented
- [ ] Backup and disaster recovery tested
- [ ] Security audit by external party (recommended before scaling)

---

## 8. References

- [GDPR full text](https://gdpr-info.eu/)
- [GDPR Art. 28 — Processor obligations](https://gdpr-info.eu/art-28-gdpr/)
- [Romanian DPA (ANSPDCP)](https://www.dataprotection.ro/)
- [Anthropic Data Processing Terms](https://www.anthropic.com/legal/aup)
