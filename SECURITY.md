# Security & Compliance

Sunnyware is built with defense-in-depth controls aligned with **SOC 2 Trust Services Criteria**.

> **Status:** Controls implemented. **Formal SOC 2 / HIPAA certification NOT yet obtained.**

---

## Implemented Security Controls

### Authentication & Identity

| Control | Implementation |
|---|---|
| Identity provider | WorkOS AuthKit + Google SSO |
| Multi-factor auth | TOTP 2FA for admin roles |
| Session management | Signed HTTP-only cookies + short-lived API keys |
| Password policy | Delegated to WorkOS (SSO-only) |

### Authorization & Access

| Control | Implementation |
|---|---|
| Role model | admin / user / viewer |
| API key scopes | Per-key role lookup |
| Admin surfaces | /api/accounting/*, /api/rag/admin/*, /api/workos/admin/* |
| Tenant isolation | Per-workspace sandboxing |

### Monitoring & Detection

| Control | Implementation |
|---|---|
| Intrusion detection | Recon Guard - 34-pattern matcher |
| Audit trail | Audit Chain - append-only (1,484 entries) |
| System monitoring | system_monitor.py - 95.5/100 Grade A+ |
| Provider health | Circuit breaker + quota tracker |

### Data Protection

| Control | Implementation |
|---|---|
| Encryption in transit | TLS 1.2+ (Hugging Face edge) |
| Encryption at rest | Neon Postgres AES-256 |
| Secrets management | Encrypted HF secrets; .env untracked |
| Sandboxing | python_eval, sql_sandbox isolated |

### Change Management

| Control | Implementation |
|---|---|
| Pre-push gate | pre_push_check.py |
| CI pipeline | GitHub Actions - pytest 326+ passed |
| Release discipline | Semantic versioning v1.0.0 to v1.10.0 |
| Rollback | git reset --hard v1.x.x |

### Input Validation

| Control | Implementation |
|---|---|
| URL scheme validation | Non-http(s) rejected |
| Timeout budgets | 25s click, 40s fill/submit |
| HTML sanitization | Markdown-only rendering |
| SQL injection | Parameterized queries only |

---

## Explicitly NOT Certified

| Standard | Status | Notes |
|---|---|---|
| SOC 2 Type I | Not obtained | Readiness Q1 2027 |
| SOC 2 Type II | Not obtained | Audit Q2 2027 |
| HIPAA | Not certified | BAA available on request |
| ISO 27001 | Not pursued | Out of scope |
| PCI DSS | Not applicable | No card data stored |

**We do not claim any certification we have not earned.**

---

## Compliance Roadmap

| Quarter | Milestone | Deliverable |
|---|---|---|
| Q4 2026 | Security documentation | This SECURITY.md |
| Q1 2027 | SOC 2 readiness | Control mapping |
| Q2 2027 | SOC 2 Type I audit | CPA report |
| Q3 2027 | SOC 2 Type II audit | 6-month window |
| Q4 2027 | HIPAA gap assessment | BAA templates |

---

## Responsible Disclosure

If you discover a security vulnerability, **please do not open a public GitHub issue.**

- **Email:** shamiur@engineer.com, shamiur.sunny@gmail.com
- **Response time:** within 48 hours
- **Scope:** Sunnyware application, API, Hugging Face Space
- **Out of scope:** Social engineering, physical attacks, third parties

---

## Current Posture Snapshot

Reproduced from system_monitor.py (last run 2026-11-07):

Security checks:
  [PASS] .env NOT tracked in git
  [PASS] Sandbox runtime present
  [PASS] No hardcoded API keys in source
  [PASS] 34-pattern Recon Guard active
  [PASS] Audit Chain OK (1,484 entries)
  [PASS] Role-based admin enforcement

**Overall system score: 95.5 / 100 (Grade A+)**

---

*Last updated: 2026-11-07 - v1.10.0*

