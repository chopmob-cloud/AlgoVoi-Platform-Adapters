# Transaction Monitoring Procedure — Public Summary

**Owner**: MLRO — Christopher Hopley
**Approved by**: MLRO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public summary; full procedure (with rule values) available under NDA on request

## 1. Purpose

To define how AlgoVoi monitors payment activity for indicators of money
laundering, terrorist financing, sanctions evasion, fraud, and other
financial-crime typologies; how alerts are triaged; and how confirmed
suspicions are escalated.

This is the **public summary**. Rule thresholds, hit-rate tuning notes,
and individual rule logic are operationally sensitive (publishing them
would help bad actors stay under detection) and are therefore held
under NDA.

## 2. Scope

Applies to all payment activity initiated through AlgoVoi-issued
checkouts, payment links, programmatic API calls, conversational-bot
flows, and AI-agent (A2A) flows, across every supported chain.

## 3. Rule families

Monitoring is implemented as a layered set of rule families. Each
family targets a recognised typology. Below is the family taxonomy:

| Family | Typology |
|---|---|
| **Structuring** | Multiple smaller payments engineered to avoid a threshold |
| **Velocity** | Sudden change in pace, volume, or value relative to the merchant's historic profile |
| **Counterparty exposure** | Payer or payee wallet has known association with high-risk addresses (mixers, sanctioned addresses, ransomware) |
| **Round-tripping** | Funds enter and leave in tightly correlated pairs, indicative of layering |
| **Geographic concentration** | Disproportionate share of payments originating from or routed through high-risk jurisdictions |
| **Anomalous chain choice** | Atypical chain selection for the merchant's profile (e.g. a UK retail merchant suddenly receiving via a chain it has never used) |
| **Adverse counterparty signals** | Counterparty wallet flagged by external intelligence feed |

Specific values (what counts as "sudden", "high-risk", etc.) are NDA.

## 4. Detection pipeline

Monitoring runs in three layers:

1. **Pre-transaction** — sanctions screening on payer / payee wallets
   and merchant; refusal to settle if a positive sanctions match is
   confirmed.
2. **At-transaction** — real-time rule evaluation on the payment record
   as it transitions through `pending → confirmed`.
3. **Post-transaction** — periodic batch evaluation across the
   merchant's history to catch slower-moving patterns (e.g. structuring
   over weeks).

## 5. Alert handling

Each generated alert flows through:

```
[1] Created → [2] Triaged → [3] Investigated → [4] Disposed
```

| Stage | Owner | Notes |
|---|---|---|
| Created | Pipeline | Alert is logged with rule, evidence, and tenant context |
| Triaged | Operations | First-level triage classifies as `false positive`, `requires investigation`, or `escalate immediately` |
| Investigated | MLRO or delegate | Reviews context, runs counterparty checks, may request information from the merchant |
| Disposed | MLRO | Outcome recorded as `false positive`, `accepted risk`, `further monitoring`, `SAR filed`, or `relationship terminated` |

All disposition records are retained with their evidence trail and the
identity of the decision-maker.

## 6. Suspicious Activity Reports (SARs)

Where the MLRO forms a reasonable belief that money laundering or
terrorist financing has occurred, is occurring, or is being attempted,
a SAR is filed via the NCA SAR Online portal. The platform observes the
prohibition on tipping off (POCA 2002 s.333A; TA 2000 s.21D).

The detailed SAR procedure is **not published** in line with UKFIU
guidance.

## 7. Tuning and effectiveness

The MLRO reviews aggregate alert metrics at least **quarterly**:

- Total alerts generated, by rule family
- True-positive vs false-positive ratio
- Average triage time
- Cases escalated to SAR
- Cases closed without action and the rationale

Where a rule generates persistent false positives without ever
generating a true positive, it is re-tuned or retired. Where a
typology emerges that no current rule catches, a new rule is drafted,
peer-reviewed, and deployed.

## 8. Independence and separation of duties

- The engineer who writes a rule is **not** the same person who
  disposes of alerts produced by it.
- The MLRO does not approve their own SAR — sign-off, where escalation
  is needed, goes via senior management or external counsel.

## 9. Incident-handling overlap

Where a monitoring alert also indicates a security incident (e.g.
suggested account takeover), the [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md)
runs in parallel.

## 10. Disclosure tiers

| Audience | What is shared |
|---|---|
| Public | This summary |
| Acquirer / regulator (NDA) | Full procedure including rule values, sample case files, tuning history |

## 11. Related documents

- [AML Policy](AML_POLICY.md)
- [Sanctions Screening Procedure — Public Summary](SANCTIONS_PROCEDURE.md)
- [PEP Screening Procedure — Public Summary](PEP_SCREENING_PROCEDURE.md)
- [Customer Risk Scoring Matrix — Public Summary](CUSTOMER_RISK_SCORING_MATRIX.md)
- [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)
