# Cloudflare Email Routing API Reference

> Session date: 2026-07-16
> Context: Research for 17uu.tw → Cloudflare migration + self-service email alias system

## REST API Endpoints

Base URL: `https://api.cloudflare.com/client/v4`

### Authentication

Two methods (use API Token, NOT Global Key when possible):

```bash
# Recommended: API Token
-H "Authorization: Bearer $API_TOKEN"

# Legacy: Email + Global Key
-H "X-Auth-Email: user@example.com"
-H "X-Auth-Key: $GLOBAL_API_KEY"
```

Required permission scope: **Email Routing Rules:Write** (or Read for read-only ops)

### Create Routing Rule

```
POST /zones/{zone_id}/email/routing/rules
```

**Body:**
```json
{
  "actions": [
    {
      "type": "forward",
      "value": ["destination@example.com"]
    }
  ],
  "matchers": [
    {
      "type": "literal",
      "field": "to",
      "value": "alias@yourdomain.com"
    }
  ],
  "enabled": true,
  "name": "Human-readable name",
  "priority": 0,
  "source": "api"
}
```

**Key notes:**
- `actions[].type`: one of `"forward"`, `"drop"`, `"worker"`
- `matchers[].type`: `"literal"` matches exact `to` address; `"all"` matches everything (catch-all)
- `matchers[].field`: must be `"to"` for literal type
- `matchers[].value`: max 90 chars
- Destination must be verified before the rule activates
- `actions[].value` is an array of string. For forward type, the first element is the destination.
- `source: "api"` means managed via API/dashboard/Terraform; `"wrangler"` means managed by a Worker's wrangler.jsonc

### List Routing Rules

```
GET /zones/{zone_id}/email/routing/rules
```

### Get Single Rule

```
GET /zones/{zone_id}/email/routing/rules/{rule_id}
```

### Update Rule

```
PUT /zones/{zone_id}/email/routing/rules/{rule_id}
```

### Delete Rule

```
DELETE /zones/{zone_id}/email/routing/rules/{rule_id}
```

### Patch Rule (enable/disable)

```
PATCH /zones/{zone_id}/email/routing/rules/{rule_id}
```

Body:
```json
{
  "enabled": false
}
```

## Practical curl Examples

```bash
# === GET ZONE ID ===
# Find your zone_id from Cloudflare dashboard, or use:
ZONE_ID=$(curl -s "https://api.cloudflare.com/client/v4/zones?name=yourdomain.com" \
  -H "Authorization: Bearer $API_TOKEN" | jq -r '.result[0].id')

# === CREATE ALIAS ===
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/email/routing/rules" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actions": [{"type": "forward", "value": ["user@gmail.com"]}],
    "matchers": [{"type": "literal", "field": "to", "value": "john@go.17uu.tw"}],
    "enabled": true,
    "name": "John - personal alias",
    "source": "api"
  }' | jq .

# === LIST ALL RULES ===
curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/email/routing/rules" \
  -H "Authorization: Bearer $API_TOKEN" | jq '.result[] | {id, name, matchers, actions, enabled}'

# === DELETE A RULE ===
curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/email/routing/rules/$RULE_ID" \
  -H "Authorization: Bearer $API_TOKEN" | jq .

# === DISABLE A RULE (without deleting) ===
curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/email/routing/rules/$RULE_ID" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' | jq .
```

## Destination Addresses

### Add a Destination

```
POST /zones/{zone_id}/email/routing/destinations
```

Body:
```json
{
  "email": "user@gmail.com"
}
```

Cloudflare sends a verification email. Rule stays disabled until verified.

### List Destinations

```
GET /zones/{zone_id}/email/routing/destinations
```

## Workers Integration

Instead of forwarding to a fixed inbox, you can route to a Cloudflare Worker for custom processing:

```javascript
export default {
  async email(message, env, ctx) {
    // Custom logic: spam filter, database, forward to multiple inboxes, etc.
    await message.forward("user@gmail.com");
  }
}
```

The Worker binding is set in `wrangler.jsonc`:
```json
{
  "email_binding": {
    "type": "email_routing",
    "domain": "yourdomain.com"
  }
}
```

## Limits Recap

| Category | Limit |
|----------|-------|
| Routing rules per domain | 200 |
| Destination addresses per account | 200 |
| Inbound email size | 25 MB |
| Outbound email size (via API) | 5 MB (25 MB to verified destinations) |
| Recipients per email | 50 |
| Subject line | 998 chars |
| Domains per zone | 30 |

## Self-Service Architecture Reference

For a web form where users apply for their own alias:

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  User visits │────▶│  Backend (Worker │────▶│  CF API          │
│  web form    │     │  or Pi/Flask)    │     │  POST /rules     │
└─────────────┘     └──────────────────┘     └──────────────────┘
       │                      │                        │
       │  submit form         │  verify + CAPTCHA      │  create rule
       │  (alias + dest)      │  check quota           │  return rule_id
       ▼                      ▼                        ▼
```

**Checklist for production:**
- [ ] Prevent duplicate alias creation
- [ ] Verify destination via email link (not just form submission)
- [ ] CAPTCHA to block bots
- [ ] Track remaining quota (200 - current rule count)
- [ ] Admin dashboard to view/disable/delete aliases
- [ ] Rate limiting per IP (e.g., max 3 aliases per day)
- [ ] Optional: invite code system for closed beta
