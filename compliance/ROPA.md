# Record of Processing Activities (RoPA) — Public Summary

**Owner**: Information Security Officer (ISO) — Christopher Hopley
**Approved by**: ISO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public summary; full RoPA available under NDA on request

## 1. Purpose

The Record of Processing Activities (RoPA) is AlgoVoi's structured
inventory of every processing activity it undertakes as a controller
or as a processor. It is required under Article 30 of the UK GDPR.

This is the **public summary** — it lists the processing activities,
their purposes, lawful bases, and high-level data categories without
revealing internal system topology. The full RoPA, including system-
level detail, is held under NDA.

## 2. Controller / Processor designation

| Context | Role |
|---|---|
| Personnel data | Controller |
| Merchant onboarding (CDD/KYB) data | Controller (for AlgoVoi's own MLR record-keeping); Processor where on the merchant's instruction |
| End-customer payment data passed via merchant integration | Processor (the merchant is the Controller) |
| Audit logs and security telemetry | Controller |

## 3. Processing activities (summary)

### 3.1 Merchant onboarding (KYB / CDD)

| Field | Value |
|---|---|
| Purpose | Verify identity, beneficial owners, and risk profile of merchants per UK MLR 2017 |
| Lawful basis | Legal obligation (UK GDPR Art. 6(1)(c)); legitimate interests (Art. 6(1)(f)) for fraud and abuse prevention |
| Categories of personal data | Identification documents; ownership-proof documents; beneficial-owner identifiers; address data; sanctions/PEP screening output |
| Categories of data subjects | Beneficial owners, directors, authorised users of the merchant |
| Recipients | Sanctions/PEP screening provider; identity-verification provider; AlgoVoi MLRO; AlgoVoi engineering (need-to-know); regulators on lawful request |
| International transfers | Where a vendor processes outside the UK, transfers are made under appropriate safeguards (UK IDTA / UK Addendum to EU SCCs) |
| Retention | 5 years from end of merchant relationship (UK MLR 2017) |
| Security measures | Encrypted at rest at application layer (separate key from general DB); TLS in transit; access on need-to-know; audit logged |

### 3.2 End-customer payment processing

| Field | Value |
|---|---|
| Purpose | Initiate, monitor, and reconcile cryptoasset payment messages between an end-customer's wallet and the merchant's wallet |
| Lawful basis | Performance of a contract between the end-customer and the merchant (Art. 6(1)(b)); legitimate interests for fraud detection and audit (Art. 6(1)(f)) |
| Controller | The merchant |
| Processor | AlgoVoi |
| Categories of personal data | Identifiers (where the merchant supplies them via metadata: email, name, account ID); transaction metadata; public on-chain identifiers |
| International transfers | None initiated by AlgoVoi; on-chain transactions are by definition global and public |
| Retention | 2 years active, then archived in line with the [Retention Procedure](RETENTION_PROCEDURE.md) |

### 3.3 Audit and security logging

| Field | Value |
|---|---|
| Purpose | Detect and investigate security incidents; demonstrate compliance with operational and regulatory obligations |
| Lawful basis | Legitimate interests (Art. 6(1)(f)); legal obligation where logs evidence MLR or breach-notification compliance (Art. 6(1)(c)) |
| Categories | API call metadata, authentication events, rate-limit events, sanctions-screening events, dashboard activity |
| Retention | 1 year general; 5 years AML-sensitive (see [Retention Procedure](RETENTION_PROCEDURE.md)) |

### 3.4 Personnel data

| Field | Value |
|---|---|
| Purpose | HR, payroll, performance, statutory employer obligations |
| Lawful basis | Performance of a contract; legal obligation; legitimate interests |
| Recipients | Payroll, HMRC, pension providers, accountancy support |
| Retention | Per HR / tax / pensions statutory minima |

### 3.5 Marketing and prospect data

| Field | Value |
|---|---|
| Purpose | Outbound contact with prospects and content distribution |
| Lawful basis | Legitimate interests (B2B) with opt-out; consent where required (PECR) |
| Categories | Business email, name, role, organisation |
| Retention | Until opt-out or 24 months of inactivity, whichever is sooner |

### 3.6 Vendor / sub-processor administration

| Field | Value |
|---|---|
| Purpose | Manage vendor relationships, conduct vendor due diligence |
| Lawful basis | Legitimate interests; legal obligation |
| Categories | Vendor contact data, contract metadata, due-diligence outputs |
| Retention | 6 years from end of vendor relationship |

### 3.7 URL / IP screening (financial-crime prevention)

| Field | Value |
|---|---|
| Purpose | Detect and refuse the use of AlgoVoi for money laundering, terrorist financing, sanctions evasion, fraud, and SSRF / DNS-rebinding attacks against the platform. Four enforcement points: signup IP, checkout `redirect_url`, webhook configuration URL, webhook delivery-time DNS-rebinding guard. |
| Lawful basis | Legitimate interests (UK GDPR Art. 6(1)(f)) for fraud and financial-crime prevention; integrity / confidentiality of processing (Art. 5(1)(f)). LIA balancing test recorded in `AML_POLICY.md` §8a. |
| Categories of personal data | IP address (Art. 4(1) personal data per Breyer line of cases); URL strings (which may incidentally contain identifiers in query parameters — these are stripped via `redact_url_for_audit` before any audit-log persistence) |
| Categories of data subjects | Prospective merchants (signup IP); end-customers (checkout `redirect_url` is configured by the merchant but reflects routing for the customer); merchants' configured webhook destinations (typically server-side, no personal data) |
| Recipients | Internal: MLRO + ISO. External (read-only references against public lists): UK OFSI, US OFAC, EU consolidated sanctions lists, Tor Project public exit list, SpamHaus DROP/EDROP, abuse.ch URLhaus / ThreatFox, OpenPhish, PhishTank. No personal data is sent to these external sources — they are read-only feed providers. |
| International transfers | None initiated by AlgoVoi; the screening data feeds are downloaded as public files to local cache (read-only, no upload of any AlgoVoi data) |
| Retention | Reason-coded audit events follow the general audit-log policy (1 year general, 5 years AML-sensitive). The IP value itself is logged at WARNING level per the platform logging policy (90-day retention). Full URL strings are NEVER persisted in the audit log — only scheme + host + path after `redact_url_for_audit` strips query string and fragment. |
| Security measures | TLS in transit (read-only feed downloads from public sources); encrypted at rest at the volume layer; access on need-to-know basis. Reason codes are machine-readable and contain no PII. |
| Article 22 compliance | Automated decisions with significant effect (signup refusal, checkout refusal, webhook configuration refusal) include a human-review appeal route via `security@algovoi.co.uk` printed in the block response. The framework is documented in `AML_POLICY.md` §8a. |

## 4. Data subject rights

AlgoVoi supports the rights of access, rectification, erasure (subject
to retention statutory minima), restriction, portability (where
applicable), and objection. Erasure handling, including the interaction
with statutory AML retention, is set out in the [Retention Procedure](RETENTION_PROCEDURE.md).

## 5. International transfers — summary

Where AlgoVoi or any of its sub-processors processes data outside the
UK / EEA, such transfers are governed by:

- The UK International Data Transfer Agreement (IDTA), or
- The UK Addendum to the EU Standard Contractual Clauses, or
- An adequacy regulation or other Article 46 mechanism.

The full sub-processor list with per-vendor transfer mechanism is
maintained at `https://algovoi.co.uk/compliance#subprocessors`.

## 6. Disclosure tiers

| Audience | What is shared |
|---|---|
| Public | This summary |
| Merchant Controller (NDA) | Full activity-level detail relevant to the Controller relationship |
| Acquirer / regulator (NDA) | Full RoPA including system mappings, vendor list, transfer instruments |

## 7. Related documents

- [DPA Template](DPA_TEMPLATE.md)
- [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
- [Data Breach Procedure](DATA_BREACH_PROCEDURE.md)
- [Retention Procedure](RETENTION_PROCEDURE.md)
- [Vendor Management Policy](VENDOR_MANAGEMENT_POLICY.md)
