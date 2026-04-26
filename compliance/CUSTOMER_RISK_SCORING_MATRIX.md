# Customer Risk Scoring Matrix — Public Summary

**Owner**: MLRO — Christopher Hopley
**Approved by**: MLRO
**Effective**: 2026-04-26
**Next review**: 2027-04-26
**Disclosure tier**: Public summary; full matrix (with weights, thresholds, and override rules) available under NDA on request

## 1. Purpose

To set out the structured way AlgoVoi assigns each merchant a risk
score at onboarding and on review, and how that score drives the level
of due diligence, monitoring, and senior-management oversight applied
to the relationship.

This is the **public summary**. Specific weights, thresholds, and the
override matrix are operationally sensitive and held under NDA.

## 2. Risk dimensions

Each merchant is scored across the following dimensions:

| Dimension | Examples of factors |
|---|---|
| **Entity risk** | Type of legal entity; complexity of ownership; transparency of beneficial ownership; jurisdiction of incorporation |
| **People risk** | PEP status of beneficial owners or directors; adverse media; sanctions screening outcome |
| **Sector risk** | Sector flagged as higher-risk in our BWRA (e.g. unregulated remittance-adjacent, high-volume gambling, high-velocity adult content, etc.) |
| **Geography risk** | UK-only operating perimeter is the baseline; out-of-perimeter relationships are escalated; FATF / UK Sch 3ZA high-risk jurisdictions are weighted up |
| **Product risk** | Mix of chains and protocols selected; high-velocity stablecoin flows; cross-border end-customer concentration |
| **Volume risk** | Expected payment volume relative to peer merchants in the same sector |

## 3. Scoring outputs

The aggregate score maps to a risk band:

| Band | Approximate meaning |
|---|---|
| **Low** | Standard CDD; standard monitoring; no special escalation |
| **Medium** | Standard CDD; enhanced monitoring on entry; periodic re-screen |
| **High** | EDD applied; senior-management approval before mainnet activation; enhanced ongoing monitoring; quarterly review |
| **Unacceptable** | Decline relationship; consider SAR if grounds exist |

The numerical breakpoints between bands are NDA.

## 4. Decision overrides

Some signals override the aggregate score regardless of where it
otherwise lands:

- A confirmed sanctions hit on the merchant or any beneficial owner →
  decline, irrespective of any other factor.
- An OFSI / OFAC / EU / UN listing match → decline.
- A jurisdiction subject to comprehensive UK sanctions → decline.
- Refusal or inability to provide CDD documents → decline.
- Beneficial owner is a foreign PEP → mandatory EDD, mandatory senior-
  management approval, irrespective of aggregate score.

The full override list, including the partial-match handling logic, is
NDA.

## 5. Re-scoring

Each merchant is re-scored:

- On any material change in CDD information (new beneficial owner,
  change of director, change of business model)
- On any sanctions / PEP list update that affects an associated
  natural or legal person
- On any monitoring alert that the MLRO classifies as material
- At a defined cadence based on the merchant's current band (NDA)

## 6. Validation

The MLRO validates the scoring framework annually:

- Reviews a sample of recent scoring decisions
- Compares to actual monitoring outcomes
- Recalibrates weights / thresholds where the data supports it
- Records the validation outcome and any change

## 7. Disclosure tiers

| Audience | What is shared |
|---|---|
| Public | This summary |
| Acquirer / regulator (NDA) | Full matrix with weights, thresholds, sample-tested decisions |

## 8. Related documents

- [AML Policy](AML_POLICY.md)
- [CDD/EDD Procedure — Public Summary](CDD_EDD_PROCEDURE.md)
- [Sanctions Screening Procedure — Public Summary](SANCTIONS_PROCEDURE.md)
- [PEP Screening Procedure — Public Summary](PEP_SCREENING_PROCEDURE.md)
- [Business-Wide Risk Assessment — Public Summary](BWRA.md)
