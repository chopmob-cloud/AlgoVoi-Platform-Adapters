# Politically Exposed Person (PEP) Screening Procedure — Public Summary

**Owner**: MLRO — Christopher Hopley
**Approved by**: MLRO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public summary; full procedure (with vendor identity and EDD detail) available under NDA on request

## 1. Purpose

To set out how AlgoVoi identifies, screens, and manages relationships
where a beneficial owner, director, or controlling officer of a
merchant is a Politically Exposed Person (PEP), a family member, or a
known close associate, in line with the FCA's PEP guidance (FG17/6) and
the UK Money Laundering Regulations 2017.

This is the **public summary**. Provider identity, scoring thresholds,
and the EDD checklist are NDA.

## 2. Definitions

| Term | Meaning |
|---|---|
| **PEP** | A natural person entrusted with prominent public functions, other than as a middle-ranking or junior official, by a state, the EU, an international body, or as defined in MLR 2017 reg 35 |
| **Family member** | Spouse, civil partner, parent, child, child's spouse / civil partner |
| **Close associate** | A person who has joint beneficial ownership of a legal entity or arrangement, or any other close business relations, with a PEP; or sole beneficial ownership of an entity established for the benefit of a PEP |
| **Domestic PEP** | A PEP entrusted with public functions by the United Kingdom |
| **Foreign PEP** | A PEP entrusted with public functions by a country other than the United Kingdom |

## 3. When screening runs

| Event | Screening |
|---|---|
| Merchant onboarding | Full PEP screening of beneficial owners ≥ 25%, directors |
| Material change in merchant CDD | Re-screen affected parties |
| Periodic re-screen | Automated rescreen on provider list updates |

## 4. Risk-based handling

The FCA's FG17/6 sets out a risk-based, proportionate approach. AlgoVoi
applies that approach as follows:

| Category | Treatment |
|---|---|
| **Domestic PEP, low corruption-risk role, no adverse media** | Apply EDD; senior-management approval; standard ongoing monitoring; do not refuse a relationship solely because of PEP status |
| **Domestic PEP, higher-risk role or any adverse media** | Apply EDD; senior-management approval; enhanced monitoring; quarterly review |
| **Foreign PEP** | Mandatory EDD; mandatory senior-management approval; enhanced monitoring; source-of-wealth confirmed; quarterly review |
| **Family member or close associate** | Treat in line with the underlying PEP's category |
| **Former PEP (more than 12 months out of office)** | Apply a tapered risk reduction over time, taking into account residual influence and corruption risk |

A PEP relationship is not, by itself, a reason to decline. A PEP
relationship combined with an inability to verify source of wealth, or
with adverse media, is.

## 5. EDD checklist (high-level)

EDD obtains, at minimum:

- Source of wealth (verifiable, not just stated)
- Detailed nature of business relationship and counterparties
- Senior-management approval before mainnet activation
- Enhanced ongoing monitoring with documented review cadence

The full checklist with documentary requirements is NDA.

## 6. Records

PEP screening records are retained for **5 years** in line with the
[Retention Procedure](RETENTION_PROCEDURE.md). Records include:

- The list version screened against
- The match score and evidence
- The PEP category determined
- Senior-management approval (where relevant)
- Quarterly review outcomes (where relevant)

## 7. Tipping off and confidentiality

The prohibition on tipping off (POCA 2002 s.333A; TA 2000 s.21D)
applies if PEP screening surfaces information that gives rise to a
SAR. Information about a person's PEP status is otherwise treated
confidentially as personal data.

## 8. Disclosure tiers

| Audience | What is shared |
|---|---|
| Public | This summary |
| Acquirer / regulator (NDA) | Full procedure including provider identity, thresholds, sample-tested cases |

## 9. Related documents

- [AML Policy](AML_POLICY.md)
- [CDD/EDD Procedure — Public Summary](CDD_EDD_PROCEDURE.md)
- [Sanctions Screening Procedure — Public Summary](SANCTIONS_PROCEDURE.md)
- [Customer Risk Scoring Matrix — Public Summary](CUSTOMER_RISK_SCORING_MATRIX.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)

## 10. External references

- FCA FG17/6 — The treatment of politically exposed persons for AML purposes
- UK MLR 2017 reg 35 (definition of PEP)
- POCA 2002 s.333A; TA 2000 s.21D (tipping-off)
