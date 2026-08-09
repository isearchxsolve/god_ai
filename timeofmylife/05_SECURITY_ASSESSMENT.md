# Security Assessment

**Date:** 2026-08-08
**Project:** Life Archive — Complete Digital Life Research & Publishing Platform
**Specification Reference:** Sections 9, 25, 26, 34 (Privacy, Privacy Engine, Security, Publication Safety)
**Classification:** INTERNAL — Contains security architecture details

---

## Executive Summary

This assessment evaluates the security posture required for the Life Archive system. The system handles **extremely sensitive data**: complete digital life record including communications, credentials, financial data, health information, third-party PII, and intellectual property.

**Current Risk Level:** **CRITICAL** — No security controls implemented yet. Empty repository.
**Target Risk Level:** **MANAGED** — Defense-in-depth with privacy-by-design, zero-trust architecture, and forensic auditability.

**Key Principles (from Spec):**
- Everything PRIVATE by default (Rule 9)
- Third-party private info never automatically public (Rule 9)
- Credentials/secrets never enter research corpus, LLM prompts, embeddings, public reports, Git, logs (Rule 9, Section 25)
- No automatic public publishing (Section 34)
- Human approval required for all publication (Rule 10, Section 34)

---

## 1. Threat Model

### 1.1 Assets (What We Protect)

| Asset | Sensitivity | Impact if Compromised |
|-------|-------------|----------------------|
| Raw source data (emails, docs, photos, chats) | **CRITICAL** | Total life exposure; identity theft; blackmail; corporate espionage |
| Derived data (entities, timeline, graph) | **HIGH** | Behavioral profiling; relationship mapping; predictive harm |
| Credentials (OAuth tokens, API keys) | **CRITICAL** | Account takeover; lateral movement to source systems |
| Research findings (hypotheses, contradictions) | **MEDIUM** | Reputational harm; IP leakage; strategic disadvantage |
| Publication drafts (pre-approval) | **MEDIUM** | Premature disclosure; editorial control loss |
| Audit logs / forensic evidence | **HIGH** | Integrity verification loss; compliance failure |

### 1.2 Threat Actors

| Actor | Capability | Motivation | Likelihood |
|-------|------------|------------|------------|
| **External attacker** (remote) | Network exploitation, credential stuffing, supply chain | Data theft, ransomware, espionage | Medium |
| **Malicious insider** (compromised account) | Legitimate access abuse | Data exfiltration, sabotage | Low |
| **Curious operator** (self) | Full system access | Accidental exposure, misconfiguration | Medium |
| **Supply chain** (compromised dependency) | Code execution via malicious package | Backdoor, data exfiltration | Low-Medium |
| **LLM provider** (data leakage) | Training on prompts, logging | Model improvement, legal compliance | Low (mitigated by privacy engine) |

### 1.3 Attack Surface

| Entry Point | Current State | Target State |
|-------------|---------------|--------------|
| Docker API (localhost) | Exposed via Docker Desktop | Restricted to localhost; TLS |
| n8n web UI (port 5678) | No auth by default | SSO + MFA; reverse proxy |
| Database ports (5432, 7687, 6379, 6333) | Exposed on Docker network | Internal network only; no host binding |
| MinIO console (9001) | Default creds | Rotated creds; internal only |
| LLM API calls | Direct from code | Via privacy engine proxy |
| File system (LIFE_ARCHIVE/) | Standard permissions | Encrypted volume (BitLocker/LUKS) |
| Git repository | No secrets scanning | Pre-commit hooks + CI scanning |

---

## 2. Security Controls by Layer

### 2.1 Infrastructure Security

| Control | Implementation | Status |
|---------|----------------|--------|
| **Network Segmentation** | Docker network `life-archive-net`; no host ports except Traefik (80/443) | 📋 Planned |
| **TLS Everywhere** | Traefik + Let's Encrypt for all external endpoints; self-signed certs for internal | 📋 Planned |
| **Container Hardening** | Non-root users; read-only rootfs; dropped capabilities; no-new-privileges | 📋 Planned |
| **Image Security** | Pinned digests; `trivy` scanning in CI; distroless/base images where possible | 📋 Planned |
| **Secrets Management** | Docker secrets for runtime; `.env` for dev only; n8n encrypted credential store | 📋 Planned |
| **Host Hardening** | BitLocker (Windows); auto-updates; firewall; audit policy | ⚠️ Host-dependent |

### 2.2 Application Security

| Control | Implementation | Status |
|---------|----------------|--------|
| **Authentication** | n8n: SSO (OIDC) + MFA; API: Bearer tokens (short-lived) | 📋 Planned |
| **Authorization** | RBAC: `admin`, `operator`, `viewer`, `connector:{id}` | 📋 Planned |
| **Input Validation** | Pydantic/Zod schemas on all boundaries; no `eval`/`exec` | ✅ By design |
| **Output Encoding** | Context-aware (HTML, JSON, SQL, Shell) | ✅ By design |
| **Error Handling** | No stack traces in responses; structured error codes | 📋 Planned |
| **Logging** | Structured JSON; PII redaction; no secrets; audit trail | 📋 Planned |
| **Rate Limiting** | Per-connector (n8n); per-API (code); per-user (dashboard) | 📋 Planned |

### 2.3 Data Security

| Control | Implementation | Status |
|---------|----------------|--------|
| **Encryption at Rest** | BitLocker (Windows host); application-level for sensitive fields (AES-256-GCM) | 📋 Planned |
| **Encryption in Transit** | TLS 1.3 for all external; mTLS for service-to-service (future) | 📋 Planned |
| **Key Management** | `N8N_ENCRYPTION_KEY` for n8n; envelope encryption for app secrets | 📋 Planned |
| **Data Minimization** | Only ingest needed fields; privacy classification at ingestion | ✅ By design |
| **Retention** | Configurable per privacy class; audit log immutable | 📋 Planned |
| **Disposal** | Secure delete (shred) for temp files; key rotation for encrypted data | 📋 Planned |

### 2.4 Privacy Engine (Section 25) — **Critical Component**

| Classification | Handling |
|----------------|----------|
| **PUBLIC** | No restrictions; can be published |
| **PRIVATE** | Default for all ingested data; never sent to LLM without redaction |
| **SENSITIVE** | Health, financial, biometric; encrypted at field level; audit access |
| **THIRD_PARTY_PRIVATE** | Other people's PII; never published; redacted in all outputs |
| **RESTRICTED** | Credentials, keys, secrets; **never leave secure store**; not in archive |

**Privacy Engine Functions:**
1. **Classification** — At ingestion (rules + ML), user-overridable
2. **Redaction** — Before any LLM prompt, embedding, search index, export
3. **Tokenization** — Replace PII with tokens; detokenize only for authorized human review
4. **Consent Tracking** — Per-third-party consent records for publication
5. **Audit** — Every access to SENSITIVE/THIRD_PARTY_PRIVATE logged

**Implementation:** Separate Python service (`privacy-engine`) with gRPC/HTTP API. Called by all pipeline stages.

---

## 3. Connector-Specific Security

| Connector | Risk | Mitigations |
|-----------|------|-------------|
| `local-files` | Path traversal; symlink attacks | Chroot to `00_RAW/`; resolve symlinks; validate paths |
| `google-takeout` | Malicious ZIP (zip slip, zip bomb) | Streaming extraction; size limits; sandbox |
| `gmail` / `google-*` | Token leakage; over-scoped OAuth | Minimal scopes; short-lived access tokens; refresh token encryption |
| `github` | PAT leakage; repo access | Fine-grained PAT; read-only; rotation schedule |
| `whatsapp` / `linkedin` | Export file tampering | Hash verification; schema validation |
| `git` | Malicious repo (git bombs, hooks) | `git bundle` (no hooks); size limits; no clone |

---

## 4. LLM Interaction Security (Critical)

**Rule:** **No raw source data ever sent to LLM.**

| Layer | Protection |
|-------|------------|
| **Privacy Engine** | Redacts PII, credentials, secrets, third-party private data before prompt construction |
| **Prompt Templates** | Parameterized; no string interpolation of raw data |
| **Function Calling** | Structured outputs only; no free-form generation from raw data |
| **Embedding Generation** | Only on redacted/normalized content; never on raw |
| **Local Model Option** | Ollama for sensitive phases; no data leaves machine |
| **Audit** | Every LLM call logged: model, prompt hash, tokens, cost, classification of input |

---

## 5. Publication Safety (Section 34)

**No automatic publishing. Ever.**

| Gate | Check | Implementation |
|------|-------|----------------|
| **FACT CHECK** | All claims validated via Validation Engine | Automated + human review |
| **PRIVACY CHECK** | Privacy Engine: no PRIVATE/SENSITIVE/THIRD_PARTY_PRIVATE/RESTRICTED | Automated |
| **COPYRIGHT CHECK** | Third-party content detection; fair use analysis | Semi-automated |
| **EVIDENCE CHECK** | Every claim traces to source archive ID | Automated |
| **EDITORIAL REVIEW** | Human editor reviews tone, accuracy, completeness | Manual |
| **HUMAN APPROVAL** | Explicit "APPROVE" action in dashboard | Manual (required) |

**Published Version Storage:** Immutable copy in `11_PUBLICATION/{channel}/{timestamp}/` with full provenance chain.

---

## 6. Compliance Considerations

| Regulation | Applicability | Controls |
|------------|---------------|----------|
| **GDPR** (EU) | If subject in EU | Right to access/erasure; DPIA; lawful basis (legitimate interest); DPO |
| **CCPA** (California) | If subject in CA | Opt-out; disclosure; deletion |
| **HIPAA** | If health data present | BAA with providers; encryption; access logs; breach notification |
| **SOC 2** | If commercialized | Security, availability, confidentiality principles |
| **ISO 27001** | Best practice | ISMS; risk treatment; controls |

**Current:** Personal use — GDPR/CCPA as best practice. Document lawful basis.

---

## 7. Incident Response Plan

| Phase | Actions | Owner |
|-------|---------|-------|
| **Detect** | Alert on: failed auth, unusual access, data egress, credential use | Monitoring (Prometheus/Grafana) |
| **Contain** | Revoke tokens; isolate containers; disable n8n; block IPs | Operator |
| **Eradicate** | Rotate all credentials; rebuild containers from clean images | Operator |
| **Recover** | Restore from verified backup; verify hashes; replay ingestion | Operator |
| **Post-Incident** | Root cause; update controls; document lessons | Operator |

**Backup Strategy:**
- `00_RAW/` — Immutable; replicate to cold storage (encrypted)
- Databases — Daily pg_dump/neo4j dump; point-in-time recovery
- n8n — Credential export (encrypted); workflow JSON export
- Config — Git (this repo)

---

## 8. Security Testing Requirements

| Test | Frequency | Tool |
|------|-----------|------|
| Dependency scanning | Every build | `trivy`, `pip-audit`, `bun audit` |
| Container scanning | Every deploy | `trivy image` |
| Secret scanning | Pre-commit + CI | `git-secrets`, `trufflehog` |
| SAST | CI | `semgrep`, `bandit` (Python) |
| DAST | Staging | `OWASP ZAP` |
| Penetration test | Quarterly | Manual / bug bounty |
| Privacy impact assessment | Major feature | DPIA template |

---

## 9. Security Debt & Known Gaps (Current State)

| Gap | Risk | Remediation |
|-----|------|-------------|
| No Docker daemon running | Cannot deploy infrastructure | Start Docker Desktop |
| No n8n deployed | No orchestration, no credential store | Deploy via Docker Compose |
| No privacy engine | PII would leak to LLMs | Implement before any LLM calls |
| No TLS | Cleartext on network | Traefik + Let's Encrypt |
| No RBAC | Single-user assumed | Implement before multi-user |
| No audit logging | No forensic trail | Structured logging + immutable store |
| No backup tested | Data loss risk | Implement + test restore |
| Host not hardened | Local privilege escalation | BitLocker, updates, firewall |

---

## 10. Verdict & Next Steps

**CURRENT STATE: NOT SECURE FOR PRODUCTION DATA**

**Minimum Viable Security for Pilot (Phase 1):**
1. Start Docker Desktop → deploy infrastructure
2. Generate strong `N8N_ENCRYPTION_KEY` → persist in `.env`
3. Configure n8n with basic auth (no SSO yet)
4. Implement `local-files` connector with path validation
5. **Implement Privacy Engine stub** (classification + redaction) before any LLM integration
6. Enable BitLocker on host drive
7. Pre-commit secret scanning

**Before Phase 2 (Google OAuth):**
8. TLS via Traefik
9. n8n SSO + MFA
10. Full Privacy Engine
11. Audit logging
12. Backup/restore tested

**Next Action:** Create `06_IMPLEMENTATION_PLAN.md` with Phase 1 tasks including security foundations.