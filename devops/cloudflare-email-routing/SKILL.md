---
name: cloudflare-email-routing
description: Set up, automate, and manage custom domain email forwarding with Cloudflare Email Routing. Covers DNS migration, REST API automation, limits, and self-service web UI architecture.
version: 1.0.0
author: Hermes Agent
platforms: [linux]
---

# Cloudflare Email Routing

## Description

Cloudflare Email Routing is a **free** service for forwarding emails from your custom domain to any existing inbox (Gmail, Outlook, etc.). It supports unlimited aliases, programmatic management via REST API + Workers, and catch-all/subaddressing patterns.

This skill covers setting it up, understanding limits, automating alias provisioning, and building a self-service web interface for users to request their own `@yourdomain.com` addresses.

## When to Load

- User wants email at a custom domain (`hello@mydomain.com`)
- User asks about free email forwarding services
- User asks about automating email alias creation
- User asks about building a signup page for domain email addresses
- User asks about DNS migration to Cloudflare to enable email services

## Prerequisites

- **Know your actual registrar.** Run `whois yourdomain.com` or check purchase records. The registrar receives your renewal fees. Changing NS to Cloudflare is NOT a registrar change — renewal stays with the original provider. Don't assume the registrar from NS whois results (e.g., `cyberdns.tw` in NS records doesn't mean they're the registrar).
- Domain's DNS must be managed by Cloudflare (change NS at registrar)
- Cloudflare account (Free plan is sufficient)
- For API automation: Cloudflare API Token with `Email Routing Rules:Write` permission
- **Check TLD support.** Cloudflare Registrar does NOT support all TLDs. Confirm before planning a full transfer. DNS-only migration (NS change) works for any TLD; registrar transfer is separate and requires CF TLD support.

## Core Limits (Free Plan)

| Item | Limit |
|------|-------|
| Routing rules per domain | 200 |
| Destination addresses per account | 200 (shared across domains) |
| Inbound message size | 25 MB |
| Outbound message size | 5 MB (25 MB to verified addresses) |
| Recipients per email | 50 (to+cc+bcc combined) |
| Subject line | 998 chars |
| Domains per zone | 30 |

## Quick Start

### 1. Move DNS to Cloudflare

0. **Identify your actual registrar first** — use `whois` or your purchase email. The registrar's NS may differ from your current DNS provider. This is who you'll contact for NS changes and who handles renewal billing.
1. Add domain to Cloudflare dashboard
2. Note the Cloudflare nameservers
3. Update NS records at your registrar (NOT at your current DNS provider — the registrar holds the NS delegation)
4. Wait for propagation (24-48h, usually faster)

### 2. Enable Email Routing

In Cloudflare Dashboard → Compute → Email Service → Email Routing:
- Add and verify destination addresses (the real inboxes)
- Create routing rules mapping `alias@yourdomain.com` → destination
- Optionally enable Catch-all for unmatched addresses

### 3. Verify Setup

Send a test email to your new alias and confirm it arrives in the destination inbox. Check Cloudflare Email Routing logs for delivery status.

## REST API — Programmatic Alias Management

All routing rules are manageable via the Cloudflare REST API, enabling fully automated alias provisioning.

### Create a routing rule

```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/email/routing/rules" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actions": [{"type": "forward", "value": ["user@gmail.com"]}],
    "matchers": [{"type": "literal", "field": "to", "value": "alias@yourdomain.com"}],
    "enabled": true,
    "name": "Alias for User",
    "source": "api"
  }'
```

### List rules

```bash
curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/email/routing/rules" \
  -H "Authorization: Bearer $API_TOKEN" | jq '.result[] | {id, name, matchers, actions, enabled}'
```

### Delete a rule

```bash
curl -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/email/routing/rules/$RULE_ID" \
  -H "Authorization: Bearer $API_TOKEN"
```

See `references/cloudflare-email-api.md` for detailed endpoint reference.

## Self-Service Web Architecture

To let people apply for their own `@go.yourdomain.com` alias via a web form:

```
User submits form → verify (CAPTCHA + email verification)
          ↓
Backend creates routing rule via CF API
          ↓
User receives confirmation
```

### Backend options

| Option | Cost | Notes |
|--------|------|-------|
| **Cloudflare Worker** | Free (100k req/day) | Everything stays in CF ecosystem |
| **Pi backend (Flask + CF API)** | $0 (already running) | More control, can integrate with existing tools |

### Security considerations for public signup

- **Verification required** — CAPTCHA + email link verification to prevent abuse
- **Monitor the 200-rule limit** — add admin panel to deactivate/delete stale aliases
- **Subdomain isolation** — use `@go.17uu.tw` to contain reputation risk from the apex domain
- **SPF/DKIM implications** — if users can send-as from their Gmail, check SPF alignment
- **Rate limiting** — prevent scripted mass signup

## Pitfalls & Troubleshooting

- **🚩 Destination must be verified first.** Routing rules are auto-disabled until the destination address is verified via email link.
- **🚩 DNS transfer takes 24-48h.** Cloudflare Email Routing won't work until NS change propagates and Cloudflare is the authoritative DNS.
- **🚩 CF Registrar doesn't support all TLDs.** Notable gap: `.tw`, `.com.tw`, `.org.tw` cannot be registered or transferred to Cloudflare Registrar. If you want cheaper renewal for these, keep DNS at CF but register elsewhere (Porkbun, Dynadot, or a local TW registrar).
- **🚩 DNS change ≠ registrar change.** Moving NS to Cloudflare only changes DNS resolution. Your domain registration (renewal, transfer) stays with the original registrar at their existing rates. These two decisions are independent and can be mixed (e.g., CF DNS + PChome renewal, or CF DNS + Porkbun renewal after transfer).
- **🚩 Rule priority matters.** When multiple rules match the same pattern, the first one wins. Avoid creating duplicate patterns.
- **🚩 Workers Free plan CPU limits.** Complex email handlers (attachment processing, heavy parsing) may hit `EXCEEDED_CPU` on free Workers.
- **🚩 Sending vs receiving.** Email Routing handles inbound only. To reply as `alias@yourdomain.com`, set up Gmail "Send Mail As" with SMTP or use a full transactional email service.
- **🚩 200 rules fill up fast for public service.** Plan for lifecycle management — allow users to delete their own aliases, and have an admin purge stale ones.
- **🚩 Subaddressing (plus addressing).** Enable in dashboard settings. `user+tag@domain.com` matches `user@domain.com` rule. Can be overridden by an explicit `user+tag@domain.com` rule.

## Related

- Official docs: https://developers.cloudflare.com/email-service/
- API reference: https://developers.cloudflare.com/api/resources/email_routing/
- Local dev testing: `wrangler dev` with simulated emails
- Alternatives: ImprovMX (free for 1 domain, no DNS transfer needed), Forward Email (open source, with IMAP)
