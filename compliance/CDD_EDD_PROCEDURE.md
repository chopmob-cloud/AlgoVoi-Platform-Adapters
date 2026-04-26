# Customer Due Diligence (CDD) / Enhanced Due Diligence (EDD) Procedure — Public Summary

**Owner**: MLRO — Christopher Hopley
**Approved by**: MLRO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public summary; full procedure (with thresholds and decision matrix) available under NDA on request

## 1. Purpose

To set out how AlgoVoi identifies and verifies merchants ("tenants") at
onboarding, what AlgoVoi expects to know about them, and when Enhanced
Due Diligence (EDD) is applied. The procedure operationalises Part 3 of
the UK Money Laundering Regulations 2017.

This is the **public summary**. Specific document checklists, decision
thresholds, and override matrices are NDA.

## 2. Scope

Applies to every merchant onboarded to the AlgoVoi platform. AlgoVoi
does not onboard end-customers as such; the merchant is the regulated
relationship. End-customer payment activity is monitored under the
[Transaction Monitoring Procedure](TRANSACTION_MONITORING_PROCEDURE.md).

## 3. The KYC-unlocks-mainnet gate

The defining preventive control: a merchant cannot transact on mainnet
until CDD has been completed and the merchant's account has been moved
from `testnet` to `mainnet`. Merchants onboarded for evaluation operate
on testnet only and cannot move real value through the platform. This
control is enforced at the platform layer; it cannot be bypassed by an
operator action on the dashboard.

## 4. Standard CDD (every merchant)

For every merchant, AlgoVoi captures and verifies:

| Item | What we capture |
|---|---|
| Legal identity of the entity | Registered name, registration number, country of incorporation |
| Trading name(s) | Where different from legal name |
| Beneficial owners ≥ 25% | Identification, verification, and screening |
| Directors / controlling officers | Identification and screening |
| Registered and principal places of business | Address verification |
| Nature and intended purpose of the business relationship | Sector, products, target customer base |
| Source of funds (high level) | Where the merchant's business funding originates |
| Sanctions and PEP screening | Across consolidated UK / EU / US / UN lists |

Verification is performed against authoritative documents (e.g.
incorporation records, regulator registers, government-issued ID for
named individuals). Verification methods can be remote.

## 5. Enhanced Due Diligence (EDD)

EDD is applied where any of the following risk factors are present:

- Beneficial owner or controlling officer is a Politically Exposed
  Person (PEP), a family member, or a close associate
- Merchant is incorporated, operates, or has principal beneficial
  ownership in a higher-risk third country (per FATF / UK Sch 3ZA)
- Merchant operates in a sector flagged as higher-risk in our BWRA
- Adverse media is found during onboarding
- Onboarding presents complex or unusual ownership structures
- The intended product mix or expected transaction profile is
  inherently higher risk (e.g. high-value, cross-border)

Where EDD applies, AlgoVoi obtains additional information on:

- Source of wealth (not just source of funds)
- Detailed nature of the merchant's business and counterparties
- Senior-management approval of the relationship
- Enhanced ongoing monitoring of the relationship

## 6. Reliance on third parties

AlgoVoi may rely on a regulated third party to perform CDD elements
(e.g. an identity-verification provider). Reliance is documented; the
third party's duty to provide underlying records on request is captured
in contract. Ultimate responsibility for compliance with the MLRs
remains with AlgoVoi.

## 7. Ongoing CDD

CDD is not a one-off:

- Merchants are required to keep their CDD records up to date.
- AlgoVoi periodically re-screens existing merchants against sanctions
  and PEP lists.
- A change in beneficial ownership, director, or business model
  triggers a CDD refresh.
- Adverse-media or sanctions-list updates trigger a real-time review.

## 8. Outcome handling

| Outcome | Action |
|---|---|
| **Pass** (low / medium risk, no hits) | Move account to `mainnet`; record outcome |
| **Refer** (open question or partial information) | Hold account on `testnet`; request missing items; no mainnet activity until cleared |
| **EDD** (high risk, but acceptable) | Senior management sign-off; enhanced monitoring; move to `mainnet` |
| **Decline** (sanctions hit, unacceptable risk, or refusal to provide CDD) | Decline relationship; record rationale; consider SAR if grounds exist |

## 9. KYC at-rest encryption

All CDD documents collected (KYB images, identity documents,
ownership-proof attachments) are encrypted at rest at the application
layer using a versioned MultiFernet scheme with a key separate from the
general database key. Plaintext exists only in process memory during
review by an authorised reviewer.

## 10. Record-keeping

CDD records (including documents, screening hits, decision rationale,
and senior-management approvals where relevant) are retained for **5
years** from the end of the business relationship, in line with the
[Retention Procedure](RETENTION_PROCEDURE.md) and the MLR 2017.

## 11. Disclosure tiers

| Audience | What is shared |
|---|---|
| Public | This summary |
| Merchant Controller (NDA) | Full document checklist, decision matrix |
| Acquirer / regulator (NDA) | Full procedure including thresholds, sample-tested cases |

## 12. Related documents

- [AML Policy](AML_POLICY.md)
- [Customer Risk Scoring Matrix — Public Summary](CUSTOMER_RISK_SCORING_MATRIX.md)
- [Sanctions Screening Procedure — Public Summary](SANCTIONS_PROCEDURE.md)
- [PEP Screening Procedure — Public Summary](PEP_SCREENING_PROCEDURE.md)
- [Transaction Monitoring Procedure — Public Summary](TRANSACTION_MONITORING_PROCEDURE.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)
