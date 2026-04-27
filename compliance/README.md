# AlgoVoi — Compliance & Security Policies

This directory contains the internal policies that govern AlgoVoi's security,
privacy, and operational practices. They are **public by design** — merchants,
auditors, and security researchers can review them without NDA.

## Document set

### Security (Tier A — fully public)

| Policy | Maps to SOC 2 criteria | Last reviewed |
|---|---|---|
| [Information Security Policy](INFORMATION_SECURITY_POLICY.md) | Security (CC1–CC9) | 2026-04-19 |
| [Access Control Policy](ACCESS_CONTROL_POLICY.md) | Security (CC6) | 2026-04-19 |
| [Change Management Policy](CHANGE_MANAGEMENT_POLICY.md) | Security (CC8) | 2026-04-19 |
| [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md) | Security (CC7) | 2026-04-19 |
| [Business Continuity & Disaster Recovery](BUSINESS_CONTINUITY_PLAN.md) | Availability | 2026-04-19 |
| [Vendor Management Policy](VENDOR_MANAGEMENT_POLICY.md) | Security (CC9) | 2026-04-19 |
| [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md) | Security (CC1) | 2026-04-19 |

### AML / Privacy (Tier A — fully public)

| Policy | Last reviewed |
|---|---|
| [AML Policy](AML_POLICY.md) | 2026-04-26 |
| [DPA Template](DPA_TEMPLATE.md) | 2026-04-26 |
| [Data Breach Procedure](DATA_BREACH_PROCEDURE.md) | 2026-04-26 |
| [Complaints Procedure](COMPLAINTS_PROCEDURE.md) | 2026-04-26 |
| [Retention Procedure](RETENTION_PROCEDURE.md) | 2026-04-26 |

### AML / Privacy (Tier B — public summary, full document under NDA)

| Document | Last reviewed |
|---|---|
| [Business-Wide Risk Assessment (BWRA)](BWRA.md) | 2026-04-26 |
| [CDD/EDD Procedure](CDD_EDD_PROCEDURE.md) | 2026-04-26 |
| [Transaction Monitoring Procedure](TRANSACTION_MONITORING_PROCEDURE.md) | 2026-04-26 |
| [Record of Processing Activities (RoPA)](ROPA.md) | 2026-04-26 |
| [Customer Risk Scoring Matrix](CUSTOMER_RISK_SCORING_MATRIX.md) | 2026-04-26 |
| [Sanctions Screening Procedure](SANCTIONS_PROCEDURE.md) | 2026-04-26 |
| [PEP Screening Procedure](PEP_SCREENING_PROCEDURE.md) | 2026-04-26 |

### Tier C — statement only on the public compliance page

- SAR Procedure (operational; not published in detail per UKFIU guidance — capability statement only)
- MLRO designation (MLRO name and contact published on the compliance page)
- IP Assignment (statement: IP fully assigned to the operating company; document held internally)
- Training Log (statement: annual AML / security training completed; log held internally)

## Scope

These policies apply to:

- All systems operated by AlgoVoi that process, store, or transmit merchant data
- All personnel (employees, contractors, third parties) with access to AlgoVoi systems
- All vendors and subprocessors that handle AlgoVoi data

The policies do **not** cover:

- Merchant-side systems (WordPress stores, etc.) — those are the merchant's responsibility
- On-chain data — public by blockchain design, not in AlgoVoi's security scope
- Customer wallets — customers control their own keys

## Ownership

| Role | Holder | Contact |
|---|---|---|
| Information Security Officer (ISO) | Christopher Hopley | support@algovoi.co.uk |
| Data Protection Officer (DPO) | Christopher Hopley | support@algovoi.co.uk |
| Money Laundering Reporting Officer (MLRO) | Christopher Hopley | support@algovoi.co.uk |
| Incident Response Lead | Christopher Hopley | support@algovoi.co.uk |

Roles are currently consolidated while the team is small; they will be split as
the team grows. All communications are logged.

## Review cadence

Every policy is reviewed at least **annually** and whenever:

- A material change to infrastructure occurs (new vendor, new region, new product surface)
- A security incident triggers a post-mortem with policy implications
- Regulatory or certification requirements change
- An external auditor identifies a gap

Changes are tracked in this Git repository — every policy edit is a commit with
a clear message. The commit history is the audit trail.

## SOC 2 readiness

AlgoVoi is actively working toward SOC 2 Type II certification. Current status:

- **Type I audit**: target Q2 2027
- **Type II observation window**: Q2–Q3 2027
- **Type II report**: target Q4 2027

These policies exist now so merchants and partners can rely on them during
procurement, without waiting for the full certification timeline.

## Requesting a full audit package

Items covered here are public. Items available **under NDA** for prospective
enterprise partners:

- Full penetration test reports
- Internal network diagrams
- Detailed data flow maps with subprocessor specifics
- SOC 2 observation evidence (pre-certification)
- Incident post-mortems

Request via support@algovoi.co.uk with your business name, use case, and the
documents you need.
