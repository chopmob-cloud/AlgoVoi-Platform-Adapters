# Change Management Policy

**Owner**: Information Security Officer
**Effective**: 2026-04-19
**Next review**: 2027-04-19
**SOC 2 mapping**: CC8 (Change Management)

## 1. Purpose

Ensure that changes to AlgoVoi's systems — code, infrastructure, data schemas,
and configuration — are deliberate, reviewed, traceable, and reversible.

## 2. Scope

Any change that affects production: code deploys, infrastructure changes,
DNS/TLS changes, vendor configuration, database migrations, third-party
credential rotation.

## 3. Types of change

| Class | Examples | Approval | Deploy window |
|---|---|---|---|
| **Standard** | Documentation, non-production features behind a flag, dependency patch bumps | 1 code review + passing CI | Any time |
| **Normal** | Production code, DB migration with rollback, new API endpoint, vendor change | 1 code review + passing CI + ISO awareness | Business hours preferred |
| **Emergency** | Security patch, actively failing service, regulatory requirement | ISO approval (can be retroactive if rolled within 30 min) | Immediate |

## 4. Process

All changes flow through GitHub pull requests. The PR is the change record.

### 4.1 Standard process

1. Author a branch from `master` (or `main`)
2. Write code + tests
3. Open a PR with a clear description: what, why, risk, rollback
4. CI must pass (build + tests + dependency scan)
5. At least one approval from a reviewer other than the author (when team ≥ 2)
6. Merge to `master`
7. Deployment triggers (manual for now; planned: CI-driven deploy to staging → prod)
8. Post-deploy verification (smoke test)

Single-person state: the author reviews their own PR honestly against a
documented checklist (`compliance/PR_CHECKLIST.md` — to be added), with
external code review from the community through open-source commits serving
as a parallel check. This will convert to dual-author review when the team
grows.

### 4.2 Emergency process

1. Identify the issue and its blast radius
2. Apply the fix directly to `master` (or a hot-fix branch)
3. Deploy
4. **Within 24 hours**: open a retrospective PR that documents what was done
   and why normal process was skipped
5. Review the retrospective at the next regular review

## 5. Deployment records

Every production deploy is logged with:

- Timestamp (UTC)
- Commit SHA
- Operator identity
- Services affected
- Verification outcome (pass / fail / partial)
- Rollback result (if any)

Logs are retained for **1 year**.

## 6. Rollback

Every change MUST have a defined rollback:

- **Application code**: revert commit + redeploy. Target ≤ 15 minutes.
- **Database migrations**: migrations are written with explicit down steps where safely possible. For one-way migrations, a snapshot is taken immediately before the migration runs.
- **Infrastructure (Cloudflare rules, DNS, vendor config)**: the change is scripted (see `cloud/scripts/cloudflare_waf.py` for example) and the script is idempotent so re-running with the prior configuration restores the previous state.
- **Vendor changes (new subprocessor, plan change)**: documented revert path before the change is made.

## 7. Secrets in change records

PRs and deploy logs must NOT contain:

- Plaintext API keys
- Plaintext passwords or tokens
- Private cryptographic keys
- PII beyond what is needed to describe the change

If a secret is accidentally committed:

1. Rotate the exposed secret immediately
2. Remove the commit from history via `git filter-repo` (precedent: we did
   this for `cloud/` and `grants/` in April 2026)
3. Force-push the scrubbed history
4. Open a post-mortem

## 8. Configuration as code

Wherever possible, production configuration is captured in source control:

- Application code: this repository
- Cloudflare WAF rules: `cloud/scripts/cloudflare_waf.py`
- Database schema: `migrations/`
- Infrastructure: (targeting Terraform — not yet in place)

Manual configuration on vendor dashboards is acceptable but must be
documented in the relevant runbook and, where feasible, automated later.

## 9. Separation of environments

AlgoVoi maintains:

| Environment | Purpose | Data |
|---|---|---|
| **Production** | Real merchant traffic | Real tenant / payment data |
| **Testnet-facing production** | Merchant testing | Real tenants, testnet chains only, no real settlement |
| **Local development** | Developer workstations | Synthetic data only |

Data does not flow from production into development. When reproduction
requires real-world data, the specific record is sanitised first.

## 10. Approval matrix

| Change type | Requires approval from |
|---|---|
| Production code deploy | Author + reviewer (peer when team ≥ 2) |
| Database migration | Author + reviewer + ISO acknowledgement |
| Vendor change (new service, plan upgrade) | ISO |
| Security control change (WAF rule, rate limit, encryption parameter) | ISO |
| Emergency change | Post-hoc ISO review within 24 hours |

## 11. Audit

All changes are auditable via the Git commit history, the deploy log, and
the vendor-side audit logs (GitHub, Cloudflare, Vultr).
