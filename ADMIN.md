# Admin Panel Guide

All admin endpoints require `role == "admin"` (`routes/accounting.py::_admin`). Unauthorized = 403.

---

## Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/auth/status | Check current role |
| POST | /api/auth/login | Exchange credentials |
| POST | /api/auth/logout | Revoke session |

## User Management (WorkOS)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/workos/admin/users | List users |
| POST | /api/workos/admin/users | Invite (email, role) |
| POST | /api/workos/admin/users/delete | Delete user |
| POST | /api/workos/admin/users/role | Update role |

**Roles:** admin > user > viewer

---

## RAG Admin

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/rag/documents | List documents |
| POST | /api/rag/admin/add | Upload document |
| POST | /api/rag/admin/delete | Delete document |
| POST | /api/rag/admin/rebuild | Rebuild FAISS index |

## Accounting

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/accounting/summary | Usage summary |
| GET | /api/accounting/invoices | List invoices |
| POST | /api/accounting/invoices | Create invoice |
| GET | /api/accounting/usage | Token usage |
| GET | /api/accounting/limits | Quota status |

## Security & Recon Guard

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/security/recon-guard | Hit counters |
| POST | /api/security/recon-guard/reset | Clear counters |
| GET | /api/audit/chain | Inspect audit chain |
| GET | /api/audit/verify | Verify integrity |

---

## System Monitoring

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health/ready | Readiness probe |
| GET | /health/live | Liveness probe |
| GET | /metrics | Metrics |
| GET | /api/local-model/status | Local LLM status |
| GET | /api/embedder/status | Embedder status |

Admin dashboard: `/status`

## Related Documentation

- [SECURITY.md](./SECURITY.md) - Compliance & SOC 2 roadmap
- [workflow.md](./workflow.md) - Dev & deploy workflow
- [resume.md](./resume.md) - Version history

*Last updated: 2026-11-07 - v1.10.0*

