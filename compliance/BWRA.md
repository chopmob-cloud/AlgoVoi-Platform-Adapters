# Business-Wide Risk Assessment (BWRA) — Public Summary

**Owner**: MLRO — Christopher Hopley
**Approved by**: MLRO
**Effective**: 2026-04-26
**Next review**: 2027-04-26 (or upon material change in product, geography, or regulation)
**Disclosure tier**: Public summary; full BWRA available under NDA on request

## 1. Purpose

The Business-Wide Risk Assessment (BWRA) is AlgoVoi's structured view of
the money-laundering and terrorist-financing risks the platform is exposed
to, the controls that mitigate those risks, and the residual risk left
after those controls are in place. It is required under regulation 18 of
the UK Money Laundering Regulations 2017.

This document is the **public summary**. The full BWRA — including
inherent and residual risk scores, scenario walk-throughs, and rule-level
control commentary — is held under NDA.

## 2. Scope of the assessment

The BWRA covers AlgoVoi as a whole: every chain supported, every product
line (hosted checkout, payment links, programmatic API, conversational
bots), every onboarded merchant geography, and every category of end-
customer the platform may touch.

## 3. Risk dimensions assessed

| Dimension | What we look at |
|---|---|
| **Customer** | Merchant business type, ownership structure, beneficial owners, sector risk profile, prior regulatory record |
| **Geography** | Merchant country of incorporation and operation; end-customer reach; high-risk-jurisdiction exposure (FATF lists, OFSI lists, supervisor lists) |
| **Product** | Each protocol (x402, MPP, AP2, A2A, Solana Actions) and each chain (currently 7), with separate consideration of stablecoin vs native-asset flows |
| **Channel** | Web checkout, payment link, programmatic API, conversational bot, AI agent (A2A) |
| **Transaction** | Typical size and velocity; structuring susceptibility; counterparty wallet exposure; round-trip risk |

## 4. Methodology

For each dimension, the BWRA:

1. Identifies the inherent risk (what could go wrong absent controls).
2. Lists the controls in place (preventive, detective, corrective).
3. Scores the residual risk on a low / medium / high / very-high scale.
4. Records the rationale, the evidence relied on, and the date of last
   review.

Risk scores and the underlying rationale narratives are operationally
sensitive (they reveal where AlgoVoi is "comfortable" vs "watching")
and are therefore held under NDA.

## 5. Headline conclusions (publishable)

1. **No-custody architecture materially reduces inherent risk.** Funds
   move customer-wallet → merchant-wallet directly on a public
   blockchain. AlgoVoi never holds, controls, or transmits funds. Loss-
   of-funds typologies tied to custodial intermediaries (rug-pull,
   exchange hack, mixer integration) are structurally not applicable.
2. **Merchant onboarding is the primary risk gate.** End-customers do
   not onboard to AlgoVoi; the merchant is the regulated relationship.
   CDD/EDD energy is therefore concentrated on the merchant.
3. **The KYC-unlocks-mainnet gate is the principal preventive control.**
   No mainnet payment activity occurs for any merchant until CDD has been
   completed and signed off. Merchants on testnet during evaluation can
   exercise the platform with no real-value flow.
4. **Geography is risk-tiered.** Geography is one of the dimensions
   scored in the customer risk matrix. UK and other low-risk
   jurisdictions are the baseline; FATF and UK Sch 3ZA high-risk
   jurisdictions are weighted up; comprehensive-sanctions jurisdictions
   are declined. Higher-risk merchant onboardings escalate to EDD with
   senior-management approval before any mainnet activity is allowed.
5. **Sanctions screening: wallet-level live, name-level in preparation.**
   Wallet-address screening against the consolidated UK OFSI, EU, US
   OFAC, and UN sanctions lists runs in real time on every payment
   (lists ingested from public XML feeds, refreshed daily). Name-based
   sanctions and PEP screening framework is defined (FCA FG17/6) and
   handled manually by the MLRO at UK Limited Company KYB review;
   the commercial data-feed integration is in preparation. Recorded
   here as a residual risk under continuing review.
6. **Transaction monitoring runs continuously.** Rule families cover
   structuring, velocity anomalies, counterparty exposure, round-tripping,
   and geographic concentration. Specific rule values are NDA.
7. **The principal residual risks** are: novel typologies emerging from
   AI-agent-initiated payments (A2A); high-risk-jurisdiction end-
   customers paying low-risk merchants; and merchant collusion (a
   merchant who is itself laundering proceeds via genuine-looking
   payments). These are addressed by monitoring + onboarding + the
   tipping-off-aware SAR escalation path.

## 6. Review cadence

The BWRA is reviewed:

- At least **annually**
- Whenever a new chain, geography, or product line is added
- Whenever a new typology alert is published by FCA, NCA, FATF, or a
  peer firm and is potentially relevant
- Whenever an internal incident or external audit suggests the
  assessment is out of date

## 7. Disclosure tiers

| Audience | What is shared |
|---|---|
| Public | This summary |
| Merchant Controllers (NDA) | Methodology section, risk dimensions, control taxonomy |
| Acquirer / regulator (NDA + signed acceptance of confidentiality) | Full BWRA including residual scores, rationale, scenarios, rule-level control commentary |

## 8. Related documents

- [AML Policy](AML_POLICY.md)
- [Customer Risk Scoring Matrix — Public Summary](CUSTOMER_RISK_SCORING_MATRIX.md)
- [CDD/EDD Procedure — Public Summary](CDD_EDD_PROCEDURE.md)
- [Transaction Monitoring Procedure — Public Summary](TRANSACTION_MONITORING_PROCEDURE.md)
- [Sanctions Screening Procedure — Public Summary](SANCTIONS_PROCEDURE.md)
