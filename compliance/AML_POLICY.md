# Anti-Money Laundering (AML) and Counter-Terrorist Financing (CTF) Policy

**Owner**: Money Laundering Reporting Officer (MLRO) — Christopher Hopley
**Approved by**: MLRO
**Effective**: 2026-04-26
**Next review**: 2027-04-26 (or upon material regulatory change)
**Disclosure tier**: Public

## 1. Purpose

To set out AlgoVoi's framework for preventing the platform from being used to
launder the proceeds of crime or to finance terrorism, and to demonstrate the
controls AlgoVoi applies to meet its obligations under the UK Money Laundering
Regulations 2017 (as amended) and related guidance (JMLSG, FCA, NCA, OFSI).

## 2. Scope

This policy applies to:

- All AlgoVoi personnel, contractors, and directors
- All merchants (tenants) onboarded to the AlgoVoi platform
- All payment activity processed through AlgoVoi-issued checkout sessions,
  payment links, or programmatic API calls
- All vendors and subprocessors that touch merchant or end-customer data

## 3. Regulatory position

AlgoVoi has self-assessed against FCA Policy Statement PS19/22 and concludes
that its **core business proposition** is the provision of payment-message
infrastructure between a customer's self-custodial wallet and a merchant's
self-custodial wallet on public blockchains. Funds are never held, controlled,
or transmitted by AlgoVoi at any point. On this basis the activity is
considered **out of scope of MLR Schedule 6A registration** as a cryptoasset
exchange provider or custodian wallet provider.

A formal external legal opinion is in preparation. Until that opinion is on
file, AlgoVoi:

- Operates under voluntary AML controls equivalent to those expected of a
  registered firm
- Maintains all of the documentation, monitoring, and reporting referenced in
  this policy as if it were a regulated entity
- Treats this position as subject to revision should the regulator publish
  superseding guidance, or should AlgoVoi materially change its architecture

## 4. Roles and responsibilities

| Role | Responsibilities |
|---|---|
| MLRO | Owns this policy; receives all internal escalations; files Suspicious Activity Reports (SARs) with the National Crime Agency where required; approves the annual Business-Wide Risk Assessment (BWRA); maintains the training log |
| Information Security Officer | Operates the technical controls that support AML monitoring (logging, audit trails, sanctions-screening pipeline) |
| All personnel | Complete annual AML/CTF training; report internal suspicions to the MLRO without delay; comply with the tipping-off prohibition under POCA 2002 s.333A |
| Vendors | Meet contractual AML obligations where applicable; flag any suspicion to AlgoVoi within 24 hours |

## 5. Three-line-of-defence model

1. **First line** — engineering and operations: implement and operate
   preventive controls (sanctions screening, customer due diligence,
   transaction monitoring, kill switches).
2. **Second line** — MLRO and ISO: own this policy, the risk register, and
   the training programme; review first-line output and exceptions.
3. **Third line** — independent review: external advisor reviews the AML
   programme annually (or at material change) and reports to the MLRO and
   the board.

## 6. Customer due diligence (CDD)

AlgoVoi onboards merchants (tenants), not retail end-customers. Tenant CDD is
performed before any tenant is moved from testnet to mainnet (the
"KYC-unlocks-mainnet" gate). Standard CDD captures the items required to
identify the merchant, verify identification, identify beneficial owners (≥
25%), and understand the nature and intended purpose of the business
relationship. Enhanced Due Diligence (EDD) is applied to higher-risk relationships.

The detailed CDD/EDD Procedure is published in summary form in this
repository and in full under NDA on request.

## 7. Risk-based approach

AlgoVoi maintains a Business-Wide Risk Assessment (BWRA) covering customer,
geography, product, channel, and transaction-type risk. The BWRA is reviewed
at least annually, and ad-hoc when the platform adds a new chain, new
geography, or new product line. The BWRA drives the customer risk-scoring
matrix used at onboarding.

Public summary in this repository; full BWRA available under NDA.

## 8. Sanctions and PEP screening

- **Wallet-level sanctions screening (live)**: every payment is screened
  in real time against the consolidated UK (OFSI), EU, US (OFAC), and UN
  sanctions lists. The lists are ingested directly from the public XML
  feeds and refreshed daily. A positive match blocks settlement and is
  escalated to the MLRO; SAR consideration follows.
- **Name-level sanctions screening of merchants and beneficial owners
  (in preparation)**: the policy framework is defined; the commercial
  data-feed integration (e.g. ComplyAdvantage / Acuris) is being
  evaluated. For UK Limited Company onboarding today, the MLRO
  performs this check manually against public sources at the KYB
  review step. Auto-approved individual / sole-trader accounts do not
  yet receive automated name-level screening — recorded as a residual
  risk in the BWRA, with feed go-live as the trigger to revisit.
- **Politically Exposed Persons (PEPs) (framework live, automated
  feed in preparation)**: PEP definition per UK MLR 2017 reg 35 and
  FCA FG17/6 risk-based handling are operational at the policy level;
  the automated commercial data feed lands together with name-level
  sanctions screening above. See
  [PEP_SCREENING_PROCEDURE.md](PEP_SCREENING_PROCEDURE.md) for the
  current state.
- Screening output is logged with tenant ID, list version, hit summary,
  and reviewer outcome.

The wallet-level screening pipeline is open in this repository
(`shared/models/compliance.py`, `control_plane/app/services/sanctions_*`).
The commercial provider's identity (once selected) and full
match-handling logic will be held under NDA.

## 9. Transaction monitoring

All payment activity is monitored against a defined ruleset that targets
typologies including (but not limited to):

- Structuring or smurfing patterns across a tenant's customer base
- Velocity anomalies relative to the tenant's historic profile
- Counterparty wallet exposure to known high-risk addresses or mixers
- Rapid in-and-out flows (round-tripping)
- Geographic risk concentration

Specific thresholds and rule values are operationally sensitive and held
under NDA. Methodology — but not values — is published in the Transaction
Monitoring Procedure summary.

## 10. Suspicious Activity Reports

Internal suspicions are reported to the MLRO without delay. Where the MLRO
forms a reasonable belief that money laundering or terrorist financing has
taken place, is taking place, or is being attempted, a SAR is filed with the
NCA via the SAR Online portal. AlgoVoi observes the prohibition on tipping
off (POCA 2002 s.333A; TA 2000 s.21D).

Operational SAR procedure is **not published in detail** in line with UKFIU
guidance. A one-line public statement of capability is given on the public
compliance page.

## 11. Training

All personnel complete AML/CTF awareness training:

- On joining, before being granted any production-system or merchant-data
  access
- At least annually thereafter
- Ad-hoc when there is a material regulatory change or a typology alert

The MLRO maintains a training log. The log itself is held internally and
referenced in the public compliance page as a one-line statement.

## 12. Record-keeping

All records required to evidence CDD, monitoring decisions, sanctions
screening, training, and SAR activity are retained for **a minimum of five
years** from the end of the business relationship or the date of the
relevant transaction, whichever is later. Records are stored in encrypted,
append-only form (see [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
section 7).

The full retention schedule is published in the
[Retention Procedure](RETENTION_PROCEDURE.md).

## 13. Travel Rule

The UK HMT Cryptoasset Travel Rule applies to cryptoasset transfers above
£1,000 made by FCA-registered cryptoasset businesses. AlgoVoi is not a
registered cryptoasset business and does not initiate or receive transfers
on its own account; settlement is wallet-to-wallet on public blockchains.
Where future architecture or regulatory scope changes bring AlgoVoi within
the Travel Rule, AlgoVoi will adopt one of the established Travel Rule
protocols (e.g. TRP, IVMS101) before activation.

## 14. Cooperation with authorities

AlgoVoi cooperates with lawful production orders and information requests
from UK and overseas competent authorities. Requests are routed to the
MLRO; responses are subject to legal review where warranted.

## 15. Review and revision

This policy is reviewed annually by the MLRO and on any of the following
triggers:

- A change in the underlying regulations or supervisory guidance
- A material change in AlgoVoi's product, geography, or architecture
- An internal incident or external audit finding that suggests the policy
  is inadequate

## 16. Related documents

- [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
- [Customer Due Diligence / Enhanced Due Diligence — Public Summary](CDD_EDD_PROCEDURE.md)
- [Transaction Monitoring Procedure — Public Summary](TRANSACTION_MONITORING_PROCEDURE.md)
- [Sanctions Screening Procedure — Public Summary](SANCTIONS_PROCEDURE.md)
- [Customer Risk Scoring Matrix — Public Summary](CUSTOMER_RISK_SCORING_MATRIX.md)
- [Business-Wide Risk Assessment — Public Summary](BWRA.md)
- [Data Breach Procedure](DATA_BREACH_PROCEDURE.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)
- [Complaints Procedure](COMPLAINTS_PROCEDURE.md)
