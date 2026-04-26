# Complaints Procedure

**Owner**: Information Security Officer (ISO) — Christopher Hopley
**Approved by**: ISO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public

## 1. Purpose

To set out a clear, fair, and timely route for merchants ("tenants") and
end-customers to raise complaints about AlgoVoi's service, and for AlgoVoi
to respond consistently and learn from those complaints.

## 2. Scope

Applies to any expression of dissatisfaction, in any form, by:

- A merchant onboarded to the AlgoVoi platform
- An end-customer who has interacted with an AlgoVoi-hosted checkout, link,
  or notification
- A third party (e.g. a researcher, a regulator, a partner)

## 3. How to raise a complaint

| Channel | Address | When to use |
|---|---|---|
| Email — general | `support@algovoi.co.uk` | Default channel for service or billing concerns |
| Email — privacy | `privacy@algovoi.co.uk` | Data-protection complaints, subject-access requests, erasure requests |
| Email — security | `security@algovoi.co.uk` | Security concerns, vulnerability reports |
| Email — compliance | `compliance@algovoi.co.uk` | AML / regulatory concerns |
| `/.well-known/security.txt` | `https://algovoi.co.uk/.well-known/security.txt` | Coordinated disclosure of security issues |

A complaint does not need to be labelled as such. Anything that
reasonably reads as dissatisfaction is treated as a complaint.

## 4. What to include

To help us resolve a complaint quickly, please include where possible:

- The name of the merchant or service involved
- A description of what happened
- The date(s) and (if known) the relevant payment, checkout, or
  reference IDs
- The outcome you are seeking
- Any prior correspondence on the issue

We will not refuse to investigate a complaint because it is missing some
of the above.

## 5. Acknowledgement and investigation

| Stage | Target |
|---|---|
| Acknowledgement | Within **3 working days** of receipt |
| Substantive response | Within **15 working days** of acknowledgement, where reasonably possible |
| Final written response | Within **35 working days** in line with FCA-adjacent expectations for complaints involving payments |

If we cannot meet the substantive-response target (e.g. because we need
information from a third party), we will tell the complainant and give a
revised expected date.

## 6. How a complaint is handled

1. The complaint is logged with a unique reference and assigned to an owner.
2. The owner reviews the underlying records (audit logs, support
   correspondence, transaction records) and, where relevant, consults with
   the engineering team, the MLRO, the ISO, or external advisors.
3. The owner forms a view on the merits and proposed resolution.
4. The complainant receives a written response setting out:
   - What was investigated
   - What we found
   - Our decision and any remediation offered
   - Routes of escalation if the complainant is not satisfied

## 7. Escalation

If a complainant is not satisfied with our final response, the available
escalation routes are:

| Topic | Escalation body |
|---|---|
| Data protection / privacy | Information Commissioner's Office (ICO) — https://ico.org.uk |
| Anti-money-laundering (regulator) | Financial Conduct Authority (FCA) — https://www.fca.org.uk |
| Sanctions concerns | Office of Financial Sanctions Implementation (OFSI) — https://www.gov.uk/government/organisations/office-of-financial-sanctions-implementation |
| Cybercrime | Action Fraud — https://www.actionfraud.police.uk |

Note: AlgoVoi is not currently within scope of the Financial Ombudsman
Service. Where a complainant disputes a payment outcome, the merchant
("Controller") is the primary counterparty. Where a complainant disputes
how AlgoVoi handled their personal data, the ICO is the primary
escalation body.

## 8. Records and root-cause review

All complaints are logged with the following metadata:

- Date received
- Channel
- Complainant category (merchant / end-customer / other)
- Topic (privacy / payment / security / billing / other)
- Owner
- Outcome
- Resolution time
- Whether root-cause action was triggered

The ISO reviews complaint trends at least quarterly. Material themes
trigger a root-cause review and, where appropriate, a change to a policy,
process, or system.

Complaint records are retained for **6 years** from closure, in line with
the [Retention Procedure](RETENTION_PROCEDURE.md).

## 9. Confidentiality and non-retaliation

Complaints are handled confidentially. AlgoVoi will not retaliate against
a complainant for raising a concern in good faith. This applies equally
to AlgoVoi personnel, contractors, merchants, and end-customers.

## 10. Related documents

- [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
- [Data Breach Procedure](DATA_BREACH_PROCEDURE.md)
- [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)
