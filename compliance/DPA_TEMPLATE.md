# Data Processing Agreement (DPA) — Template

**Owner**: Information Security Officer (ISO) — Christopher Hopley
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public

This is the standard Data Processing Agreement that AlgoVoi enters into with
merchants ("Controllers") who use the AlgoVoi platform to process personal
data. It is published as a template for transparency. The signed,
counter-party-specific version is exchanged on request.

This template is drafted to satisfy Article 28 of the UK GDPR (and EU GDPR
where applicable), the Data Protection Act 2018, and the European Commission's
Standard Contractual Clauses (SCCs) where international transfers are in
scope.

---

## 1. Parties

- **Controller**: the merchant (tenant) onboarded to AlgoVoi
- **Processor**: AlgoVoi (legal entity to be confirmed in the executed agreement)

## 2. Subject matter and duration

| Item | Value |
|---|---|
| Subject matter | Processing of personal data necessary for AlgoVoi to provide the payment-message and analytics services to the Controller |
| Duration | For the term of the underlying service agreement |
| Nature and purpose | Initiating, monitoring, and reconciling cryptoasset payment messages between the Controller's customers and the Controller's self-custodial wallet |
| Categories of data subjects | The Controller's end-customers; the Controller's authorised users |
| Categories of personal data | Identifiers (name, email, account ID); transaction metadata (amount, timestamp, public on-chain identifiers); KYC/KYB documents where the Controller is itself onboarded to AlgoVoi (encrypted at rest) |
| Special categories | None ordinarily processed; if a Controller passes special category data via webhook payload or order metadata, it does so at its own determination and outside AlgoVoi's intended use |

## 3. Processor obligations

The Processor shall:

1. Process personal data only on the documented instructions of the
   Controller, including with regard to international transfers, unless
   required to do so by UK or EU law (in which case the Processor shall
   inform the Controller of that legal requirement before processing,
   unless that law prohibits such information).
2. Ensure that persons authorised to process the personal data have
   committed themselves to confidentiality or are under an appropriate
   statutory obligation of confidentiality.
3. Take all measures required pursuant to Article 32 of the UK GDPR
   (security of processing); see the [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
   for the technical and organisational measures (TOMs) currently in force.
4. Respect the conditions for engaging another processor (sub-processor)
   set out in clause 5 below.
5. Taking into account the nature of the processing, assist the Controller
   by appropriate technical and organisational measures, insofar as
   possible, in fulfilling the Controller's obligation to respond to
   requests from data subjects exercising their rights under the UK GDPR.
6. Assist the Controller in ensuring compliance with Articles 32–36 of the
   UK GDPR (security, breach notification, data protection impact
   assessment, prior consultation), taking into account the nature of
   processing and the information available to the Processor.
7. At the choice of the Controller, delete or return all personal data
   after the end of the provision of services relating to processing, and
   delete existing copies unless UK or EU law requires storage of the
   personal data.
8. Make available to the Controller all information necessary to
   demonstrate compliance with the obligations laid down in Article 28 of
   the UK GDPR, and allow for and contribute to audits, including
   inspections, conducted by the Controller or another auditor mandated
   by the Controller (subject to reasonable confidentiality, frequency,
   and cost-bearing terms).

## 4. Personal data breach

The Processor shall notify the Controller without undue delay and in any
event within **48 hours** of becoming aware of a personal data breach
affecting the Controller's data. The notification shall, to the extent
known at the time, describe:

- The nature of the breach
- Categories and approximate number of data subjects and records affected
- Likely consequences
- Measures taken or proposed to address the breach and mitigate adverse
  effects

This timeline is designed to give the Controller adequate margin to meet
its own 72-hour notification obligation to the Information Commissioner's
Office (ICO) under Article 33 of the UK GDPR.

The full Processor breach process is described in the
[Data Breach Procedure](DATA_BREACH_PROCEDURE.md).

## 5. Sub-processors

The Processor maintains a public list of sub-processors at
`https://algovoi.co.uk/compliance#subprocessors`. The Processor shall:

- Not engage another processor without prior specific or general written
  authorisation of the Controller
- In the case of general written authorisation, inform the Controller of
  any intended changes concerning the addition or replacement of other
  processors, giving the Controller the opportunity to object to such
  changes
- Impose on each sub-processor, by contract, the same data protection
  obligations as set out in this DPA

## 6. International transfers

Where the Processor transfers personal data outside the UK / EEA in the
course of providing the services, such transfers shall be subject to
appropriate safeguards, which may include the UK International Data
Transfer Agreement, the UK Addendum to the EU SCCs, or another mechanism
recognised under Article 46 of the UK GDPR.

## 7. Liability and indemnity

Liability under this DPA is governed by the underlying service agreement
between the parties. Nothing in this DPA shall limit liability that
cannot be limited under applicable data protection law.

## 8. Governing law

This DPA is governed by the laws of England and Wales. The courts of
England and Wales have exclusive jurisdiction over any dispute arising
from or in connection with this DPA.

---

## Annex A — Technical and Organisational Measures (TOMs)

See [Information Security Policy](INFORMATION_SECURITY_POLICY.md), section
6 (Encryption) and section 7 (Monitoring and logging), and the
[Access Control Policy](ACCESS_CONTROL_POLICY.md).

## Annex B — Sub-processors

See `https://algovoi.co.uk/compliance#subprocessors`.

## Annex C — International Data Transfer Mechanism

To be completed in the executed counterparty-specific version where
relevant.

---

**Note**: This template is provided for transparency. It does not constitute
legal advice. Controllers should obtain their own legal advice before
executing.
