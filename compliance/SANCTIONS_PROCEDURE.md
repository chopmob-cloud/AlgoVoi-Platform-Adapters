# Sanctions Screening Procedure — Public Summary

**Owner**: MLRO — Christopher Hopley
**Approved by**: MLRO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public summary; full procedure (with vendor identity and match-handling logic) available under NDA on request

## 1. Purpose

To set out how AlgoVoi screens merchants, beneficial owners, directors,
and counterparty wallets against the consolidated sanctions lists, and
how it handles matches.

This is the **public summary**. The screening provider, the partial-
match thresholds, and the disposition workflow are NDA.

## 2. Lists screened

AlgoVoi screens against, at minimum:

- **UK** — HM Treasury Office of Financial Sanctions Implementation
  (OFSI) consolidated list
- **EU** — EU consolidated financial sanctions list
- **US** — OFAC SDN and consolidated sanctions lists
- **UN** — UN Security Council consolidated sanctions list

Where list updates are published, AlgoVoi's screening provider ingests
the update and rescreens the existing tenant base.

## 3. When screening runs

| Event | Screening |
|---|---|
| Merchant onboarding | Full screening of legal entity, beneficial owners ≥ 25%, directors |
| Material change in merchant CDD | Re-screen affected parties |
| New sanctions list version | Automated rescreen of full tenant base |
| Counterparty wallet appearing in payment activity | Wallet screening against on-chain sanctions / risk lists |
| Pre-payout (if applicable) | Wallet-level screening as part of risk control |

## 4. Match handling

A potential match is **never** auto-actioned without review. Each match
flows through:

```
[1] Match detected → [2] Triaged → [3] Confirmed / Dismissed → [4] Disposition
```

| Stage | What happens |
|---|---|
| Match detected | Provider returns potential match with score and evidence |
| Triaged | Operations review against name, date of birth, jurisdiction, identifiers |
| Confirmed | Confirmed positive match → mainnet activity blocked; relationship review; SAR considered; OFSI report where mandated |
| Dismissed | False positive recorded with rationale and reviewer identity |

Rapid-action confirmed-match procedure (e.g. immediate wallet freeze
where AlgoVoi has technical means, immediate relationship suspension)
is held under NDA.

## 5. OFSI reporting

Where AlgoVoi confirms that it has dealt with, or holds funds or
economic resources of, a designated person, AlgoVoi reports to OFSI as
required by The Sanctions and Anti-Money Laundering Act 2018 and
associated regulations.

Note: in the no-custody architecture, AlgoVoi does not hold funds or
economic resources on its own books. The reporting trigger is most
likely to arise from an attempted onboarding or from a counterparty
wallet that surfaces during monitoring.

## 6. Records

Sanctions screening records are retained for **5 years** in line with
the [Retention Procedure](RETENTION_PROCEDURE.md). Records include:

- The list version screened against
- The query terms
- The match score and evidence
- The reviewer's identity and timestamp
- The disposition (confirmed / false positive) and rationale

## 7. Independence

The reviewer who dismisses a potential match is **not** the same person
who onboarded the merchant. Where only one person is rota'd, the
escalation path is to the MLRO.

## 8. Tipping off

The prohibition on tipping off applies (POCA 2002 s.333A; TA 2000
s.21D) to any communication that might prejudice an investigation
arising from a confirmed match.

## 9. Disclosure tiers

| Audience | What is shared |
|---|---|
| Public | This summary |
| Acquirer / regulator (NDA) | Full procedure including provider identity, thresholds, sample-tested matches |

## 10. Related documents

- [AML Policy](AML_POLICY.md)
- [CDD/EDD Procedure — Public Summary](CDD_EDD_PROCEDURE.md)
- [PEP Screening Procedure — Public Summary](PEP_SCREENING_PROCEDURE.md)
- [Customer Risk Scoring Matrix — Public Summary](CUSTOMER_RISK_SCORING_MATRIX.md)
- [Transaction Monitoring Procedure — Public Summary](TRANSACTION_MONITORING_PROCEDURE.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)
