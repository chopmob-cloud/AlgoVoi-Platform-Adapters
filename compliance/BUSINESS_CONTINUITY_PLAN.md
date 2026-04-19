# Business Continuity and Disaster Recovery Plan

**Owner**: Information Security Officer
**Effective**: 2026-04-19
**Next review**: 2027-04-19 (or after any event that triggers the plan)
**SOC 2 mapping**: Availability (A1)

## 1. Purpose

Ensure AlgoVoi can continue or rapidly resume critical operations during
and after a disruption — whether caused by infrastructure failure, vendor
outage, natural event, human error, or security incident.

## 2. Critical services

| Service | Definition of "up" | Criticality |
|---|---|---|
| **Payment link creation API** | `POST /v1/payment-links` returns 2xx for valid requests | Tier 1 (critical) |
| **On-chain settlement verification** | Payment status updates within 2 minutes of chain confirmation | Tier 1 |
| **Webhook delivery** | Events delivered to merchant webhook URLs with ≤ 1 minute delay | Tier 1 |
| **Merchant dashboard** | dash.algovoi.co.uk serves authenticated pages | Tier 2 |
| **Signup / onboarding** | New-tenant registration works | Tier 3 |
| **Reporting / analytics** | Historical payment reports available | Tier 3 |

## 3. Recovery objectives

| Service tier | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) |
|---|---|---|
| Tier 1 | 1 hour | 15 minutes of data loss |
| Tier 2 | 4 hours | 1 hour |
| Tier 3 | 24 hours | 4 hours |

These are commitments the service is **built to meet**. Actual performance
is reviewed quarterly against real incidents.

## 4. Backup strategy

### 4.1 Database (PostgreSQL)

- **Continuous**: WAL (write-ahead log) archiving every 5 minutes to an off-host location
- **Daily**: Full pg_dump snapshot, retained for 30 days
- **Weekly**: Full snapshot, retained for 12 weeks
- **Monthly**: Full snapshot, retained for 12 months
- **Annual**: Full snapshot, retained for 5 years (AML requirement)
- **Encryption**: All backups are encrypted at rest (AES-256) and in transit (TLS)
- **Off-site**: At least one copy stored in a geographically distinct region from primary

### 4.2 Code and configuration

- Primary: GitHub (source code, CI configuration, IaC)
- Mirror: Local clones held by the ISO; periodic archive to long-term cold storage
- Secrets: stored in the server environment + the ISO's password manager (1Password or equivalent); not in Git

### 4.3 Operational data

- Cloudflare configuration: scripted where possible (`cloud/scripts/cloudflare_waf.py`), otherwise documented in runbooks
- DNS: registrar + Cloudflare both retain history; manual restoration possible
- TLS certificates: Let's Encrypt auto-renews; certs can be re-issued from scratch in ≤ 1 hour

## 5. Backup verification

- **Weekly**: Automated restore test against the most recent full snapshot into an isolated instance; query the restored database for sanity checks
- **Quarterly**: Full DR drill — bring up a complete stack from backups, run smoke tests against it, tear down
- Results logged and reviewed by the ISO

Unverified backups don't count. A backup that can't be restored is a backup
that doesn't exist.

## 6. Disaster scenarios

### 6.1 Primary region / host outage

- **Trigger**: Vultr VPS unavailable for > 10 minutes
- **Response**: Restore from latest backup to a standby host in a different region (new VPS provisioned from snapshot or rebuilt from Ansible/Terraform)
- **Target RTO**: 1 hour for Tier 1
- **Data loss**: ≤ 15 minutes (WAL replay gap)

### 6.2 Database corruption

- **Trigger**: Logical corruption detected (failed queries, invariant violations)
- **Response**: Restore to latest consistent snapshot, replay WAL up to the point before corruption
- **Target RTO**: 2 hours
- **Data loss**: potentially up to the full RPO for Tier 1

### 6.3 Vendor outage (Cloudflare)

- **Trigger**: Cloudflare unreachable or widely degraded
- **Response**: Fall back to direct-origin DNS (Cloudflare bypassed); accept loss of WAF/DDoS protection temporarily
- **Target RTO**: 1 hour
- **Impact**: Service stays up with reduced protection; monitor for abuse
- **Caveat**: Direct-origin IP exposure means future re-hardening may be needed; document and remediate post-outage

### 6.4 Vendor outage (Vultr)

- **Trigger**: Host provider unavailable
- **Response**: Restore from off-site backups to an alternative provider (a pre-vetted backup provider is documented in the vendor register — e.g., DigitalOcean, Hetzner)
- **Target RTO**: 4 hours (Tier 1 elevated due to provisioning lead time)

### 6.5 Credential compromise

- **Trigger**: Any indication that production credentials are exposed
- **Response**: Follow the Incident Response Plan. Rotate all credentials in a defined order: edge (Cloudflare), then production (SSH, database), then tenant secrets (API keys, webhook secrets)
- **Target RTO**: 30 minutes to contain (credential rotation)

### 6.6 Key personnel unavailable

- **Trigger**: ISO or sole on-call unavailable for > 4 hours during an incident
- **Response**: Defined backup on-call (currently: an external advisor with delegated authority under a documented agreement)
- **Mitigation**: No single person holds an irreversible key. All critical credentials have at least one recoverable path (password manager with emergency access, inheritance contact registered with registrar/GitHub/Cloudflare).

### 6.7 Regulatory / legal injunction

- **Trigger**: Service is required to cease operation in a jurisdiction
- **Response**: Notify affected merchants; route traffic out of that jurisdiction where feasible; comply with the order while preserving evidence and contesting through legal channels if appropriate

## 7. Communication during a disruption

Primary channel: **status page** (`status.algovoi.co.uk` — to be stood up).
Secondary: email blast to registered merchant contacts.

Updates are posted at least every **30 minutes** during a SEV 1 incident,
every **2 hours** during SEV 2.

Honest communication rule: we say what we know, say what we don't know, and
say when we'll next update. We don't speculate or minimise.

## 8. Return to normal

After a disruption:

1. Confirm all services at target performance
2. Verify no data loss beyond the stated RPO
3. Notify affected merchants of resolution
4. Conduct a post-mortem within 7 days
5. Update this plan if the event revealed gaps

## 9. Testing this plan

- Tabletop exercises (walk through scenarios without executing): quarterly
- Live DR drills (actually restore to standby): annually
- Findings feed into the next revision of this document

## 10. Dependencies

Critical external dependencies tracked in the [Vendor Management Policy](VENDOR_MANAGEMENT_POLICY.md):

- Cloudflare — DDoS, WAF, CDN
- Vultr — compute
- GitHub — source code hosting
- npm / PyPI — package distribution
- Let's Encrypt — TLS certificates
- Blockchain nodes (our own + failover providers) — chain data
- Sanctions feeds (OFAC, OFSI) — AML compliance

Each has a documented failover or manual workaround.
