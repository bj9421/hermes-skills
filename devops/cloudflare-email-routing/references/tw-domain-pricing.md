# .tw Domain Pricing Reference (Verified Jun 2026)

Cloudflare Registrar does **not** support `.tw` / `.com.tw` / `.org.tw`. If you want CF DNS + cheaper renewal, DNS and registration must be at different providers.

## Cheapest .tw Registrars (out of 58 tracked)

| Rank | Registrar | 1st Year | Renewal | Transfer | 5-Year Total | Notes |
|------|-----------|----------|---------|----------|-------------|-------|
| 🥇 | **Porkbun** | $16.99 | **$17.99** | $16.99 | **$88.95** | Coupon `MRKEHEL`; renewal ~= 1st year (no bait-and-switch) |
| 🥇 | Porkbun (regular) | $17.99 | $17.99 | $17.99 | $88.95 | Same price without coupon |
| 🥈 | **Dynadot** | $18.00 | **$18.00** | $18.00 | $90.00 | Stable price since Nov 2025; no promo needed |
| 🥉 | OVHcloud | $20.49 | $21.99 | $20.49 | $108.45 | ICANN-accredited |
| 4 | Domgate | $23.17 | $23.17 | $23.17 | $115.85 | Slight increase from $23.10 |
| 5 | Gandi | $24.00 | $24.00 | $24.00 | $120.00 | — |
| 6 | Namecheap | $24.99 | $24.99 | $24.99 | $124.95 | — |

### Taiwan Local Registrars (NTD, includes 5% tax)

| Registrar | Renewal/yr | Notes |
|-----------|-----------|-------|
| **Cloudmax (匯智)** | **NT$550** | Promotional pricing; was NT$760 regularly |
| PChome | ~NT$800 | Where 17uu.tw is currently registered |
| Hinet | ~NT$800 | — |
| Gandi (TW pricing) | ~NT$780 | Handles .tw natively |
| 戰國策 | ~NT$800 | — |
| 遠振 | ~NT$800 | — |

## Market Context

- **Market average** for .tw registration: ~$56.89/yr.
- **續約陷阱 score**: 2.72/100 (very low — most registrars don't bait-and-switch on .tw).
- **Price stability score**: 223.43 (high consistency across registrars).
- Lowest-priced registrars (Porkbun, Dynadot) are ~70% below market average.
- No restrictions — .tw is open for registration by anyone globally (unlike .com.tw which has local presence requirements for some sub-domains).

## Key Decision Factors

1. **DNS vs Registrar are independent.** You can keep PChome registration + CF DNS for Email Routing. Or transfer to Porkbun for cheaper renewal + CF DNS.
2. **CF Registrar doesn't support .tw at all.** So if you want CF DNS, you must keep registration elsewhere regardless.
3. **Transfer process:** Request AuthCode from current registrar (PChome), initiate transfer at new registrar. Takes ~5-7 days.
4. **Porkbun vs Dynadot:** $1/yr diff — negligible. Both have free WHOIS privacy, transparent renewal pricing.

## Sources

- TLDwise.com — aggregated .tw pricing across 64 registrars
- DomainOffer.net — real-time verification with promo codes
- Cloudmax.com.tw — Taiwan local pricing
- NSS.com.tw — 2026 Taiwan registrar comparison table
