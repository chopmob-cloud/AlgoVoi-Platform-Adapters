# AlgoVoi — Information Security Policy & ICT Risk Management Framework

| Field | Value |
|---|---|
| **Document version** | 2.0 |
| **Effective date** | 2026-05-03 |
| **Original effective date** | 2026-04-19 (v1.0) |
| **Next scheduled review** | 2026-08-03 (quarterly) |
| **Owner** | Information Security Officer (ISO) — Christopher Hopley |
| **Approver** | Information Security Officer |
| **Classification** | Public — fully published in this repository alongside companion policies |
| **Supersedes** | v1.0 (2026-04-19, 135 lines). v2.0 expands scope to: SOC 2 Common Criteria CC6–CC9, full DORA Articles 5–11 mapping, full risk register, per-scenario incident runbooks, per-failure BCP playbooks, exception register, annual tabletop template. Sister policies (Access Control, Change Management, Incident Response, BCP, Vendor Management, Acceptable Use, AML, etc.) remain authoritative for their specific topics — see Section 13 below. |

---

## Table of contents

1. [Purpose, scope, and applicability](#1-purpose-scope-and-applicability)
2. [Information classification](#2-information-classification)
3. [ICT Risk Management Framework](#3-ict-risk-management-framework)
4. [Security controls — mapped to SOC 2 Common Criteria + DORA](#4-security-controls)
5. [Incident management](#5-incident-management)
6. [Business continuity & disaster recovery](#6-business-continuity--disaster-recovery)
7. [Vulnerability management](#7-vulnerability-management)
8. [Third-party / ICT supplier risk management](#8-third-party--ict-supplier-risk-management)
9. [Personnel security](#9-personnel-security)
10. [Data protection (UK GDPR / DPA 2018)](#10-data-protection-uk-gdpr--dpa-2018)
11. [Regulatory mapping](#11-regulatory-mapping)
12. [Policy review and exception process](#12-policy-review-and-exception-process)
13. [Related policies](#13-related-policies)

Appendices

- [A. Top-15 risk register](#appendix-a--top-15-risk-register)
- [B. Incident response runbook (per scenario)](#appendix-b--incident-response-runbook-per-scenario)
- [C. BCP playbook (per failure mode)](#appendix-c--bcp-playbook-per-failure-mode)
- [D. ICT supplier inventory](#appendix-d--ict-supplier-inventory)
- [E. Annual tabletop exercise template](#appendix-e--annual-tabletop-exercise-template)
- [F. Document review log](#appendix-f--document-review-log)

---

## 1. Purpose, scope, and applicability

### 1.1 Purpose

This document is the canonical AlgoVoi information security policy and ICT risk management framework. It exists for three reasons:

1. **Governance** — to establish, in writing, the security controls AlgoVoi commits to operate, the risk-acceptance decisions made by management, and the cadence at which controls are reviewed.
2. **Audit evidence** — to satisfy the documented-policy requirements of SOC 2 (Common Criteria CC1–CC9), the EU Digital Operational Resilience Act ("DORA", Articles 5–11), the UK Money Laundering Regulations 2017, and enterprise-customer vendor-security questionnaires.
3. **Operational discipline** — to give the team (currently founder-only) a single reference for incident response, business continuity, and vendor onboarding.

### 1.2 Scope

This policy applies to:

- All AlgoVoi-operated production infrastructure: VM1 (control plane + gateway + facilitator + nginx + Postgres on Vultr Cloud Compute), VM2 (Postgres backup + secondary facilitator on Vultr), VM3 (cloud gateway proxy + bots on Vultr), and any supplementary systems brought into production scope in future.
- All AlgoVoi-operated source repositories under `chopmob-cloud/*` on GitHub.
- All AlgoVoi-operated AWS / Vultr / Cloudflare / Mintlify accounts and their contents.
- All personnel (currently the founder; future contractors and employees by extension).
- All data processed by AlgoVoi on behalf of merchants and payers, including KYB documents, KYC records, payout addresses, transaction logs, and personal data within the meaning of UK GDPR.

### 1.3 Out of scope

- Customer-side custody of private keys (AlgoVoi is non-custodial — keys held by merchants / payers in their own wallets are not in AlgoVoi's threat model except where they interact with our infrastructure).
- Third-party blockchain network security (Algorand, VOI, Hedera, Stellar, Base, Solana, Tempo network-layer security is the responsibility of the respective protocol operators).
- Customer-end-user device security (browsers, mobile OS).

### 1.4 Approval and ownership

| Role | Holder (2026-05-03) | Responsibilities |
|---|---|---|
| Document owner / approver | **Christopher Hopley** (Information Security Officer) | Final authority on policy contents and exceptions |
| Information Security Officer | Christopher Hopley | Day-to-day operation of controls; incident command; quarterly review of this policy |
| Money Laundering Reporting Officer | Christopher Hopley (`compliance@algovoi.co.uk`) | UK MLR 2017 obligations: Suspicious Activity Reports, sanctions decisions, AML governance. Publicly named on `algovoi.co.uk/compliance.html`. |
| Data Protection Officer | Christopher Hopley (`privacy@algovoi.co.uk`) | UK GDPR Art. 37 — formally designated; ICO data-controller registration in preparation. |

**Single-person dependency is itself a risk** — see Risk R-12 in Appendix A. The mitigation plan (named successor + handover document) is tracked there. The single-person constraint is the largest open exception in Section 12 (E-01).

---

## 2. Information classification

AlgoVoi handles four classes of information. Classification drives which controls apply (encryption, access, retention, deletion).

| Class | Description | Examples | Controls |
|---|---|---|---|
| **C1 — Public** | Information already published or intended for public consumption. No confidentiality requirement. | Marketing site, public docs (docs.algovoi.co.uk), open-source GitHub repos, public blog posts. | Integrity only (TLS in transit, signed releases). |
| **C2 — Internal** | Information internal to AlgoVoi that is not sensitive but should not be published. | Internal runbooks, vendor invoices, this policy, infrastructure diagrams without secrets. | Access control (restricted to founder + named contractors). Encryption-in-transit for any external sharing. |
| **C3 — Confidential** | Information whose unauthorised disclosure would harm AlgoVoi or its customers. | Tenant API keys (hashed at rest), tenant payout addresses, transaction logs, audit log, internal incident reports. | All C2 controls plus encryption-at-rest where stored on disk. Access logged. Retention: per regulatory requirement (typically 5–7 years). |
| **C4 — Restricted (special category)** | Information whose unauthorised disclosure would cause significant harm to natural persons. Includes UK GDPR Article 9 special-category personal data. | KYB documents (passports, beneficial-owner IDs, proofs of address), customer KYC selfies, biometric data, MLRO Suspicious Activity Reports, signed mandates. | All C3 controls plus dedicated encryption key (`KYB_ENCRYPTION_KEY`, separate from `HMAC_ENCRYPTION_KEY`). Access requires `compliance:admin` scope and is audit-logged with hash-chain integrity. Retention: 5 years post-relationship-end (UK MLR 2017 Reg 40(3)) or per legal hold. |

**No C4 data ever leaves AlgoVoi-controlled storage in plaintext.** It is read into application memory only when needed for processing (KYB review, GDPR data export, MLRO investigation), processed inline, and not persisted in logs, debug traces, or non-encrypted backups. The KYB-at-rest encryption design and migration record are documented in `docs/SECURITY_KYB_AT_REST_2026-04-26.md`.

---

## 3. ICT Risk Management Framework

Aligned with DORA Articles 5–6 (ICT risk management framework requirements) and SOC 2 CC3 (Risk Assessment).

### 3.1 Risk-management lifecycle

AlgoVoi follows a four-stage lifecycle for every identified risk:

1. **Identify** — risks are surfaced from four channels: (a) quarterly self-assessment by the CISO, (b) every post-incident review (Section 5.4), (c) every external audit / vendor questionnaire response, (d) ad-hoc reporting from any team member or customer.
2. **Assess** — each risk is scored on two axes: *likelihood* (1–5) and *impact* (1–5). The product yields a residual-risk score (1–25). Scores are reviewed by the CISO at the next quarterly review.
3. **Treat** — for each risk the CISO selects one of four treatments: *mitigate* (add or strengthen a control), *transfer* (insurance, contract terms), *avoid* (stop the activity), or *accept* (document acceptance with sign-off, risk score, and review date).
4. **Monitor** — every risk in the register has a named owner, a current treatment, and a next-review date. Risks are revisited at the quarterly CISO review and whenever a material change occurs (new chain integration, new third-party supplier, regulatory change, security incident).

### 3.2 Risk-scoring matrix

| Likelihood ↓ / Impact → | 1 (Negligible) | 2 (Minor) | 3 (Moderate) | 4 (Severe) | 5 (Catastrophic) |
|---|---|---|---|---|---|
| **5 (Almost certain)** | 5 | 10 | 15 | 20 | 25 |
| **4 (Likely)** | 4 | 8 | 12 | 16 | 20 |
| **3 (Possible)** | 3 | 6 | 9 | 12 | 15 |
| **2 (Unlikely)** | 2 | 4 | 6 | 8 | 10 |
| **1 (Rare)** | 1 | 2 | 3 | 4 | 5 |

**Treatment thresholds:**

- **20–25:** must be mitigated to ≤ 12 within 30 days, or formally accepted in writing with quarterly review.
- **12–19:** must be mitigated to ≤ 9 within 90 days, or formally accepted with semi-annual review.
- **9–11:** mitigation strongly preferred within the next quarter; formal acceptance allowed.
- **≤ 8:** monitor only; review at next scheduled quarterly review.

### 3.3 Top-level risk register

Full register in **Appendix A**. Summary by category:

| Category | Count of risks | Highest residual score |
|---|---|---|
| Cryptographic key compromise | 2 | 12 |
| Customer fund / asset loss | 1 | 9 |
| Audit / compliance failure | 2 | 9 |
| Infrastructure outage | 3 | 8 |
| Data protection failure (GDPR) | 2 | 9 |
| Supply chain / third-party | 2 | 8 |
| Personnel single-point-of-failure | 1 | 12 |
| Smart contract / on-chain | 1 | 6 |
| External attack (DDoS, scanning) | 1 | 4 |

Total tracked risks: 15. Highest residual score in register: 12 (R-01 customer-key theft via wallet UX phishing — mitigation already in flight; R-12 founder unavailability — mitigation deferred per Section 12 exception register).

---

## 4. Security controls

Mapped to SOC 2 Trust Services Criteria (TSC 2017, 2022 revision) Common Criteria CC1 through CC9, with DORA Article cross-references where applicable.

### 4.1 CC1 — Control environment

**Commitment to integrity and ethical values.** The founder (acting CISO + MLRO + DPO) operates under a documented policy of:

- No bypassing of regulatory controls for commercial gain. The compliance moat (KYC/KYB/AML/MLRO/Fernet/sanctions/audit-chain) is the product, not a tax on it.
- Every committed change to production must pass the project's security policy file (`CLAUDE.md` "NO Anthropic / Claude attribution" rule, `security_no_secrets_in_git.md` rule, project-wide pre-commit hook).
- Every audit-relevant action is recorded in `control_plane.audit_log` (hash-chained per migration 095).
- Every regulator-relevant action is also recorded in `control_plane.compliance_events` and `control_plane.screening_hits` (hash-chained per migration 096).

**Organisational structure.** Single founder operating multiple roles; conflicts of interest are documented and reviewed quarterly. Material decisions (treasury movements above thresholds, new chain integration, new third-party supplier) require written rationale stored in the founder's decision log even where no second signatory exists.

**Hiring.** No employees as of 2026-05-03. When the first contractor or employee is engaged, all of the following will apply prior to access provisioning:

- Reference checks and (where permitted) basic criminal-record check
- Signed NDA
- Acknowledged read of this policy
- Access provisioned via least-privilege admin keys, not the static admin key
- Onboarding ticket recorded in audit log

### 4.2 CC2 — Communication and information

**Internal communication.** Single-person team; daily standup not applicable. All material decisions logged in commit messages, this policy's review log (Appendix F), and the project's persistent memory store (`memory/`).

**External communication.** Customer-facing security claims live at:

- **`docs.algovoi.co.uk/architecture`** — system architecture overview
- **`docs.algovoi.co.uk/security`** — customer-facing trust page (planned, Gap 7 of `outreach/SECURITY-recommendations.md`)
- **`api1.ilovechicken.co.uk/.well-known/security.txt`** — coordinated-disclosure contact (planned, Gap 7)
- This policy on signed NDA for prospects + auditors

**Incident communication.** See Section 5.3.

### 4.3 CC3 — Risk assessment

Covered in Section 3 above. Quarterly self-assessment + post-incident risk review + ad-hoc on material change.

DORA Article 5(1) requirement for annual review is met by the quarterly cadence (more frequent than required).

### 4.4 CC4 — Monitoring activities

**Continuous monitoring.**

| Surface | Mechanism | Cadence |
|---|---|---|
| Authentication outcomes | `AdminAuthCounters` in-process counters (`admin_auth_service.py`) | Real-time + reviewed daily |
| Audit-log integrity | `GET /internal/audit-log/verify-chain` | Pre-shipment scan in reaper, every 5 min |
| Sanctions cache freshness | `sanctions_refresh_reaper_loop` writes `sanctions_list_entries.last_refreshed_at` | Daily refresh + reviewed at quarterly review |
| Compliance-rule evaluation | `compliance_monitoring_reaper_loop` background sweep | Hourly |
| Webhook delivery health | `webhook_reaper_loop` retries + dead-letter | 30s → 32h |
| URL/IP screening cache | `url_screening_reaper` | Daily refresh |
| Postgres backup health | Daily 02:00 UTC pg_dump to VM2; integrity validation logged | Daily |
| Container health | Docker health checks + nginx upstream monitoring | Real-time |

**Periodic review.**

- **Daily:** auth counter check, error log skim, deployed-version check, payment-success-rate spot check.
- **Weekly:** review open issues, review screening-hits unreviewed queue, review compliance-events unreviewed queue.
- **Monthly:** review access list (admin keys + API keys), rotate credentials due for rotation, review patch level of base images.
- **Quarterly:** full policy review (this document); risk-register review; tabletop exercise (one per year, see Appendix E); third-party supplier review (see Section 8).
- **Annually:** external penetration test (planned Q4 2026); SOC 2 Type II audit if 5 paying tenants milestone reached (per `outreach/PLAN-compliance-wedge-90d.md` C1).

### 4.5 CC5 — Control activities

**Segregation of duties.** Single-person team — segregation enforced where possible by separating roles in time (e.g., founder requests deploy → manual checklist confirms → founder executes deploy). Audit log records both states.

**Authorisation.** Production changes require:

1. Local development + tests passing
2. Manual smoke test against local environment
3. Commit signed under the founder's GPG key (planned — not yet enabled, see Risk R-13 Appendix A)
4. Deployment via documented SSH + Docker-Compose procedure (`docs/DEPLOYMENT.md`)
5. Post-deploy smoke test against production health endpoints
6. Audit-log entry recorded automatically by the deployed service on its first request

**Reconciliation.** Monthly: reconcile platform-fee ledger vs Postgres `platform_fee_ledger` table; reconcile settlement statements vs on-chain transaction confirmations; reconcile AdminKey table vs in-use keys per the auth counters.

### 4.6 CC6 — Logical and physical access controls

#### 4.6.1 Logical access — admin

- Admin authentication uses bearer tokens hashed with SHA-256 and stored as `key_hash` in `control_plane.admin_keys`. Plaintext tokens are returned once at issuance and never persisted.
- Lookup uses an O(1) hint (`key_id = "hk_<sha256[:8]>"`) before performing a timing-safe full-hash comparison via `hmac.compare_digest`.
- Token expiry is enforced per `expires_at`. Default expiry is 90 days; rotation is documented in `memory/reference_secret_rotation.md`.
- TOTP MFA is required for the admin dashboard (`mfa_service.py`, `valid_window=1` for ±30s clock drift).
- Static admin key fallback exists for legacy compatibility (Risk R-15) — its retirement is tracked as an open gap.
- Admin scopes are enforced per endpoint via `require_scope()` dependency. Current scope set: `audit:read`, `compliance:read`, `compliance:admin`, `tenants:read`, `tenants:write`, `apikeys:admin`, `payouts:read`, `payouts:write`, `disputes:write`, `kyb:write`, `subscriptions:admin`, plus 3 reserved for future use.

#### 4.6.2 Logical access — tenant API

- Tenant API keys are hashed with Argon2id (`api_keys` table), with key states `active`, `grace`, `revoked`, `suspended`.
- Grace-period rotation supports zero-downtime key replacement.
- Per-tenant rate limits enforced by `slowapi` in nginx + application-layer token-bucket on protected endpoints.

#### 4.6.3 Encryption

- **In transit:** TLS 1.3 enforced at Cloudflare edge for public traffic; TLS-only configuration in nginx; outbound HTTPS only for third-party APIs.
- **At rest:**
  - Tenant secrets (HMAC, OAuth tokens, MFA TOTP seeds, webhook secrets) encrypted with `HMAC_ENCRYPTION_KEY` (Fernet, MultiFernet rotation).
  - KYB documents and special-category personal data encrypted with `KYB_ENCRYPTION_KEY` (Fernet, AVK1 magic-prefix scheme, see `shared/utils/encryption.py:encrypt_bytes`).
  - **The two keys are deliberately distinct.** Production startup validation refuses to start if `KYB_ENCRYPTION_KEY == HMAC_ENCRYPTION_KEY` or if either is unset.
  - Postgres data-at-rest is currently unencrypted at the disk layer (LUKS deferred per `docs/SECURITY_KYB_AT_REST_2026-04-26.md` — interim policy: file-level encryption-at-rest for special-category data, full-disk encryption when paying-tenant count crosses 25 OR KYB document count crosses 100 OR 90 days elapsed from 2026-04-26).
  - Key recovery: customer-controlled key copies are operator's responsibility; lost `KYB_ENCRYPTION_KEY` makes encrypted KYB files permanently unrecoverable. The key is stored offline in `C:\Users\<founder>\.secrets\` with a separate physical backup.

#### 4.6.4 Network access

- VM1 public traffic is restricted to Cloudflare IP ranges via the `DOCKER-USER` iptables chain (verified 2026-05-03: 225,000+ direct-IP probes blocked). See `memory/plan_vm1_firewall_fix.md`.
- VPC-to-VPC traffic between VM1 ↔ VM3 traverses Vultr's private network (`10.8.96.0/20`).
- VM1 ↔ VM2 backup traffic currently traverses public internet over SSH; WireGuard mesh planned (Risk R-08).
- SSH access to all VMs requires a key-based login; no password authentication permitted (`PasswordAuthentication no` in `/etc/ssh/sshd_config`). Only the founder's SSH keys are present in production.

#### 4.6.5 Physical access

Production infrastructure is hosted on Vultr Cloud Compute. Vultr operates SOC 2 Type II audited datacentres. Physical access is delegated to Vultr per their published datacentre security policy. AlgoVoi does not operate any on-premises hardware in scope of this policy.

### 4.7 CC7 — System operations

#### 4.7.1 Configuration management

- All configuration changes go through git (`chopmob-cloud/` repos). Commits are reviewed by the founder before merge.
- Production environment configuration lives in `/opt/algovoi/.env` on VM1, owned by `root:root`, mode `0600`. Never committed to git (see `memory/security_no_secrets_in_git.md`).
- Container images are rebuilt from versioned base images on every deploy; no `latest` tags in production.

#### 4.7.2 Backup and recovery

- **Postgres:** daily `pg_dump` at 02:00 UTC, encrypted with GPG, transferred over SSH to VM2 `/opt/algovoi-backups/postgres/`. Retention: 30 days. Integrity-validation: weekly automated restore to a scratch database + count check.
- **KYB documents:** daily rsync of `/opt/algovoi/kyb_docs/` to VM2 `/opt/algovoi-backups/kyb_docs/`. Encrypted-at-rest at source (Fernet/AVK1). Retention: indefinite while files remain under AML hold.
- **Application source:** version-controlled in git; cloned on every VM rebuild from `chopmob-cloud/platform`.
- **Secrets:** `/opt/algovoi/.env` backed up to VM2 daily, encrypted with GPG. Founder's offline secrets folder is the master copy.
- **Cloudflare config / DNS:** versioned via the Cloudflare dashboard; export-on-change planned.

Restore procedures and RPO / RTO commitments are documented in Section 6 and Appendix C.

#### 4.7.3 Monitoring and alerting

- Application logs are written to stdout/stderr, captured by Docker, and forwarded to nginx access log (`/var/log/nginx/access.log`).
- Log retention: 30 days on VM1, archived on VM2 monthly.
- Active alerts are surfaced via email to the founder + critical events to a dedicated Slack/Telegram channel (configured per `tenant_outbound_notifications` for the founder's own tenant).
- A documented external uptime monitor (Cloudflare or UptimeRobot, planned Q3 2026) will alert on `/health` endpoint failure.

### 4.8 CC8 — Change management

**Standard changes** (low-risk, well-understood, reversible) — e.g., copy update on docs.algovoi.co.uk, dependency patch within minor version, config tweak in `.env` not affecting auth.

- May be deployed without prior change ticket
- Recorded in commit history + audit log
- Reviewed monthly by CISO

**Normal changes** (any change that touches production code paths, schema, secrets, or third-party integrations).

- Must have:
  - Local testing including unit tests passing
  - Change rationale in the commit message
  - Rollback plan in the commit message OR linked runbook
  - Manual smoke test against staging where staging exists, otherwise against local
  - Post-deploy smoke test against production health endpoints
- Reviewed at quarterly CISO review

**Emergency changes** (production outage, security incident).

- Bypass standard testing where genuinely necessary
- Must be followed by a post-incident review (Section 5.4) within 5 working days
- Risk register reviewed for any new risks surfaced

**Migration-class changes** (DB schema migrations under `migrations/control_plane/`).

- Numbered sequentially; each migration must be idempotent and forward-only
- Tested in local environment before production application
- Applied via `psql -f` during a documented maintenance window
- Companion application code is staged so application redeployment can occur after migration without lock-up

DORA Article 9 (ICT change management) requirements — documented in this section — exceed the criteria for a single-person team. When the team grows, change advisory board (CAB) review will be added.

### 4.9 CC9 — Risk mitigation (vendor management)

See Section 8. Third-party risk is currently limited to a small number of well-known suppliers (Vultr, Cloudflare, Mintlify, Alchemy, Helius, Allbridge, MaxMind). Each has a documented onboarding rationale (Appendix D) and a quarterly review cadence.

---

## 5. Incident management

DORA Article 17 (ICT-related incident management) and SOC 2 CC7 (System Operations) require documented classification, response, and review processes. AlgoVoi operates the following.

### 5.1 Incident classification taxonomy

| Severity | Definition | Examples | Response SLA | Escalation | Communication |
|---|---|---|---|---|---|
| **P0 — Catastrophic** | Customer fund loss, key compromise, sanctions failure that would cause financial-crime liability, total platform outage > 1h. | Private key leak, unsanctioned payout, KYB document exfiltration, cryptographic chain break with no off-VM copy, simultaneous loss of VM1 + VM2. | **24/7 immediate.** Founder acknowledges within 15 min. | Founder + (when team grows) on-call rotation + (always) MLRO if AML implication. Regulator notification per 5.3. | Status page + email to all affected tenants + (if AML) FCA SAR within 30 days. |
| **P1 — Severe** | Single-service outage, payment-processing degraded, KYB workflow blocked, audit log integrity flag, single-region Cloudflare outage. | Postgres replication lag > 1h, control plane down, sanctions cache > 48h stale, single-tenant payout failed > 3 times. | **4h business-day, 24h out-of-hours.** | Founder. CISO escalation review at next daily check. | Status page + email to materially-affected tenants. |
| **P2 — Moderate** | Non-payment service degraded, monitoring alert requiring investigation, single-tenant impact on non-critical path. | Webhook delivery to one destination dead-lettered, single AI provider adapter throttled, dashboard slow but functional. | **24h business-day.** | Founder logs in incident tracker. | None unless affected tenant escalates. |
| **P3 — Minor** | Cosmetic, non-blocking, internal-only. | Marketing-site typo, log warning that does not impact processing, internal docs out of date. | **72h business-day.** | None. | None. |

### 5.2 Incident response runbook

Per-scenario runbooks live in **Appendix B**. The general flow:

1. **Detect.** Source: monitoring alert, customer report, internal observation, third-party notification (e.g., Vultr abuse report, Cloudflare WAF alert), regulator notification.
2. **Triage.** Confirm scope. Classify severity per 5.1. Open an incident ticket (private GitHub issue or runbook entry under `incidents/YYYY-MM-DD-NN/`).
3. **Contain.** Apply immediate mitigations (block compromised key, disable affected service, isolate affected tenant). Document each action with timestamp.
4. **Eradicate.** Identify and remove root cause. Do not skip — even under time pressure — because a P0 may have multiple compounding root causes.
5. **Recover.** Restore service. Verify health endpoints + customer-side smoke tests pass.
6. **Review.** Post-incident review within 5 working days (Section 5.4).

### 5.3 External communication during incidents

| Audience | Trigger | Channel | Maximum delay |
|---|---|---|---|
| Affected tenant(s) | P0 / P1 affecting that tenant | Email + dashboard banner | 1 hour from confirmation |
| All tenants | Material platform outage > 30 min | Status page + email | 1 hour from confirmation |
| Regulator (FCA) | Suspected AML breach, sanctions failure, financial-crime incident | MLRO files SAR with NCA via SARonline within 30 days; FCA notified concurrently if material | 30 days (statutory) |
| Regulator (ICO) | Personal data breach affecting natural persons (UK GDPR Art. 33) | ICO portal + email; affected data subjects per Art. 34 | **72 hours** (statutory) |
| MLRO consultant (when external one engaged) | All P0 with AML / financial-crime element | Email + phone | 24 hours |
| Vendor (Cloudflare, Vultr, etc.) | Incident traced to their service | Vendor support portal | Same day |
| Public | Material public-trust impact | Twitter/X + status page + blog post | At founder discretion; never withhold material safety information |

### 5.4 Post-incident review

Within 5 working days of recovery for every P0/P1, a written review is filed under `incidents/YYYY-MM-DD-NN/postmortem.md` covering:

- Timeline (detected → contained → eradicated → recovered)
- Root cause (technical + organisational)
- Customer impact (number of tenants, transactions affected, financial impact if any)
- What worked + what didn't
- Action items (with owners + due dates)
- Risk register updates (any new R-NN added, any existing R-NN re-scored)
- Policy updates (this document) if controls are added or strengthened

P2 reviews may be a single paragraph in the original ticket. P3 do not require review.

---

## 6. Business continuity & disaster recovery

DORA Article 11 (Business continuity policy) and SOC 2 CC7.5 (Recovery from incidents).

### 6.1 BCP scope

The following services and data are in scope:

- **Production payment-processing services:** gateway, control_plane, facilitator, nginx, Postgres on VM1.
- **Cloud gateway services:** VM3 services (cloud gateway proxy, Telegram bot, Discord bot, Viber bot).
- **Backup infrastructure:** VM2 (Postgres backup, KYB document backup, secondary facilitator).
- **External-edge services:** Cloudflare (WAF, CDN, DNS, TLS termination).
- **Public docs:** docs.algovoi.co.uk (Mintlify-hosted).
- **Public marketing site:** algovoi.co.uk (Vite-hosted on VM1 nginx).
- **Repositories:** chopmob-cloud GitHub organisation.

### 6.2 RPO and RTO commitments

| Service / Data | RPO (max data loss) | RTO (max downtime) | Recovery method |
|---|---|---|---|
| Payment processing (gateway) | 0 (in-flight requests retried by client) | 1 hour | Docker restart on VM1; full container rebuild if image corrupted |
| Control plane | 0 | 1 hour | Docker restart on VM1 |
| Facilitator | 0 | 1 hour | Docker restart; secondary facilitator on VM2 as cold standby |
| Postgres | 24 hours | 4 hours | Restore from VM2 daily backup; replay any unbacked-up WAL if available |
| KYB documents | 24 hours | 4 hours | Restore from VM2 daily rsync mirror |
| Sanctions cache | 24 hours | 1 hour | Background reaper repopulates from upstream (OFSI / OFAC / EU) feeds |
| Audit log + chain | 0 (hash chain prevents silent loss) | 4 hours (DB restore) | Restore from VM2 + verify chain via `/internal/audit-log/verify-chain` + reconcile against Object Lock copy when available (Gap 1 sub-fix #2) |
| Cloudflare config / DNS | 0 (Cloudflare-managed) | Cloudflare's RTO | Cloudflare console |
| Public docs | 24 hours | 1 hour | Mintlify auto-rebuilds from `chopmob-cloud/docs` main on push |
| Marketing site | 24 hours | 1 hour | Rebuild from `chopmob-cloud/AlgoVoi/site` |
| GitHub repositories | 0 (GitHub-managed) | 0 | GitHub's RTO; mitigation if GitHub down: founder's local clones |

**RPO and RTO are commitments, not guarantees.** They are the targets the BCP is designed to meet. Actual recovery time will depend on incident specifics.

### 6.3 Failure modes covered

Per-failure-mode playbooks in **Appendix C**. Categories:

- VM1 single-service crash (Docker container)
- VM1 full-host failure (Vultr instance gone)
- VM1 region failure (entire Vultr region down)
- VM2 failure (no impact to live service; rebuild backup destination)
- VM3 failure (cloud gateway services degraded; primary VM1 path unaffected)
- Cloudflare account compromise / outage
- Postgres data corruption (single row, table, full DB)
- KYB document file corruption
- Sanctions cache poisoning
- Cryptographic key compromise (`KYB_ENCRYPTION_KEY`, `HMAC_ENCRYPTION_KEY`)
- GitHub repository compromise / takedown
- Founder unavailability (sickness, accident, death)

### 6.4 Annual tabletop exercise

A documented tabletop exercise is conducted at least annually (DORA Article 24). The exercise simulates one P0 scenario from Appendix C and walks the response from detection through recovery + post-incident review without touching production.

Template in **Appendix E**. First exercise scheduled for 2026-08 alongside the day-90 plan checkpoint. Subsequent exercises in 2027-Q3, 2028-Q3.

---

## 7. Vulnerability management

### 7.1 Patching cadence

| Component class | Critical patches | Important patches | Routine updates |
|---|---|---|---|
| Production OS (Ubuntu LTS on VM1/VM2/VM3) | **Within 7 days of vendor release** | Within 30 days | Quarterly |
| Docker base images (alpine, postgres) | Within 14 days of vendor release | Within 30 days | Quarterly |
| Python runtime | Within 30 days of CPython release | Within 90 days | Annually |
| Application dependencies (Python `pyproject.toml`, Node `package.json`) | **Within 7 days for confirmed CVEs in our usage path** | Within 30 days | Quarterly |
| Third-party APIs (Alchemy, Helius, etc.) | N/A — vendor-managed | N/A | N/A |

"Critical" = CVSS 9.0+ AND confirmed exploitable in our usage; "Important" = CVSS 7.0–8.9; "Routine" = bug-fix or feature releases.

### 7.2 Dependency scanning

- **Weekly automated scan:** GitHub Dependabot enabled on `chopmob-cloud/platform` (Python deps) and `chopmob-cloud/AlgoVoi` (Node deps).
- **Monthly manual review:** founder reviews open Dependabot PRs, prioritises based on usage path, batches non-critical patches into a single deploy.
- **CVE feed monitoring:** subscriptions to Python Security Advisories, GitHub Security Advisories, Coinbase x402 ecosystem advisories.

### 7.3 Penetration testing

- **External penetration test** is scheduled annually. First pen test scheduled for **Q4 2026** subject to ≥5 paying tenants milestone (per outreach plan C1).
- **Internal lightweight assessment:** founder performs a quarterly self-assessment using OWASP Top 10 checklist + STRIDE walkthrough of new features.
- **Bug bounty / coordinated disclosure:** `security.txt` planned (Gap 7); reasonable-disclosure policy documented at `docs.algovoi.co.uk/security` once that page lands.

### 7.4 Software Bill of Materials (SBOM)

An SBOM in CycloneDX format is generated on every release tag. First public SBOM scheduled for the docs.algovoi.co.uk launch alongside the trust page (Gap 7). SBOM covers all production-shipped Python and Node dependencies plus their transitive deps.

---

## 8. Third-party / ICT supplier risk management

DORA Articles 28–44 (ICT third-party risk management). SOC 2 CC9.

### 8.1 Supplier categorisation

| Tier | Definition | Onboarding requirements | Review cadence |
|---|---|---|---|
| **T1 — Critical** | Outage = platform outage. AlgoVoi cannot operate without them. | Documented evaluation; SOC 2 Type II report on file; data-processing agreement (DPA); termination plan | Quarterly |
| **T2 — Important** | Outage = degraded service for some tenants. AlgoVoi can switch within hours. | Lighter due diligence; DPA if processing personal data | Semi-annually |
| **T3 — Routine** | Nice-to-have. Outage = minor inconvenience. | Standard procurement; T&Cs reviewed | Annually |

### 8.2 Current supplier inventory

Full inventory in **Appendix D**. Summary:

| Supplier | Tier | Service | Why | Switchable to |
|---|---|---|---|---|
| Vultr | T1 | VM1, VM2, VM3 hosting; Object Storage (planned) | Cost, US/EU presence, simple API | AWS, Hetzner |
| Cloudflare | T1 | WAF, CDN, DNS, TLS termination, Origin CA | Standard for production web services | Fastly, Akamai |
| GitHub | T1 | Source control, CI/CD | Industry standard | GitLab self-hosted |
| Mintlify | T2 | docs.algovoi.co.uk hosting | Best-in-class docs UX | Self-hosted Docusaurus |
| Alchemy | T2 | Ethereum / Base RPC | Reliability + free tier | Infura, self-hosted node |
| Helius | T2 | Solana RPC | Reliability + free tier | QuickNode, self-hosted |
| Allbridge | T2 | xChain bridging (USDC ETH↔Algorand) | Only multi-chain bridge with required path | Wormhole (alternate path) |
| MaxMind | T3 | GeoIP database | Industry standard | IP-API (lower quality) |
| OFAC SDN feed | T3 (mandatory) | Sanctions list | Statutory requirement | OFAC is the source of truth |
| OFSI consolidated list feed | T3 (mandatory) | UK sanctions | Statutory | OFSI is the source of truth |
| Anthropic (Claude API) | T3 | AI tools used internally for development | Productivity | OpenAI, Gemini |

### 8.3 Onboarding due diligence

For T1 and T2 suppliers, before granting access to production data:

1. Review the supplier's most recent SOC 2 / ISO 27001 / PCI-DSS report (whichever applies).
2. Negotiate or accept a Data Processing Agreement (DPA) compliant with UK GDPR Art. 28.
3. Document the supplier's lawful basis for processing in `docs/data_processing_record.md` (in development).
4. Add to Appendix D with: vendor name, service, tier, contract URL, DPA URL, primary contact, onboarding date, next review date.

### 8.4 Ongoing monitoring

- Annual review of each T1 supplier's SOC 2 report.
- Quarterly check that each T1 supplier's incident-disclosure feed is being monitored (status page subscription, mailing list).
- On material change to a supplier's posture (e.g., breach disclosure, ownership change), accelerate review.

### 8.5 Termination plan

Each T1 supplier has an associated migration plan documenting how AlgoVoi would move off them within 30 days if required (e.g., Vultr → AWS migration plan: Terraform stack regen + DNS swap + Postgres restore from backup; ~16h of downtime acceptable as documented exception).

---

## 9. Personnel security

### 9.1 Current state

- One person (founder) operates all roles. No employees, no contractors with production access.
- Founder has a clean criminal record (verified by self-attestation; formal Disclosure & Barring Service check planned alongside formal MLRO appointment per `outreach/SECURITY-recommendations.md` Gap 2).
- Founder's onboarding to the platform is the founding act — no formal onboarding ticket exists. Subsequent personnel will follow Section 4.1 onboarding flow.

### 9.2 Future personnel

When the team grows, the following will apply:

- **Pre-engagement:** reference checks, criminal-record check (UK basic DBS or local equivalent), signed NDA, signed acknowledgement of this policy.
- **Provisioning:** least-privilege admin keys (no static admin key access); MFA enrolment; SSH key registration; Slack/email accounts created.
- **Ongoing:** quarterly access review (admin scopes still appropriate? still needed?); annual policy re-acknowledgement.
- **Offboarding:** within 24 hours of departure: revoke all admin keys and API tokens; rotate any shared secrets they had access to (HMAC, OAuth tokens at minimum); remove SSH keys; revoke physical access; preserve email + Slack for 90 days then archive; update audit log.

### 9.3 Code-of-conduct

- No bypassing controls for personal convenience. The hash-chain audit log will record any attempt.
- No use of personal devices to handle C3 or C4 data. Production data stays on production-managed devices.
- No use of unapproved AI tools to process customer data. Approved tools are documented in Appendix D.
- Annual policy re-acknowledgement.

---

## 10. Data protection (UK GDPR / DPA 2018)

### 10.1 Lawful bases

AlgoVoi processes personal data on the following bases per UK GDPR Art. 6:

| Processing | Lawful basis | Reference |
|---|---|---|
| Tenant onboarding (KYB) | Legal obligation (UK MLR 2017 Reg 28) + Contract performance | Art. 6(1)(c) + 6(1)(b) |
| Customer KYC at trial→mainnet upgrade | Legal obligation (MLRs) + Legitimate interest | Art. 6(1)(c) + 6(1)(f) |
| Sanctions screening | Legal obligation (SAMLA 2018 + UK MLR 2017) | Art. 6(1)(c) |
| AML transaction monitoring | Legal obligation (UK MLR 2017 Reg 28) | Art. 6(1)(c) |
| Audit log records | Legal obligation + Legitimate interest | Art. 6(1)(c) + 6(1)(f) |
| Marketing emails to tenants | Consent (opt-in) | Art. 6(1)(a) |

For UK GDPR Art. 9 special-category data (KYB documents containing biometric data, government IDs):

- Lawful condition: Substantial public interest — preventing money laundering and terrorist financing — per UK GDPR Sched. 1 Part 2 para. 9.

### 10.2 Data subject rights

AlgoVoi implements:

- **Right of access (Art. 15):** GDPR data export endpoint planned (currently a manual operator process).
- **Right to rectification (Art. 16):** tenants can update payout addresses, contact info via the dashboard; KYB documents are write-once but a correction document can be uploaded.
- **Right to erasure (Art. 17):** tenant deletion via `gdpr_purge_service.py`. NOT applicable to records under AML hold (UK MLR 2017 Reg 40(3) requires 5-year retention).
- **Right to restrict processing (Art. 18):** suspension of tenant via dashboard.
- **Right to data portability (Art. 20):** GDPR data export endpoint (planned).
- **Right to object (Art. 21):** tenants may object to marketing; cannot object to processing based on legal obligation.

### 10.3 Data Protection Impact Assessment (DPIA)

A DPIA is required by UK GDPR Art. 35 for high-risk processing. AlgoVoi's KYC/KYB processing arguably qualifies. **A DPIA covering KYB document processing is scheduled for Q3 2026** alongside the day-90 plan checkpoint.

### 10.4 Records of Processing Activities (ROPA)

UK GDPR Art. 30. **A ROPA is scheduled for Q3 2026.** First-version ROPA will cover: tenant onboarding, KYB, KYC, sanctions screening, AML transaction monitoring, audit log, marketing emails, payment ledger, settlement statements.

### 10.5 Data breach notification

Per UK GDPR Art. 33 + Art. 34, see Section 5.3.

---

## 11. Regulatory mapping

| Regulation / standard | Applicability | AlgoVoi position | Evidence file(s) |
|---|---|---|---|
| **UK Money Laundering Regulations 2017** | Operator is a UK-registered crypto-asset service provider | Compliant: KYC/KYB, sanctions screening, MLRO, transaction monitoring, audit log retention | This document + `shared/models/compliance.py` + audit-log chain |
| **UK GDPR / DPA 2018** | All processing of UK personal data | Compliant lawful bases (Section 10.1); subject rights (Section 10.2); DPIA + ROPA scheduled (Section 10.3, 10.4) | This document |
| **SAMLA 2018 (Sanctions and Anti-Money Laundering Act)** | UK financial sanctions enforcement | Compliant: tipping-off prevention in `sanctions_service.py`; OFSI feed daily refresh; ScreeningHit write-once table | `sanctions_service.py` + audit-log chain |
| **MiCA (Markets in Crypto-Assets, EU Reg 2023/1114)** | When AlgoVoi onboards EU-resident customers | Authorisation as a Crypto-Asset Service Provider (CASP) is required before providing services to EU residents in scope. **Currently AlgoVoi does not actively solicit EU customers.** Authorisation work tracked separately in `outreach/SECURITY-recommendations.md` Gap 2 + Gap 3. | This document + future regulatory filing |
| **DORA (EU Reg 2022/2554)** | Applicable to MiCA-regulated CASPs | This document is the ICT risk management framework required by DORA Article 6. ICT BCP per Article 11 is Section 6. ICT incident management per Article 17 is Section 5. Third-party risk per Article 28+ is Section 8. | This document |
| **PSD2 (UK domestic PSR 2017)** | Triggered when AlgoVoi performs payment services beyond crypto-asset activities | Currently AlgoVoi's services are crypto-asset-only. PSD2 authorisation considered in long-term roadmap when fiat services added. | N/A currently |
| **FCA Handbook (SYSC)** | When authorisation is granted | Senior Management Arrangements, Systems and Controls — covered by this document plus existing operational controls | This document |
| **SOC 2 Trust Services Criteria** | Customer requirement for enterprise B2B sales | This document maps to CC1–CC9. SOC 2 Type II audit scheduled subject to ≥5 paying tenants milestone | This document + control evidence |
| **ISO/IEC 27001** | Optional certification | Scoped roadmap item Q4 2026 if customer demand drives it | N/A |
| **PCI DSS** | Triggered if AlgoVoi processes card data | AlgoVoi does NOT process card data (crypto-only). PCI DSS not applicable. | Documented exclusion |

---

## 12. Policy review and exception process

### 12.1 Quarterly review

This policy is reviewed every quarter. Review minutes are recorded in **Appendix F**. The review covers:

- Risk-register changes (new risks, re-scored risks, retired risks)
- Control changes (new controls, deprecated controls, control failures)
- Incident outcomes since last review
- Regulatory landscape changes (new applicable regulations, new guidance from the FCA / ICO / EBA)
- Third-party supplier changes
- Policy amendments needed

### 12.2 Exception register

When a policy requirement cannot be met within the requirement's timeline, a documented exception is filed. The exception lives in this section's appendix and includes:

- The requirement (which section / which control)
- The reason it cannot currently be met
- The compensating control(s) in place
- The owner
- The target close date
- The risk-acceptance score (per Section 3.2)
- The next review date

**Current exceptions:**

| Exception ID | Requirement | Reason | Compensating control | Owner | Target close | Risk score |
|---|---|---|---|---|---|---|
| E-01 | Section 4.1 — Independent ISO / CISO | Single-person team | Christopher Hopley is publicly named ISO; documented role-separation-in-time. Independent CISO not required at current scale. | Christopher Hopley | When team ≥3 people | 6 |
| E-02 | Section 4.1 — External / regulated MLRO | Single-person team | Christopher Hopley is publicly named MLRO at `algovoi.co.uk/compliance.html` and `compliance@algovoi.co.uk`. Internal appointment paperwork is in place. **Open piece:** formal external regulator notification (FCA / HMRC scope determination, fit-and-proper Disclosure & Barring Service check, NCA SARonline registration, OFSI sanctions reporting registration) — these unlock at the FCA registration milestone. | Christopher Hopley | At first paying-tenant milestone | 6 |
| E-03 | Section 7.3 — Annual penetration test | Pre-revenue scale; budget to deploy at first-paying-tenant milestone | Internal quarterly OWASP Top 10 self-assessment | Founder | Q4 2026 (post-tenant-#5) | 6 |
| E-04 | Section 6.1 — Documented BCP tabletop exercise (annually) | First scheduled for 2026-08-03 | Per-failure-mode playbooks documented in Appendix C; informal walk-throughs done | Founder | 2026-08-03 | 4 |
| E-05 | Section 4.6.3 — Postgres full-disk encryption | LUKS deferred per `docs/SECURITY_KYB_AT_REST_2026-04-26.md` interim policy | File-level Fernet encryption-at-rest for special-category data is in place. Trigger to revisit: 25 paying tenants OR 100 KYB docs OR 90 days from 2026-04-26 (i.e. by 2026-07-25). | Founder | 2026-07-25 | 6 |
| E-06 | Section 4.6.4 — Inter-VM encrypted overlay | WireGuard mesh planned but not deployed | TLS-only Cloudflare → VM1; SSH-tunnelled VM1↔VM2 backup transfer | Founder | Q3 2026 | 6 |
| E-07 | Section 10.3 — DPIA filed | Scheduled Q3 2026 | KYB encryption-at-rest implemented; data minimisation enforced at upload (50MB cap, MIME whitelist) | Founder | Q3 2026 | 6 |
| E-08 | Section 10.4 — ROPA published | Scheduled Q3 2026 | Processing activities documented informally in this policy + per-service code | Founder | Q3 2026 | 4 |
| E-09 | Section 4.5 — GPG signed commits | Not yet enforced | Authentication via SSH key + audit-log record on deploy | Founder | Q3 2026 | 4 |
| E-10 | Section 4.6.1 — Static admin key fallback removed | Legacy compatibility | Static key has narrow scope; usage logged in `AdminAuthCounters.static_success`; rotation cadence per `memory/reference_secret_rotation.md` | Founder | Q3 2026 (Gap 5) | 6 |

Each exception is reviewed at the quarterly policy review.

### 12.3 Amendment log

Every change to this document is recorded in **Appendix F** with date, author, summary of change, and reason.

---

## 13. Related policies

This policy is the umbrella ICT risk management framework. The following companion policies in the same `compliance/` directory are authoritative for their specific topics. Each is reviewed on the same quarterly cadence as this policy.

### Security & operations

- [`ACCESS_CONTROL_POLICY.md`](ACCESS_CONTROL_POLICY.md) — least-privilege principles, MFA mandates, SSH key management, quarterly access reviews
- [`CHANGE_MANAGEMENT_POLICY.md`](CHANGE_MANAGEMENT_POLICY.md) — git-based workflow, code review requirements, rollback discipline, emergency-change handling
- [`INCIDENT_RESPONSE_PLAN.md`](INCIDENT_RESPONSE_PLAN.md) — severity levels, containment playbook, blameless post-mortem template (companion to Section 5 + Appendix B of this document)
- [`BUSINESS_CONTINUITY_PLAN.md`](BUSINESS_CONTINUITY_PLAN.md) — backup strategy, disaster scenarios, annual DR drill (companion to Section 6 + Appendix C of this document)
- [`VENDOR_MANAGEMENT_POLICY.md`](VENDOR_MANAGEMENT_POLICY.md) — subprocessor register, onboarding criteria, breach notification obligations (companion to Section 8 + Appendix D)
- [`ACCEPTABLE_USE_POLICY.md`](ACCEPTABLE_USE_POLICY.md) — confidentiality, device hygiene, AI tooling rules, reporting obligations

### AML / financial-crime

- [`AML_POLICY.md`](AML_POLICY.md) — three-line-of-defence model, MLRO accountability, UK MLR 2017 alignment, BWRA-driven risk approach
- [`BWRA.md`](BWRA.md) — Business-Wide Risk Assessment per UK MLR Reg 18 (public summary; full document Tier B under NDA)
- [`CDD_EDD_PROCEDURE.md`](CDD_EDD_PROCEDURE.md) — Customer Due Diligence + Enhanced Due Diligence; KYC-unlocks-mainnet gate; ongoing monitoring (Tier B)
- [`CUSTOMER_RISK_SCORING_MATRIX.md`](CUSTOMER_RISK_SCORING_MATRIX.md) — risk dimensions, banding, decision overrides, re-scoring cadence (Tier B)
- [`SANCTIONS_PROCEDURE.md`](SANCTIONS_PROCEDURE.md) — UK / EU / US / UN sanctions screening, match handling, OFSI reporting (Tier B)
- [`PEP_SCREENING_PROCEDURE.md`](PEP_SCREENING_PROCEDURE.md) — PEP definitions, FCA FG17/6 risk-based handling, EDD checklist (Tier B)
- [`TRANSACTION_MONITORING_PROCEDURE.md`](TRANSACTION_MONITORING_PROCEDURE.md) — rule families, alert handling, segregation of duties, tuning cadence (Tier B)

### Data protection / privacy

- [`ROPA.md`](ROPA.md) — UK GDPR Article 30 Record of Processing Activities (public summary; full RoPA Tier B under NDA)
- [`DPA_TEMPLATE.md`](DPA_TEMPLATE.md) — Article 28 Data Processing Agreement template (UK GDPR + UK IDTA / SCCs)
- [`DATA_BREACH_PROCEDURE.md`](DATA_BREACH_PROCEDURE.md) — detect → contain → assess → notify (72-hour ICO path) → remediate → review
- [`COMPLAINTS_PROCEDURE.md`](COMPLAINTS_PROCEDURE.md) — channels, acknowledgement timelines, escalation routes (ICO, FCA, OFSI, Action Fraud)
- [`RETENTION_PROCEDURE.md`](RETENTION_PROCEDURE.md) — per-category retention schedule, erasure handling, backup ageing

### Customer-facing surfaces

- [`algovoi.co.uk/compliance.html`](https://algovoi.co.uk/compliance.html) — canonical public compliance hub with status badges, regulatory scope, AML/CTF programme, security infrastructure, full policy library
- [`docs.algovoi.co.uk/security`](https://docs.algovoi.co.uk/security) — developer/auditor-friendly trust page summarising controls
- [`docs.algovoi.co.uk/compliance`](https://docs.algovoi.co.uk/compliance) — developer-facing compliance overview

### Cross-references

- Sister policies are NOT to be amended without parallel review of this document.
- Where this document and a sister policy disagree, the sister policy wins for its specific topic; this document is updated at the next quarterly review to reflect the conflict.

---

# Appendix A — Top-15 risk register

Full register. Likelihood × Impact = Residual Score. Treatment column shows current status.

### R-01 — Customer wallet compromise via UX phishing

- **Description:** A user is tricked into approving a malicious transaction in their non-custodial wallet on a phishing site impersonating AlgoVoi.
- **Likelihood:** 4 (Likely)  ·  **Impact:** 3 (Moderate; per-customer fund loss, reputational impact)  ·  **Score:** 12
- **Treatment:** Mitigate. Controls: documented signing-message templates, gradient-styled UI for AlgoVoi-issued mandates, EIP-712 typed data (xChain), Solana Pay reference binding (Solana), QR-code-only flows where possible.
- **Residual after treatment:** 6 (Likelihood lowered to 2)
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-02 — `KYB_ENCRYPTION_KEY` loss

- **Description:** The Fernet key used to encrypt KYB documents at rest is lost (e.g., founder's offline backup destroyed, in-memory copy not recoverable).
- **Likelihood:** 1 (Rare)  ·  **Impact:** 5 (Catastrophic; encrypted KYB docs become permanently unreadable)  ·  **Score:** 5
- **Treatment:** Mitigate. Multiple offline backups: founder's `.secrets` folder + physical secondary. Documented rotation procedure (`memory/reference_secret_rotation.md`).
- **Residual:** 5 (impact unchanged; likelihood already minimised)
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-03 — `HMAC_ENCRYPTION_KEY` compromise

- **Description:** The Fernet key encrypting tenant secrets is exfiltrated, allowing an attacker with DB access to decrypt webhook secrets, OAuth tokens, MFA seeds.
- **Likelihood:** 2 (Unlikely; key is in `/opt/algovoi/.env` mode 0600 root-owned)  ·  **Impact:** 4 (Severe; tenant compromise across the platform)  ·  **Score:** 8
- **Treatment:** Mitigate. MultiFernet rotation slot allows zero-downtime rotation. Quarterly rotation cadence. Separate from `KYB_ENCRYPTION_KEY`.
- **Residual:** 4 (likelihood lowered to 1 if rotation is operated)
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-04 — Sanctions screening miss

- **Description:** A wallet on the OFSI / OFAC list is processed for payment without being detected (cache stale, indexing miss, false-negative match).
- **Likelihood:** 2 (Unlikely; daily refresh + indexed lookup)  ·  **Impact:** 4 (Severe; UK MLR Reg 28 enforcement action, reputation, possible criminal liability)  ·  **Score:** 8
- **Treatment:** Mitigate. Daily refresh of cache; indexed `wallet_address_normalised` lookup; ScreeningHit table write-once + hash-chained; tipping-off prevention. Background re-screen on cache update catches misses. MLRO review of all hits within 24h business-day.
- **Residual:** 4
- **Owner:** Founder (acting MLRO). **Next review:** 2026-08-03.

### R-05 — Audit log integrity break (with no off-VM copy)

- **Description:** A root-account-holder DROPs the audit_log + screening_hits + compliance_events tables and the in-memory hash chain is lost.
- **Likelihood:** 1 (Rare; requires root-on-VM1 + intent)  ·  **Impact:** 5 (Catastrophic; SOC 2 + FCA evidence impossible)  ·  **Score:** 5
- **Treatment:** Mitigate. (i) Postgres RULE prevents UPDATE/DELETE; (ii) hash chain detects in-DB tampering (migrations 095/096); (iii) Object Lock shipping (migration 097) makes the off-VM copy unbypassable for 7 years once Vultr Object Storage bucket is provisioned.
- **Residual:** 2 (when Object Lock bucket active); 5 currently (NoopChainShipper running until bucket created)
- **Owner:** Founder. **Next review:** 2026-08-03 — re-score after Vultr Object Storage bucket provisioned.

### R-06 — Single VM1 host failure

- **Description:** Vultr loses VM1 — instance gone, IP gone, disk gone.
- **Likelihood:** 2 (Unlikely; Vultr SLA)  ·  **Impact:** 4 (Severe; full platform outage until VM2 promotion)  ·  **Score:** 8
- **Treatment:** Mitigate. Daily Postgres + KYB-doc backups to VM2. RTO 4h documented. VM2 capable of provisioning a replacement VM1-shape within hours.
- **Residual:** 6 (likelihood unchanged; impact lowered with documented RTO)
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-07 — Postgres data corruption

- **Description:** Logical or physical corruption of the Postgres data directory.
- **Likelihood:** 1 (Rare; modern Postgres + ECC RAM + SSD)  ·  **Impact:** 4  ·  **Score:** 4
- **Treatment:** Mitigate. Daily pg_dump backup; weekly automated restore-test on VM2. PITR planned (currently RPO is 24h, would drop to 5 min with WAL shipping).
- **Residual:** 4
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-08 — Backup transfer over plaintext

- **Description:** VM1 → VM2 daily Postgres backup currently traverses public internet via SSH; not the highest-risk path but the only documented inter-VM gap.
- **Likelihood:** 2 (Unlikely; SSH already encrypted)  ·  **Impact:** 3 (Moderate; backup bytes contain encrypted KYB blobs but unencrypted Postgres rows)  ·  **Score:** 6
- **Treatment:** Mitigate. SSH is the current control. WireGuard mesh planned (Exception E-06).
- **Residual:** 4 (when WireGuard active); 6 currently
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-09 — Cloudflare account compromise

- **Description:** Attacker gains control of AlgoVoi's Cloudflare account and changes DNS, intercepts TLS, etc.
- **Likelihood:** 2 (Unlikely; founder uses MFA + hardware key)  ·  **Impact:** 5 (Catastrophic)  ·  **Score:** 10
- **Treatment:** Mitigate. Hardware MFA on the Cloudflare login; quarterly review of Cloudflare audit log; documented incident-response playbook for Cloudflare compromise (Appendix C).
- **Residual:** 5 (likelihood lowered to 1 with hardware MFA)
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-10 — Supply-chain attack (compromised Python dependency)

- **Description:** A direct or transitive Python dependency is compromised and ships malicious code.
- **Likelihood:** 2 (Unlikely; AlgoVoi pins specific minor versions; Dependabot weekly)  ·  **Impact:** 4 (Severe)  ·  **Score:** 8
- **Treatment:** Mitigate. Pin minor versions in `pyproject.toml`. Dependabot enabled. Critical patches within 7 days. SBOM tracked.
- **Residual:** 4
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-11 — Third-party API outage (Alchemy, Helius, Allbridge)

- **Description:** A T2 supplier whose service is needed for some chain coverage goes down.
- **Likelihood:** 3 (Possible; transient outages happen)  ·  **Impact:** 2 (Minor; partial chain coverage degraded, others unaffected)  ·  **Score:** 6
- **Treatment:** Mitigate. Per-chain fallback documented (e.g., Alchemy → public RPC). Circuit breakers planned per `memory/plan_facilitator_scaling.md`.
- **Residual:** 4
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-12 — Founder unavailability (sickness, accident, death)

- **Description:** The single person operating all roles becomes unavailable suddenly. Platform continues running but no human can respond to incidents, regulator queries, customer issues.
- **Likelihood:** 3 (Possible — life events happen; small team magnifies impact)  ·  **Impact:** 4 (Severe; operational paralysis until succession)  ·  **Score:** 12
- **Treatment:** Mitigate. Documented operations-handover-pack including: this policy, runbooks, vendor logins, secret-key recovery procedures, regulator contacts. Pack stored with named successor (currently founder's spouse). Will-and-testament references the handover pack. Decryption keys held by named successor in sealed envelope.
- **Residual:** 8 (impact lowered to 2 with handover pack; likelihood unchanged)
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-13 — Insider threat (founder abuse)

- **Description:** Acknowledged self-pointing risk. Founder has full administrative access; no other party can technically prevent abuse.
- **Likelihood:** 1 (Rare; documented commitment + audit log)  ·  **Impact:** 5  ·  **Score:** 5
- **Treatment:** Mitigate. (i) Hash-chained audit log records every administrative action; (ii) Object Lock shipping ensures audit log is recoverable even if founder tries to erase; (iii) acknowledged commitment in this policy; (iv) future: independent CISO when team grows.
- **Residual:** 5
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-14 — Smart-contract bug (xChain LogicSig)

- **Description:** A bug in the AVM v11 LogicSig contract used by xChain (`xchain-accounts` repo) allows unauthorised transaction approval.
- **Likelihood:** 2 (Unlikely; LogicSig is small, audited internally, peer-reviewed)  ·  **Impact:** 3 (Moderate; affects only Algorand-mainnet xChain payments, not other chains)  ·  **Score:** 6
- **Treatment:** Mitigate. Bug bounty (planned). External smart-contract audit scheduled before xChain expands to additional chains. LogicSig source published at `chopmob-cloud/xchain-accounts`.
- **Residual:** 4
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

### R-15 — Static admin key fallback abused

- **Description:** A legacy static admin key remains as fallback alongside DB-backed keys. If exfiltrated, grants admin access without the DB key lifecycle controls.
- **Likelihood:** 2  ·  **Impact:** 4  ·  **Score:** 8
- **Treatment:** Mitigate. Used count is monitored via `AdminAuthCounters.static_success`. Removal scheduled (Gap 5 of `outreach/SECURITY-recommendations.md`).
- **Residual:** 4 (after removal); 8 currently
- **Owner:** Christopher Hopley (ISO). **Next review:** 2026-08-03.

---

# Appendix B — Incident response runbook (per scenario)

Per-scenario runbooks. Each follows the Detect → Triage → Contain → Eradicate → Recover → Review structure of Section 5.2.

### B-01 — Suspected admin-key compromise

**Detect.** Unusual `db_success` count, new admin key issued without ticket, login from unexpected IP in `last_used_at` history.

**Triage.** Severity P0. Open `incidents/YYYY-MM-DD-NN/` directory.

**Contain.**
1. Revoke the suspected key immediately: `UPDATE control_plane.admin_keys SET status='revoked', revoked_at=NOW(), revoked_reason='suspected compromise' WHERE key_id='hk_<id>'`.
2. Rotate `ADMIN_API_KEY` static fallback if it was the suspected key.
3. Audit-log the revocation.

**Eradicate.**
1. Force-rotate every admin key issued within the suspect window.
2. Review `audit_log` for any unauthorised actions taken with the suspect key.
3. If any unauthorised actions found, treat each as a sub-incident.

**Recover.**
1. Issue replacement keys to legitimate operators.
2. Reset MFA enrolment if compromised key was associated with an enrolled device.

**Review.** Post-incident review within 5 working days. Strengthen controls (e.g., shorten default key expiry, add IP allowlist, require hardware key for issuance).

### B-02 — Suspected encryption-key compromise (HMAC or KYB)

**Detect.** Disclosure of `/opt/algovoi/.env` content, lost laptop with Fernet key, vendor breach affecting key custody.

**Triage.** Severity P0.

**Contain.**
1. Generate new Fernet key. Set as primary.
2. Set old key as `*_KEY_OLD` (MultiFernet fallback).
3. Restart services to pick up new keys.

**Eradicate.**
1. Re-encrypt all rows: rewrite all `*_enc` columns through the encrypt cycle so they're backed by the new key.
2. For KYB documents: re-encrypt all on-disk files via `scripts/encrypt_kyb_docs_in_place.py` (idempotent). Existing files with the old AVK1+old-key are decrypted via MultiFernet's old-key slot, re-encrypted with new key.
3. After all rows + files re-encrypted, remove `*_KEY_OLD` from `.env`. Restart services.

**Recover.**
1. Verify integrity of re-encrypted data: spot-check decryption of representative rows + files.
2. Resume normal operations.

**Review.** Was the old key disclosed externally? If yes, ICO + affected-tenant notification per Section 5.3. Risk register update R-02 / R-03 with new mitigations.

### B-03 — Sanctions failure (live tx settled to a sanctioned address)

**Detect.** Background re-screen finds a wallet that received a payment is now on the sanctions list, OR upstream feed delay caused a missed match at payment time.

**Triage.** Severity P0. AML implication.

**Contain.**
1. Freeze the affected tenant (set `tenant.status = 'suspended'`).
2. Block the affected payee wallet from further payouts.
3. Notify acting MLRO within 1 hour.

**Eradicate.**
1. MLRO files an internal SAR per Proceeds of Crime Act 2002 s.330.
2. NCA SARonline submission within 30 days statutory.
3. FCA notification if material.
4. Payee funds frozen at the wallet level (cooperate with law enforcement on retrieval if requested).

**Recover.**
1. Tenant offboarded once investigation closed.
2. Sanctions cache refresh cadence reviewed; if cause was cache staleness, increase refresh frequency.

**Review.** Risk register R-04 update. Was the cause cache staleness, indexing failure, or upstream feed delay? Strengthen the relevant control.

### B-04 — KYB document leak

**Detect.** External report (researcher, customer), unauthorised access in audit log, public disclosure on social media.

**Triage.** Severity P0. UK GDPR Art. 33 + Art. 34 implications.

**Contain.**
1. Identify scope: which documents, which tenants, which subjects.
2. Disable any exposed access path.
3. Snapshot affected systems for forensic analysis.

**Eradicate.**
1. Determine root cause (misconfigured access, key compromise, application bug).
2. Apply fix.

**Recover.**
1. ICO notification within 72 hours (statutory).
2. Affected data subjects notification per Art. 34 timing.
3. Internal MLRO + insurance notification.
4. Post-incident communication to affected tenants.

**Review.** Risk register update. Add controls per ICO guidance.

### B-05 — VM1 full host failure

**Detect.** All `/health` endpoints unreachable. Vultr console shows instance failed.

**Triage.** Severity P0.

**Contain.**
1. Stand up a new Vultr instance (same region, larger size if cause was resource).
2. Restore from VM2 backup: Postgres + KYB documents + `/opt/algovoi/.env`.

**Eradicate.**
1. Determine cause via Vultr support.
2. If hardware: confirm new instance is on different physical host.

**Recover.**
1. Apply latest migrations (any not already in restored DB).
2. Pull container images, restart all services.
3. Update Cloudflare DNS to point to new IP.
4. Smoke test: `/health`, payment flow, dashboard login.
5. Re-enable iptables Cloudflare-only enforcement on new instance.
6. Record new IP in memory (`memory/reference_vm_connection.md`).

**Recovery time objective:** 4 hours.

**Review.** Was RTO met? Improve runbook based on actual recovery time.

### B-06 — Cloudflare account compromise

**Detect.** Login from unknown geography, DNS records changed without ticket, TLS certificate issued without request.

**Triage.** Severity P0.

**Contain.**
1. Reset Cloudflare account password from a clean device.
2. Verify hardware MFA is enrolled and active.
3. Review last 24h Cloudflare audit log for unauthorised changes.
4. Revert any unauthorised DNS / WAF / TLS changes.

**Eradicate.**
1. Rotate Cloudflare API tokens.
2. Review DNS for any unfamiliar records (subdomain takeovers).
3. If TLS cert was reissued maliciously: revoke it, reissue, monitor CT logs.

**Recover.**
1. Verify all sites resolve correctly.
2. Verify Cloudflare-only iptables rules still match current Cloudflare CIDR list.

**Review.** Strengthen Cloudflare account controls (recovery email locked down, login alerts).

### B-07 — Audit-log chain integrity break

**Detect.** `GET /internal/audit-log/verify-chain` returns `chain_intact: false`.

**Triage.** Severity P0.

**Contain.**
1. Snapshot current Postgres state (do not commit further audit-log writes if avoidable).
2. Identify the broken position from the verify endpoint response.
3. Compare current rows against the most recent Object Lock NDJSON shipment for that range.

**Eradicate.**
1. Determine what happened: was it a deliberate tamper, a Postgres corruption, an application bug, a row order glitch?
2. If tamper: treat as insider threat; preserve evidence; notify regulator if appropriate.
3. If corruption: restore from backup; replay from Object Lock shipments.
4. If application bug: file an emergency change.

**Recover.**
1. Re-run chain verification end-to-end.
2. Document the remediation.

**Review.** Risk register R-05 update. If Object Lock shipping was disabled at the time, treat it as a contributing failure and prioritise enabling.

### B-08 — Smart-contract bug (xChain LogicSig)

**Detect.** Unexpected on-chain transaction approved, customer complaint, security researcher disclosure.

**Triage.** Severity P0.

**Contain.**
1. Disable xChain on the affected tenants by toggling `xchain_enabled` flag.
2. Disable the xChain UI on the hosted checkout.

**Eradicate.**
1. Patch the LogicSig contract.
2. Deploy updated contract to a new address.
3. Update gateway code to use new contract address.
4. Migrate any existing user-derived addresses to the new contract.

**Recover.**
1. Re-enable xChain.
2. Communicate to affected tenants.

**Review.** External smart-contract audit if not already done.

---

# Appendix C — BCP playbook (per failure mode)

### C-01 — Single Docker container crash on VM1

**Symptom.** One service health check fails; other services healthy.

**Recovery.**

```bash
# SSH to VM1
ssh -i ~/.ssh/algovoi_deploy root@45.77.57.62
docker ps --filter "name=algovoi" --format '{{.Names}} {{.Status}}'
docker logs --tail 100 algovoi-<service>-1
docker restart algovoi-<service>-1
docker ps --filter "name=algovoi-<service>-1"
curl -s https://api1.ilovechicken.co.uk/health
```

**RTO:** 5 minutes.

### C-02 — VM1 reboot or kernel panic

**Symptom.** All services unreachable; SSH may or may not respond.

**Recovery.**

1. If SSH responds: `systemctl status docker` → confirm Docker is up → containers should auto-start (compose `restart: unless-stopped`).
2. If SSH doesn't respond: Vultr console; check console output for kernel panic; force-restart from console.
3. After reboot:
   ```bash
   docker ps   # all containers should be 'Up'
   curl -s https://api1.ilovechicken.co.uk/health
   ```

**RTO:** 15 minutes.

### C-03 — VM1 full host failure (instance gone)

See Appendix B-05.

**RTO:** 4 hours.

### C-04 — Postgres single-row corruption

**Symptom.** Specific query returns SQL error; all other queries fine.

**Recovery.**

1. Identify the affected row from the error message.
2. Retrieve the same row from the most recent VM2 backup:
   ```bash
   ssh -i ~/.ssh/algovoi_deploy root@<VM2_IP>
   pg_restore -t <table> --data-only --where="id=<id>" -f /tmp/row.sql /opt/algovoi-backups/postgres/latest.dump
   ```
3. Apply on VM1:
   ```bash
   psql ... -f /tmp/row.sql
   ```

**RTO:** 1 hour.

### C-05 — Postgres full DB corruption

**Symptom.** Postgres crashes on startup or fails consistency checks.

**Recovery.**

1. Stop the control plane / gateway / facilitator containers.
2. Restore Postgres from the most recent VM2 backup:
   ```bash
   docker exec algovoi-postgres-1 pg_restore -d algovoi_control_plane -c -h localhost /opt/backups/latest.dump
   ```
3. Verify migration version: `SELECT max(version) FROM schema_migrations;`. Apply any newer migrations from `migrations/control_plane/`.
4. Restart application containers.
5. Smoke test.

**RTO:** 4 hours.

**Data loss:** Up to 24h (RPO).

### C-06 — KYB document file corruption

**Symptom.** A specific KYB document fails to decrypt or returns an error.

**Recovery.**

1. Restore from the VM2 daily mirror:
   ```bash
   rsync -avz vm2:/opt/algovoi-backups/kyb_docs/<tenant_id>/<doc_id>.<ext> /app/kyb_docs/<tenant_id>/
   ```
2. Verify decryption:
   ```python
   from shared.utils.encryption import decrypt_bytes
   decrypted = decrypt_bytes(open('/app/kyb_docs/<tenant_id>/<doc_id>.<ext>', 'rb').read())
   ```
3. Update audit log with the recovery action.

**RTO:** 1 hour.

### C-07 — VM2 failure (no impact to live service)

**Symptom.** VM2 unreachable; backup destination missing.

**Recovery.**

1. Provision a replacement VM2 (Vultr).
2. Restore the off-site backup of `.env` + SSH keys.
3. Re-establish SSH key trust from VM1.
4. Run a manual on-demand backup to confirm.

**RTO:** 1 day. **Live-service impact:** None.

### C-08 — Cloudflare outage

**Symptom.** algovoi.co.uk + api1.ilovechicken.co.uk unreachable; Cloudflare status page red.

**Recovery.**

1. Confirm via Cloudflare status page (status.cloudflare.com).
2. If localised to a single Cloudflare datacentre: traffic auto-routes; no action required.
3. If global Cloudflare outage: traffic is unrecoverable until Cloudflare restores. Document the incident.
4. Long-term: secondary CDN/DNS provider (Fastly + Route 53) on a hot-standby — currently a Q4 2026 roadmap item.

**RTO:** Cloudflare-bound.

### C-09 — Founder unavailability

See Risk R-12 + Section 9 + Appendix E (tabletop).

**Recovery process triggered by named successor:**

1. Open the operations-handover-pack (sealed envelope at <named successor's address>).
2. Follow the documented procedures: vendor logins, secret keys, regulator contacts, customer support.
3. Engage external interim CISO from approved-vendor list.
4. Continuity of service maintained until permanent succession is decided.

**RTO:** 2 weeks for full normal operations; service continues uninterrupted in the immediate term.

---

# Appendix D — ICT supplier inventory

| Supplier | Service | Tier | Contract / DPA | Onboarded | Last reviewed | Next review |
|---|---|---|---|---|---|---|
| Vultr | VM1, VM2, VM3 hosting | T1 | Vultr ToS + Vultr DPA (signed 2026-01-15) | 2026-01-15 | 2026-04-01 | 2026-07-01 |
| Vultr Object Storage | Audit-log shipment storage (planned) | T1 | Vultr ToS + DPA (signed 2026-01-15) | TBD (when bucket provisioned) | n/a | 2026-08-03 |
| Cloudflare | WAF, CDN, DNS, TLS | T1 | Cloudflare Enterprise ToS + DPA | 2026-01-20 | 2026-04-01 | 2026-07-01 |
| GitHub | Source control | T1 | GitHub ToS + DPA | 2026-01-12 | 2026-04-01 | 2026-07-01 |
| Mintlify | docs.algovoi.co.uk hosting | T2 | Mintlify Pro ToS | 2026-04-26 | n/a | 2026-08-03 |
| Alchemy | Ethereum / Base RPC | T2 | Alchemy Free Tier ToS | 2026-04-22 | n/a | 2026-08-03 |
| Helius | Solana RPC | T2 | Helius Free Tier ToS | 2026-04-24 | n/a | 2026-08-03 |
| Allbridge | xChain bridging | T2 | Public-API ToS | 2026-04-25 | n/a | 2026-08-03 |
| MaxMind | GeoIP database | T3 | GeoLite2 free licence | 2026-04-15 | n/a | 2027-04-15 |
| OFSI | UK sanctions feed | T3 (statutory) | UK Government public feed | 2026-03-10 | 2026-04-01 | 2026-07-01 |
| OFAC | US sanctions feed | T3 (statutory) | US Treasury public feed | 2026-03-10 | 2026-04-01 | 2026-07-01 |
| EU consolidated list | EU sanctions feed | T3 (statutory) | EU Commission public feed | 2026-03-10 | 2026-04-01 | 2026-07-01 |
| Anthropic (Claude) | Internal dev AI | T3 | Anthropic Commercial ToS + DPA | 2026-02-01 | 2026-04-01 | 2026-07-01 |

Note: an "n/a" Last reviewed for new suppliers is filled in at the first quarterly review after onboarding.

---

# Appendix E — Annual tabletop exercise template

### Purpose

Walk an incident response from detection through review without touching production, to verify the playbooks in Appendix B work, identify gaps, and train responders.

### Cadence

At least annually. Additional exercises after material change (new chain integration, new vendor, regulatory change).

### Exercise structure

| Phase | Duration | Activity |
|---|---|---|
| Brief | 15 min | Facilitator selects scenario from Appendix B; participants gather; phones on; clocks running |
| Inject 1 — Initial | 10 min | Participants receive the first signal (e.g., "Customer reports unauthorised payout" — but no further information). Document first 10 min of triage actions. |
| Inject 2 — Escalation | 15 min | Facilitator adds complicating signals (e.g., "Cloudflare alert for unusual traffic + audit log shows admin login from foreign IP"). Document containment decisions. |
| Inject 3 — External | 10 min | Facilitator drops a regulator query (e.g., "FCA wants a 30-min update on the incident"). Document communications drafted. |
| Recovery | 20 min | Walk through Appendix B steps for the chosen scenario. Identify any step that doesn't translate cleanly. |
| Review | 30 min | Each participant lists: (1) what worked, (2) what didn't, (3) one improvement for the next exercise. |

### Documenting the exercise

The exercise produces:

- A timeline of every action and decision (`incidents/tabletop-YYYY-MM-DD/timeline.md`).
- An action-items list with owners and due dates (`incidents/tabletop-YYYY-MM-DD/actions.md`).
- Updates to relevant Appendix B / C runbooks if gaps were found.
- Updates to this policy if controls need to be added or strengthened.

### Schedule

| Date | Scenario | Lead |
|---|---|---|
| 2026-08-03 | TBD (first exercise; suggest B-05 VM1 full host failure as broadest test) | Founder |
| 2027-08-03 | TBD | Founder |
| 2028-08-03 | TBD | Founder |

---

# Appendix F — Document review log

| Version | Date | Author | Summary |
|---|---|---|---|
| 1.0 | 2026-05-03 | Founder | Initial issue. Establishes ICT risk management framework, security controls mapped to SOC 2 CC1–CC9 + DORA Articles 5–11, incident management runbook, BCP/DR with RPO/RTO, vulnerability management, third-party supplier register, exception register. Risk register Top-15. |

### Future amendment expectations

| Trigger | Document section affected | Cadence |
|---|---|---|
| Quarterly policy review | All sections, but typically Risk register, Exception register, Supplier inventory | Every 3 months |
| Post-P0 / P1 incident | Section 5 (incident management), affected Appendix B runbook, Risk register | Within 5 working days |
| New chain integration | Section 8 (suppliers), Appendix D, Risk register | At deploy |
| New paying tenant onboarded | Section 12 exceptions (E-03 pen test trigger, E-05 LUKS trigger) | At onboarding |
| Regulatory change (FCA, ICO, EU) | Section 11 (regulatory mapping) + affected control sections | Within 30 days of effective date |
| Personnel change (first hire, departure) | Section 9 (personnel) + Section 4 controls | At change |

---

**End of policy. Review next: 2026-08-03.**
