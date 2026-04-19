# Vendor Management Policy

**Owner**: Information Security Officer
**Effective**: 2026-04-19
**Next review**: 2027-04-19 (or when a new subprocessor is onboarded)
**SOC 2 mapping**: CC9 (Risk Mitigation)

## 1. Purpose

Identify, evaluate, and monitor the third-party services that handle
AlgoVoi data or operate critical parts of the service. Ensure each one
meets security expectations that are consistent with AlgoVoi's own posture.

## 2. Scope

Every vendor that:

- Processes, stores, or transmits AlgoVoi data, **or**
- Hosts or operates infrastructure AlgoVoi depends on for production

is a "subprocessor" for this policy. Marketing tools that handle only
public data are out of scope.

## 3. Subprocessor register

Current subprocessors, as of 2026-04-19:

| Vendor | Purpose | Data class | Location | Security programme |
|---|---|---|---|---|
| **Cloudflare** | CDN, DDoS, WAF, TLS termination for `*.algovoi.co.uk` and `ilovechicken.co.uk` | All transit data (encrypted) | Global, primary EU/US | SOC 2 Type II, ISO 27001, PCI-DSS, GDPR |
| **Vultr (Vultr Holdings LLC)** | Compute (VPS hosting) for production, database, Cloud gateway, MCP server | All AlgoVoi data at rest | Primary: London | SOC 2 Type II, ISO 27001 (colo partners) |
| **GitHub (Microsoft)** | Source code hosting, CI | Code + build artefacts (no production secrets) | Global | SOC 2 Type II, ISO 27001 |
| **npm, Inc. (GitHub)** | Package distribution for `@algovoi/*` | Published package artefacts only | Global | SOC 2 Type II |
| **PyPI (Python Software Foundation)** | Package distribution for `algovoi-mcp` | Published package artefacts only | Global | Non-profit; best-effort |
| **Let's Encrypt (ISRG)** | TLS certificate issuance | Domain names only (no private keys) | Global | ISO 27001 (parent non-profit) |
| **OFAC / OFSI sanctions feeds** | Live sanctions screening | Sanctions list content only; no AlgoVoi data sent | Government data sources | Public data |
| **Algorand / VOI / Hedera / Stellar public nodes** | On-chain transaction verification | Public blockchain data; no AlgoVoi data sent | Global, decentralised | On-chain protocol security |

The register is re-audited **quarterly** and updated in this repository
immediately when a vendor relationship changes.

## 4. Criteria for adding a new vendor

A new subprocessor must meet **all** of:

1. **Security attestation**: a current SOC 2 Type II, ISO 27001, PCI-DSS, or
   equivalent third-party attestation — or a documented equivalent for
   specialised providers (e.g., a public blockchain node operator)
2. **Data Processing Agreement (DPA)**: signed before any AlgoVoi data is sent
3. **Minimal data**: we send only the data the vendor needs to perform its
   function; we never send more
4. **Location**: EU/UK/US preferred; alternative locations require ISO review
5. **Breach notification**: contractual commitment to notify AlgoVoi within
   24 hours of vendor-side breach
6. **Exit plan**: documented procedure for migrating off the vendor within
   a defined timeline

## 5. Evaluation process

1. Business justification documented
2. Security review: ISO reviews vendor's latest attestation report, security
   whitepaper, and sub-subprocessor list
3. DPA drafted or reviewed (use vendor's standard; amend if needed)
4. Data flow diagram updated to show the new subprocessor
5. Approval by ISO
6. Vendor added to this register
7. Merchants notified within 30 days of any new subprocessor (material
   subprocessors only — not e.g. changes to Cloudflare's own subprocessors)

## 6. Ongoing monitoring

- **Quarterly**: re-read the vendor's public security page; note changes
- **Annually**: request an updated attestation report (SOC 2 Type II typically renews yearly)
- **On vendor change**: re-evaluate data flow and DPA terms
- **On incident**: immediate review whether vendor was a contributing factor

## 7. Sub-subprocessors

Cloudflare, Vultr, GitHub, etc. use their own subprocessors. AlgoVoi does
not maintain a running list of sub-subprocessors (this would be
impractical) but relies on each primary vendor's commitment to their
published sub-subprocessor list. Merchants can inspect each vendor's list
directly (e.g., cloudflare.com/subprocessors).

## 8. Data localisation

Merchants may have data-residency requirements (e.g., UK-only or EU-only
data). Our default is **UK-primary with EU/US failover**. For merchants
needing strict localisation:

- Payment metadata stored in the UK primary database
- On-chain data: inherently global by blockchain design (non-negotiable)
- Static assets and TLS termination: Cloudflare's global edge network

We cannot offer strict single-country data residency today. We flag this in
sales conversations; merchants requiring it must either accept the scope or
choose a different gateway.

## 9. Vendor offboarding

When ending a vendor relationship:

1. Confirm all AlgoVoi data is retrieved or deleted per the DPA
2. Rotate any credentials the vendor held
3. Remove the vendor from this register
4. Update data flow diagrams
5. Notify merchants if the change is material

## 10. Breach notification from a vendor

Handled under the [Incident Response Plan](INCIDENT_RESPONSE_PLAN.md#7-vendor-breach).

## 11. Exceptions

A vendor that doesn't meet all the criteria in §4 may still be approved if:

- The business justification is compelling
- The risk is documented and acknowledged by the ISO
- A compensating control is in place (e.g., we only send data in an
  encrypted form the vendor cannot decrypt)
- The exception is reviewed annually
