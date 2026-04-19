# Access Control Policy

**Owner**: Information Security Officer
**Effective**: 2026-04-19
**Next review**: 2027-04-19
**SOC 2 mapping**: CC6 (Logical and Physical Access Controls)

## 1. Purpose

Define who gets access to what, under what conditions, and how access is
granted, reviewed, and revoked.

## 2. Scope

Applies to all systems that host AlgoVoi code, data, or operational
infrastructure.

## 3. Identity

Every access-granting action attaches to a named identity (person or service
account). Shared accounts are prohibited.

| System | Identity source |
|---|---|
| AlgoVoi Cloud dashboard | GitHub OAuth |
| AlgoVoi Cloud API | Per-tenant API keys (`algv_*`) |
| GitHub organisation | GitHub accounts with MFA required |
| Cloudflare | Cloudflare accounts with MFA |
| Vultr (hosting) | Vultr accounts with MFA |
| npm / PyPI | Per-publisher accounts; org-scoped tokens for CI |
| Production SSH | Ed25519 SSH keys, one per person |
| Production database | Postgres role per service + per operator |

## 4. Authentication requirements

| Access tier | Requirement |
|---|---|
| **End-user merchant dashboard** | OAuth via GitHub; provider enforces MFA |
| **API consumers** | Bearer `algv_*` token in `Authorization` header |
| **Admin access to infrastructure (Cloudflare, Vultr, npm, PyPI, GitHub org)** | MFA mandatory — TOTP app or hardware key |
| **Production SSH** | Ed25519 public key registered in `~/.ssh/authorized_keys`; password auth disabled in sshd |
| **Production database (direct)** | Separate Postgres role per operator; credentials never shared; access only from jump host |

## 5. Authorisation principles

- **Least privilege**: A new grant must be the minimum needed. "Admin" is not the default.
- **Need to know**: Access to Confidential/Restricted data requires a documented business reason.
- **Segregation of duties**: The person who authored a change should not be the only person who approves the deploy. (When the team is one person, an external code review via GitHub issues/PRs serves as a formal checkpoint; this will split with team growth.)
- **No standing admin**: Root access is reserved for break-glass scenarios.

## 6. Provisioning

New access grants follow this process:

1. Requester submits a request with business justification to the ISO.
2. ISO approves or denies within 1 business day.
3. Grant is applied (GitHub org invite, Cloudflare member add, SSH key registration, etc.).
4. Entry added to the access register (`compliance/ACCESS_REGISTER.md` — kept private, summarised publicly on request).

## 7. De-provisioning

Access is revoked within **24 hours** of:

- An employee or contractor leaving
- A role change that no longer needs the access
- Detection of credential compromise
- A vendor relationship ending

The ISO maintains a de-provisioning checklist that covers:

- GitHub org membership
- Cloudflare, Vultr, npm, PyPI memberships
- SSH public keys in `authorized_keys`
- Database roles
- Shared secrets known to the departing person (webhook secrets, API keys) — these are **rotated**, not just revoked
- Any personal devices used for AlgoVoi work — remote wipe or attestation of destruction

## 8. Access reviews

Scheduled reviews:

- **Quarterly**: all human identities, all systems — confirm each person still needs each grant they have
- **Annually**: all service accounts and machine-to-machine credentials — confirm still in use, rotate keys
- **On incident**: targeted review of any systems implicated in an incident

Evidence of each review is stored in the compliance Git repository.

## 9. Credential handling

- Plaintext API keys are shown **once** at issuance, then stored only as bcrypt hashes
- Webhook secrets, service-account credentials, and similar shared secrets are stored in the server environment, never in Git
- Personal credentials (your login password, your authenticator seed) are never shared with anyone — not even the ISO
- Shared secrets (webhook signing keys, third-party API keys) are rotated on a schedule (at minimum annually) and immediately upon suspected compromise

## 10. SSH key management

- Keys are Ed25519 (preferred) or RSA-4096
- Each person has a **named** key (filename or comment identifies owner)
- Keys are rotated at least annually or on device replacement
- SSH passwords are disabled on all production hosts (`PasswordAuthentication no` in `sshd_config`)

## 11. Privileged operations

Actions that can cause broad impact (deploy to production, rotate a database
credential, modify DNS, rotate a webhook secret) must:

- Be captured in a deploy log with a link to the commit or change ticket
- Be reviewed by a second person when the team is ≥2 people (today, the ISO is the reviewer; self-review is flagged honestly in the deploy log)
- Trigger a notification to the on-call channel

## 12. Physical access

AlgoVoi does not operate physical datacentres. Physical security is
inherited from our IaaS provider (Vultr) under their data-centre compliance
programme. Staff devices must:

- Auto-lock after 5 minutes of inactivity
- Encrypt the disk (FileVault / BitLocker / LUKS)
- Run a supported and patched OS
- Not store Confidential/Restricted data beyond what is needed for an active task

## 13. Exceptions

Same process as the [Information Security Policy](INFORMATION_SECURITY_POLICY.md#9-exceptions).

## 14. Enforcement

Violations may result in immediate access revocation and, depending on
severity, contract termination and regulatory notification.
