# Incident Response Plan

**Owner**: Information Security Officer (also Incident Response Lead)
**Effective**: 2026-04-19
**Next review**: 2027-04-19 (or after any Severity 1 incident)
**SOC 2 mapping**: CC7 (System Operations)

## 1. Purpose

Define how AlgoVoi identifies, contains, investigates, remediates, and
communicates security incidents.

## 2. Scope

Any event that threatens confidentiality, integrity, or availability of
AlgoVoi systems or merchant/customer data. Includes:

- Unauthorised access (attempted or successful)
- Data exposure (accidental or malicious)
- Service outage or degradation affecting production
- Vendor breach notification
- Suspected phishing, social engineering, or insider threat
- Regulatory compliance failure

## 3. Contact and reporting

### 3.1 Report a suspected incident

| Channel | Who |
|---|---|
| Email | security@algovoi.co.uk |
| Security.txt | https://algovoi.co.uk/.well-known/security.txt |
| Out-of-band phone | Published to partners on request |

Anyone — merchant, customer, security researcher, employee, vendor — can
report to the email above. We aim to acknowledge within **4 hours** during
business hours, **24 hours** out of hours.

### 3.2 Internal escalation

1. First responder: whoever notices (on-call engineer)
2. Incident Commander: ISO (or delegate when team grows)
3. Communications lead: ISO
4. Legal counsel: engaged for Severity 1 or any regulatory-notifiable event

## 4. Severity levels

| Severity | Definition | Response target | Examples |
|---|---|---|---|
| **SEV 1** | Active harm to users or data; regulatory notification likely required | Engagement within **30 min** 24/7 | Confirmed data breach; production API down > 15 min; suspected credential compromise |
| **SEV 2** | Significant risk, no confirmed harm yet | Engagement within **2 hours** during business hours | Vulnerability publicly disclosed; suspicious access pattern; vendor breach notification affecting us |
| **SEV 3** | Limited scope or non-urgent | Engagement within **1 business day** | Low-severity CVE in dependency; misconfiguration with limited blast radius |
| **SEV 4** | Informational | Review at next team standup | False positive alerts; hygiene issues |

## 5. Response workflow

### 5.1 Identify

- Declare the incident in a named channel (a GitHub issue labelled `incident`, a Slack channel, or an email thread — whichever is fastest)
- Assign the Incident Commander
- Note the detection source (alert, report, external disclosure, etc.)

### 5.2 Contain

Priority is stopping further harm. Typical containment moves:

- Rotate the affected credentials (API keys, webhook secrets, database passwords, SSH keys)
- Block the malicious actor at the edge (Cloudflare WAF custom rule)
- Disable the affected endpoint, feature, or integration
- Isolate the affected service (take it out of the load balancer, pause the process, kill the container)
- Preserve evidence **before** making destructive changes where feasible (snapshots, log exports)

### 5.3 Investigate

- Timeline: when did it start? How was it detected? What actions happened when?
- Scope: what data was accessed/modified/exfiltrated? Which tenants?
- Root cause: why did it happen? What control failed or was absent?
- External exposure: was the event visible to third parties?

### 5.4 Remediate

- Apply the fix that addresses the root cause (not just the symptom)
- Verify the fix holds under simulated reproduction
- Close the incident only when the Incident Commander is satisfied

### 5.5 Communicate

- **Internal**: continuous during the incident
- **Affected merchants**: within **72 hours** of confirmation of impact (GDPR Article 33 requires supervisory authority notification within this window; we apply the same to merchants)
- **Regulators**: ICO for personal data breaches, FCA if regulated activity is implicated, HMRC if criminal-proceeds notification applies (PoCA s.330)
- **Public**: for widespread or material incidents, a public post-mortem on the algovoi.co.uk site

### 5.6 Learn

Within **7 days** of incident closure, publish an internal post-mortem that
covers:

- What happened (facts, timeline)
- What went well (detection, response speed, containment)
- What went wrong (control gaps, delays)
- Actions (with owners and due dates)
- Policy updates (which policy documents need changes)

Post-mortems are **blameless**: focus on systems and processes, not individuals.

## 6. Data breach decision matrix

Within 72 hours of confirming a breach involving personal data, we must
assess and, if applicable, notify:

| Situation | Notification |
|---|---|
| Personal data exposed + risk to individuals | ICO + affected individuals |
| Personal data exposed + no risk to individuals | Document decision, no notification |
| Merchant business data exposed | Merchant notified within 72 hours |
| Payment-related data (order IDs, amounts) exposed | Merchant notified; reviewed with MLRO if AML implications |
| On-chain data (already public) exposed | Not a breach — on-chain data is public by design |

## 7. Vendor breach

When a subprocessor (Cloudflare, Vultr, npm, etc.) reports a breach:

1. Receive the notification via the contact listed in our vendor register
2. Assess whether AlgoVoi data was in scope
3. If yes: run our own investigation under this plan, treating the vendor notification as the trigger
4. If no: document the decision and continue normal operations

## 8. Law enforcement coordination

If law enforcement approaches AlgoVoi directly (NCA, police, HMRC, etc.),
the ISO is the sole point of contact. All requests are:

- Verified against an independent channel (do not trust the caller's identity without verification)
- Logged
- Reviewed by legal counsel before action
- Complied with as required by law — but no more than required

We preserve customer privacy to the maximum extent the law allows.

## 9. Evidence preservation

For any SEV 1 or SEV 2 incident:

- Snapshot relevant logs at the time of detection
- Capture the state of affected systems (running processes, network state, current configuration)
- Preserve for the longer of: 1 year, or the full duration of any related investigation
- Use a write-once storage mechanism where practical

## 10. Testing this plan

The response process is exercised at least **annually** via a tabletop
exercise. Findings from exercises feed back into policy updates.

## 11. Related

- [Information Security Policy](INFORMATION_SECURITY_POLICY.md)
- [Access Control Policy](ACCESS_CONTROL_POLICY.md) — for credential rotation
- [Business Continuity & DR](BUSINESS_CONTINUITY_PLAN.md) — for recovery procedures
- [Vendor Management Policy](VENDOR_MANAGEMENT_POLICY.md) — for subprocessor breach handling
