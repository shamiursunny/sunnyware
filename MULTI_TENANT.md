# Multi-Tenant Architecture

Sunnyware is built as a **true multi-tenant SaaS application** from the ground up. Every user, organization, and workspace is logically isolated, resource-governed, and independently authenticated.

## Tenant Isolation Model

| Layer | Isolation Mechanism |
|---|---|
| **Identity** | WorkOS AuthKit maps every user to an `org_id` and `user_id`. |
| **Data (RAG)** | Vector indices are partitioned by `org_id`. Cross-tenant retrieval is impossible. |
| **Workspace** | File system sandbox is scoped to `/data/workspace/{org_id}/{user_id}/`. |
| **Memory** | Conversation history is keyed by `(org_id, session_id)`. |
| **Secrets** | Provider API keys and limits are stored per-tenant in `provider_limits.json`. |

## Role-Based Access Control (RBAC)

| Role | Scope | Permissions |
|---|---|---|
| **Owner** | Org-level | Billing, user management, API key rotation, full data access. |
| **Admin** | Org-level | Manage users, view audit logs, configure SSO, access all workspaces. |
| **User** | Workspace-level | Run tools, upload documents to own workspace, view own history. |
| **Viewer** | Workspace-level | Read-only access to shared dashboards and reports. |

## Resource Governance & Quotas

Sunnyware enforces per-tenant limits to prevent noisy-neighbor problems:

- **Token budgets:** Daily/monthly limits per provider (Groq, Gemini, etc.) tracked in `provider_limits.json`.
- **Tool execution caps:** Max 100 browser operations per org per hour.
- **Storage quotas:** 1 GB RAG index per tenant (configurable by plan).
- **Rate limiting:** 60 requests/minute per API key, 1,000/day per tenant.

## Enterprise SSO & Provisioning

- **SSO:** WorkOS AuthKit supports SAML 2.0 / OIDC with Google, Okta, Azure AD, and generic IdPs.
- **SCIM:** Automated user provisioning and de-provisioning (roadmap Q1 2027).
- **Audit Logs:** Every admin action is written to the immutable Audit Chain with `(org_id, user_id, action, timestamp)`.

## Why This Matters for Investors

- **Land-and-expand:** A single tenant can start with one user, then add teams, departments, and subsidiaries without re-architecture.
- **Enterprise-ready:** SSO, RBAC, and audit logs satisfy the first 20 questions of any enterprise security review.
- **Unit economics:** Per-tenant quotas and metering enable usage-based billing (Stripe integration ready).
- **Compliance path:** Tenant isolation is the foundational prerequisite for SOC 2 Type II and HIPAA.

---

*Last updated: 2026-11-07 - v1.10.0*

