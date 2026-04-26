# Data Retention Procedure

**Owner**: Information Security Officer (ISO) — Christopher Hopley
**Approved by**: ISO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public

## 1. Purpose

To set out how long AlgoVoi retains each category of data, why, and how
that data is destroyed at end-of-life. Retention is one half of the data
minimisation principle (UK GDPR Article 5(1)(c) and (e)); destruction
is the other half.

## 2. Scope

Applies to all categories of personal data, transactional data, audit
data, and operational data processed by AlgoVoi as a controller or as a
processor on behalf of a merchant.

## 3. Retention principles

1. **Necessity** — we keep data only for as long as we have a defined
   reason to keep it.
2. **Statutory minima** — where a statutory minimum applies (e.g. five
   years post-relationship for AML records), the minimum sets the floor.
3. **Documented exceptions** — we may retain individual records longer
   where a regulator, court, or open investigation requires it; the
   exception is recorded and reviewed annually.
4. **Verifiable destruction** — destruction is logged. Encrypted backup
   tapes / snapshots that contain a deleted record are aged out on the
   schedule below; we do not "reach into" a backup to delete a single
   record.

## 4. Retention schedule

| Category | Examples | Retention | Trigger | Statutory basis |
|---|---|---|---|---|
| AML / KYC records | CDD documents, BWRA outputs, screening results, MLRO files | **5 years** | End of business relationship or date of relevant transaction (whichever is later) | UK MLR 2017, regs 40–41 |
| Suspicious Activity Report (SAR) records | SARs filed with NCA, supporting evidence | **5 years** | Filing date | POCA 2002 / TA 2000 |
| Transaction monitoring evidence | Rule hits, alert dispositions | **5 years** | Date of alert | UK MLR 2017 / firm-of-record obligation |
| Personal data breach records | Incident records, ICO correspondence | **6 years** | Closure date | UK GDPR Art. 33(5), Limitation Act 1980 |
| Complaint records | Complaint correspondence, decisions | **6 years** | Closure date | Industry expectation, Limitation Act 1980 |
| Contract and financial records | Merchant contracts, invoices, payment records | **6 years** | End of contract / final invoice | Limitation Act 1980, HMRC / Companies Act |
| Tax records | VAT, corporation tax, PAYE | **6 years** (current year + 5 prior) | Year-end | HMRC |
| Tenant audit logs (general) | API call logs, dashboard activity | **1 year** | Event date | Operational |
| Tenant audit logs (security-sensitive) | Auth failures, rate-limit breaches, sanctions hits | **5 years** | Event date | AML evidence chain |
| End-customer payment metadata | Checkout records, status, on-chain reference | **2 years** (active), then **archive** until retained until matching AML / contract minimum elapses | Checkout creation | Operational + AML |
| Backups | Encrypted snapshots of production database | **30 days rolling** | Snapshot date | Operational recovery (RTO/RPO) |
| Web-server access logs | nginx logs | **90 days** | Event date | Operational + abuse investigation |
| Encryption keys (rotated) | Old MultiFernet keys held during overlap window | **Held until last record encrypted under that key version is destroyed**, then destroyed | Key rotation date | Cryptographic discipline |
| Deleted account residue | Records flagged for erasure following an Article 17 request | **Tombstone for 30 days**, then irreversible deletion + backup-aging | Erasure-request acceptance | UK GDPR Art. 17 |
| Training records | AML / security training completion log | **5 years** | Training date | UK MLR 2017 evidence |
| Vendor / sub-processor records | Vendor due diligence files | **6 years** | End of vendor relationship | Limitation Act 1980 |

## 5. Erasure requests (Article 17)

Where an end-customer raises a verifiable erasure request:

1. AlgoVoi forwards the request to the relevant merchant Controller, who
   is the primary controller of end-customer data.
2. AlgoVoi deletes its own processor-side records of the data subject
   within **30 days** of the Controller's confirmed instruction.
3. Where AlgoVoi must retain a record to meet a statutory minimum
   (e.g. AML), the record is restricted (not deleted) and held in a
   limited-access archive until the statutory minimum elapses.

## 6. Backup ageing

Encrypted backup snapshots are retained on a rolling 30-day window. When
a record is erased, AlgoVoi does not selectively scrub backups; instead,
the backup containing the record ages out within 30 days, after which
the data is gone from backups too. End-customers and merchants are
informed of this convention as part of any erasure response.

## 7. Destruction methods

| Medium | Method |
|---|---|
| Database row | Cryptographic erasure where applicable; otherwise SQL delete + backup-ageing |
| File on disk | OS delete + filesystem trim; for encrypted volumes, key destruction is sufficient |
| Backup snapshot | Storage-layer expiry per retention window; snapshot keys destroyed on expiry |
| Paper records (rare) | Cross-cut shred and disposal via a confidential-waste contractor |
| End-of-life storage media | Physical destruction or NIST 800-88 Purge |

## 8. Roles

| Role | Responsibility |
|---|---|
| ISO | Owns this procedure; reviews annually |
| MLRO | Confirms AML retention compliance |
| Engineering | Implements retention controls and erasure tooling |
| All personnel | Do not retain copies of confidential or restricted data outside approved systems |

## 9. Review

Reviewed annually and on any material change to law, regulation, or
AlgoVoi's processing.

## 10. Related documents

- [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
- [Data Breach Procedure](DATA_BREACH_PROCEDURE.md)
- [AML Policy](AML_POLICY.md)
- [DPA Template](DPA_TEMPLATE.md)
- [Complaints Procedure](COMPLAINTS_PROCEDURE.md)
