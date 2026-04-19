# Acceptable Use Policy

**Owner**: Information Security Officer
**Effective**: 2026-04-19
**Next review**: 2027-04-19
**SOC 2 mapping**: CC1 (Control Environment)

## 1. Purpose

Define what is and is not acceptable use of AlgoVoi's systems, credentials,
and data by personnel (employees, contractors, advisors). This protects
AlgoVoi, its merchants, their customers, and the people doing the work.

## 2. Scope

Applies to everyone with access to AlgoVoi resources, whether granted via
employment, contractor agreement, advisor arrangement, or any other path.

## 3. Core expectations

### 3.1 Confidentiality

- Treat every piece of non-public AlgoVoi data as confidential by default
- Never share credentials (API keys, passwords, session tokens, SSH keys) with anyone, including other AlgoVoi personnel
- Never post credentials, production data, or internal architecture details in public forums, social media, or AI chat interfaces that send data to third parties without an AlgoVoi-approved DPA
- When in doubt, ask the ISO before sharing

### 3.2 Data minimisation

- Don't export production data to personal devices
- Don't screenshot production dashboards unless specifically needed for a documented purpose, and redact what you don't need
- Synthetic / sanitised data is always the preferred tool for demos, docs, and debugging

### 3.3 System use

- Use AlgoVoi accounts and credentials only for AlgoVoi work
- Don't attempt to circumvent security controls, rate limits, or access boundaries on AlgoVoi systems — even to test them — without prior ISO approval (penetration testing is welcome, but scheduled, bounded, and documented)
- Don't install software on production hosts that isn't part of the approved stack; if you think something should be added, it goes through Change Management

### 3.4 Device hygiene

Personal devices used for AlgoVoi work must:

- Have an encrypted disk (FileVault / BitLocker / LUKS)
- Auto-lock after 5 minutes of inactivity
- Run a currently-supported OS with security updates applied
- Not run random screen-share / remote-control software

### 3.5 Mandatory practices

- Multi-factor authentication on every AlgoVoi-related account (GitHub, Cloudflare, Vultr, npm, PyPI, email, domain registrar)
- Separate browser profile for AlgoVoi work (reduces cross-site risk from extensions and cookies)
- Password manager used for all credentials
- No reuse of AlgoVoi credentials for non-AlgoVoi services

## 4. Prohibited actions

The following are never acceptable:

- Committing plaintext secrets to Git
- Running `git push --force` on a shared branch without team agreement
- Disabling a security control (WAF rule, rate limit, HMAC verification) to "just test something"
- Using merchant data for any purpose other than operating the service
- Contacting a merchant's customers directly using data obtained through AlgoVoi
- Running production queries that modify data (UPDATE, DELETE) outside of an approved change process
- Running load tests against production (use a staging environment)
- Copying code that's clearly proprietary to a competitor into AlgoVoi's codebase
- Exfiltrating AlgoVoi data when leaving the organisation

## 5. AI tooling

AI coding assistants (Claude, Copilot, Cursor, etc.) are permitted and
encouraged, with conditions:

- The assistant must not have access to production data or credentials
- Sensitive files (keys, .env, secrets) must be excluded from the assistant's context
- Code the assistant generates is reviewed with the same rigour as human code
- The assistant's training data terms must be acceptable (prefer providers who
  don't train on your prompts by default — e.g., Anthropic's API, OpenAI's API
  with opt-out enabled, Azure OpenAI, self-hosted models)

## 6. Reporting

Everyone is expected to report:

- Any suspected security incident to security@algovoi.co.uk within 1 hour of awareness
- Any mistake you made (accidentally committed a secret, lost a device, sent data to the wrong place) — **no blame culture**; concealment is far worse than reporting
- Any observed violation of this policy by another person

## 7. Privacy of personnel

AlgoVoi does not monitor personal communications, does not read personal email
even on company-provided devices without a lawful basis, and does not use
keystroke or screen-capture surveillance tools. What AlgoVoi does log:

- Application-level access and action logs for AlgoVoi systems (who did what)
- Git commit history (public by nature)
- Vendor-side audit logs (GitHub, Cloudflare, etc.) as retained by those vendors

## 8. Enforcement

Violations are reviewed case-by-case, proportionate to severity. The range:

- Informal conversation for first-time minor violations
- Formal written notice for repeated or moderate violations
- Access revocation + contract termination for deliberate or severe violations
- Legal or regulatory notification where warranted

## 9. Acknowledgement

Every person with access to AlgoVoi systems reads and agrees to this policy
at onboarding and at each annual review. Acknowledgement is tracked in the
compliance repository.
