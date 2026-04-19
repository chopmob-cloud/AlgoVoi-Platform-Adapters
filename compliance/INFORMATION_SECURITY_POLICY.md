# Information Security Policy

**Owner**: Information Security Officer (ISO) — Christopher Hopley
**Approved by**: ISO
**Effective**: 2026-04-19
**Next review**: 2027-04-19 (or upon material change)
**SOC 2 mapping**: CC1 (Control Environment), CC2 (Communication), CC3 (Risk Assessment), CC4 (Monitoring), CC5 (Control Activities)

## 1. Purpose

To establish AlgoVoi's baseline security posture — what we protect, how we
protect it, and who is responsible — so that merchants, partners, and auditors
have a clear, honest statement of our practices.

## 2. Scope

Applies to every system, person, and vendor involved in processing merchant or
end-customer data through AlgoVoi. This includes production infrastructure,
source code repositories, package registries, development environments,
vendor SaaS tools, and personal devices used for AlgoVoi work.

## 3. Information classification

All data AlgoVoi handles falls into one of four tiers:

| Tier | Description | Examples | Protection |
|---|---|---|---|
| **Public** | Safe to distribute widely | Open-source adapter code, public documentation, marketing pages | No controls |
| **Internal** | Not secret but not for external distribution | Architecture notes, backlogs, internal runbooks | Access limited to authorised personnel |
| **Confidential** | Could cause harm if disclosed | Merchant business details, payment metadata, API key hashes, webhook secrets | Encryption at rest + in transit; access on need-to-know |
| **Restricted** | Direct legal/financial/safety impact if disclosed | Plaintext API keys (transient only), admin credentials, private keys, root passwords | Encryption + MFA + audit logging; never emailed, never pasted into chat, never committed to Git |

Public on-chain data (transaction IDs, wallet addresses, on-chain amounts) is
not AlgoVoi's data — it is already public — and is excluded from this
classification.

## 4. Responsibilities

| Role | Responsibilities |
|---|---|
| Information Security Officer | Owns this policy; reviews annually; approves deviations; final escalation for incidents |
| All personnel | Read and follow this policy; complete security awareness refresher annually; report any suspected incident within 1 hour of awareness |
| Vendors / subprocessors | Meet the security obligations in their contracts; notify AlgoVoi of any breach within 24 hours of discovery |

## 5. Principles

### 5.1 Defence in depth

No single control protects against compromise. We layer:

1. **Edge**: Cloudflare WAF + DDoS mitigation + bot protection
2. **Transport**: HTTPS everywhere; HSTS preload; TLS 1.2+ only; strict cipher suites
3. **Application**: Per-tenant rate limiting (token bucket); input validation; HMAC-verified webhooks; authenticated-origin-only access
4. **Data**: Encryption in transit (TLS), encryption at rest (Postgres AES-256 for disk), Fernet-encrypted session tokens
5. **Code**: No secrets in Git; branch-protected main; code review required; dependency scanning
6. **Identity**: GitHub OAuth for dashboard; MFA on every admin surface; SSH key auth only (no passwords)
7. **Detection**: Structured audit logs per tenant; sanctions-screening hits logged; rate-limit breaches logged

### 5.2 Least privilege

Every identity gets the minimum access needed for its role. Access reviews
happen quarterly and whenever a role changes. Unused credentials are revoked
within 7 days of becoming unused.

### 5.3 No custody principle

AlgoVoi is non-custodial by architectural choice: merchant funds never pass
through AlgoVoi wallets. Settlement is direct on-chain. This materially
reduces the impact of any breach — we cannot lose funds we do not hold.

### 5.4 Data minimisation

We collect only what is necessary to operate the service. We do not store
cardholder data (we process none), customer PII beyond what the merchant
sends us for order fulfilment, or wallet private keys (ever).

### 5.5 Transparency

Security practices are documented publicly in this repository. External
researchers are welcome to report vulnerabilities via the `/.well-known/security.txt`
route (see [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md)).

## 6. Encryption

| Where | Mechanism |
|---|---|
| **Data in transit (external)** | TLS 1.2 or higher, certificate issued by a public CA (currently Let's Encrypt / Cloudflare-managed) |
| **Data in transit (internal)** | Same TLS standards; service-to-service over private network on a single VPC |
| **Data at rest (database)** | PostgreSQL on disk with AES-256 encryption at the volume level |
| **Data at rest (backups)** | Encrypted at the storage layer + encrypted snapshot copies |
| **API keys** | Stored as bcrypt hashes; plaintext visible only once at issuance |
| **Session tokens** | Fernet-encrypted; rotated hourly; invalidated on logout |
| **Webhook secrets** | Stored encrypted; used server-side only for HMAC verification |
| **SSH access** | Ed25519 or RSA-4096 keys only; no password-based SSH to production |

## 7. Monitoring and logging

- All authenticated API calls are logged with tenant ID, endpoint, status code, and latency
- Failed authentication attempts, rate-limit breaches, and sanctions-screening hits are logged at higher fidelity
- Audit logs are append-only (Postgres RULE prevents update/delete on compliance tables)
- Logs are retained for **1 year minimum** (general) and **5 years** (AML-sensitive)
- Log integrity is verified periodically via a cryptographic hash chain

## 8. Vulnerability management

- Dependency scanning on every PR via Dependabot / npm audit / pip-audit
- Critical CVEs (CVSS ≥ 9.0) patched within **7 days**
- High CVEs (CVSS 7.0–8.9) patched within **30 days**
- Medium/Low CVEs reviewed quarterly
- Underlying OS patched monthly via `apt upgrade` during a scheduled maintenance window
- External penetration test conducted **annually** by an independent firm

## 9. Exceptions

Any deviation from this policy must be:

1. Justified in writing
2. Approved by the Information Security Officer
3. Time-bounded (max 90 days; renewable with fresh justification)
4. Tracked in a public exceptions register (redacted for security-sensitive items)

## 10. Enforcement

Policy violations are reviewed case-by-case. Material violations may result in
access revocation, employment/contract termination, and — where warranted —
legal or regulatory notification.

## 11. Related policies

- [Access Control Policy](ACCESS_CONTROL_POLICY.md)
- [Change Management Policy](CHANGE_MANAGEMENT_POLICY.md)
- [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md)
- [Business Continuity & DR](BUSINESS_CONTINUITY_PLAN.md)
- [Vendor Management Policy](VENDOR_MANAGEMENT_POLICY.md)
- [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md)
