# Personal Data Breach Procedure

**Owner**: Information Security Officer (ISO) — Christopher Hopley
**Approved by**: ISO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public
**SOC 2 mapping**: CC7 (System Operations), P5 (Privacy — Quality of Personal Information)

## 1. Purpose

To define how AlgoVoi detects, contains, assesses, notifies on, and learns
from personal data breaches, in line with Articles 33 and 34 of the UK GDPR
and the Data Protection Act 2018.

## 2. Scope

Applies to any actual, suspected, or imminent breach of personal data
processed by AlgoVoi as a controller (e.g. for AlgoVoi's own personnel) or
as a processor on behalf of a merchant.

## 3. What counts as a breach

A "personal data breach" is a breach of security leading to the accidental
or unlawful destruction, loss, alteration, unauthorised disclosure of, or
access to, personal data transmitted, stored, or otherwise processed.

This includes:

- Unauthorised access to a database, server, or backup
- Loss or theft of a device containing personal data
- Misdirection of personal data (e.g. wrong recipient on an email)
- Ransomware or other malware that renders personal data inaccessible
- Accidental disclosure (e.g. mis-shared file, mis-configured access)

A near-miss (where the breach was prevented before any data was actually
exposed) is logged but does not trigger external notification.

## 4. Detection sources

Breaches may be detected via:

- Internal monitoring (audit-log alerts, intrusion-detection, anomaly
  detection)
- Vendor or sub-processor notification (sub-processor contracts require
  notification within 24 hours)
- External researcher report via `/.well-known/security.txt`
- Customer or merchant report
- Law-enforcement or regulator notification

## 5. The 6-step procedure

```
[1] Identify   →  [2] Contain  →  [3] Assess   →
[4] Notify     →  [5] Remediate →  [6] Review
```

### Step 1 — Identify (within 1 hour of awareness)

The person discovering the breach informs the ISO via the dedicated
incident channel. The ISO opens a numbered incident record and assigns:

- Incident lead (default: ISO)
- Technical responder (default: on-call engineer)
- Communications lead (default: ISO)
- Clock-keeper (logs every action with timestamp)

### Step 2 — Contain (within 4 hours)

Immediate containment actions, sized to the incident:

- Revoke compromised credentials (API keys, sessions, SSH keys)
- Rotate webhook signing secrets
- Block hostile IP ranges at the edge
- Disable affected services if needed (kill switch)
- Snapshot evidence (logs, memory, disk image where appropriate) before
  any destructive remediation

### Step 3 — Assess (within 24 hours of awareness)

The incident lead documents:

- What personal data was affected (categories, volume, data subjects)
- Cause and timeline
- Actual or likely consequences
- Whether the breach is "likely to result in a risk to the rights and
  freedoms of natural persons" (the UK GDPR Article 33 trigger)
- Whether the breach is "likely to result in a high risk to the rights
  and freedoms of natural persons" (the Article 34 data-subject-
  notification trigger)

### Step 4 — Notify (within 72 hours of awareness)

Where Article 33 applies, the ISO files with the ICO at
`https://ico.org.uk/for-organisations/report-a-breach/` within 72 hours
of becoming aware. The notification covers the items required by
Article 33(3); incomplete notification is permitted (with a follow-up)
provided AlgoVoi gives reasons for any delay.

Where AlgoVoi is the processor, the merchant Controller is notified
within **48 hours** (per the [DPA Template](DPA_TEMPLATE.md), clause 4)
to give the Controller adequate margin for its own 72-hour ICO
notification.

Where Article 34 applies, affected data subjects are notified directly,
in clear and plain language, without undue delay.

For payment data and platform-security implications, the relevant
merchant Controllers are notified in parallel, regardless of whether
the personal data threshold is met, so they can advise their own
end-customers.

### Step 5 — Remediate

Permanent fixes are tracked in the incident record:

- Patch / configuration change deployed
- Compromised credentials replaced
- Logging or detection gap closed
- Vendor relationship escalated or terminated where the cause was
  third-party

### Step 6 — Review (within 30 days of closure)

A post-incident review is held with the ISO, the technical responder, and
(where relevant) the merchant Controller. The review captures:

- Root cause
- What worked, what did not
- Action items with owners and deadlines
- Whether this policy or any related policy needs updating

The post-incident review record is retained for **6 years** in line with
the [Retention Procedure](RETENTION_PROCEDURE.md).

## 6. Communications

Until the assessment is complete:

- Internal: the incident channel and the ISO only
- External: no comment beyond an acknowledgement that an incident is
  under investigation

After ICO notification (where applicable), and once the assessment is
complete, AlgoVoi may publish a public post-mortem. Sensitive details
(e.g. specific exploit chains) may be withheld where publication would
materially increase risk for AlgoVoi or its merchants.

## 7. Tipping off

Where the breach also constitutes (or may constitute) money laundering,
terrorist financing, or another reportable suspicion, the MLRO is
involved before any notification is made, to avoid breaching the
tipping-off prohibition under POCA 2002 s.333A.

## 8. Records

Per Article 33(5) of the UK GDPR, AlgoVoi maintains an internal record of
all personal data breaches — including those that did not require ICO
notification — for a minimum of **6 years**.

## 9. Related documents

- [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
- [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md)
- [Business Continuity Plan](BUSINESS_CONTINUITY_PLAN.md)
- [DPA Template](DPA_TEMPLATE.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)

## 10. External references

- UK GDPR Articles 33 and 34
- ICO guidance on personal data breaches
  (https://ico.org.uk/for-organisations/report-a-breach/)
- NCSC Incident Management guidance
- AlgoVoi `/.well-known/security.txt` for external reporting
