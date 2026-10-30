# Flyrel waitlist website

A deliberately small landing page: a hero with a one-line waitlist capsule (email, multi-select
brokers, explicit early-access consent), a concept preview of what Flyrel intends to decide, and
the broker list. The 172-entry catalog covers all major world regions. It measures interest, not
supported integrations, broker recommendations, customer eligibility, or a promise of future
availability. `markets` values are search hints, not a list of jurisdictions where a visitor can
open an account.

This is a separate Cloudflare Worker with static assets and a D1 database. It imports no MCP
code, loads no broker credentials, and cannot place or modify orders. It needs no frontend
framework or build step. Signup data is never stored in browser storage.

The console on the page is a looping illustration, not product output. Its orders, amounts and
rules are synthetic and it is labelled as a concept. Keep that label, and keep copy about limits
and approvals in the future tense of "what we're building" until enforcement actually exists.

## Assets

- `public/fonts/`: self-hosted Mona Sans, Geist and Geist Mono (SIL OFL, licenses alongside). The
  CSP allows only same-origin fonts.
- `public/globe.js`: draws the hero globe on a canvas. It pauses off-screen and renders one static
  frame under `prefers-reduced-motion`. Arcs and hubs are decorative, not order flow.
- `public/globe-mask.js`: generated land/sea bits from Natural Earth (public domain). Regenerate
  with the command at the top of `scripts/generate-globe-mask.mjs`.

## Local development

Requires Node.js 22.13+ (Node 24 recommended).

```bash
cd website
npm ci
npm run db:local
npm run dev
```

Wrangler prints the local URL. D1 data stays in ignored `.wrangler/`; local development does not
use the production database. Use invented `@example.invalid` addresses for testing.

```bash
npm test
npm run check
npx playwright install chromium
npm run test:browser
```

`npm test` executes the actual migration and handler queries against SQLite, including duplicate
signups, broker ID validation, consent, request bounds, SQL parameterization, rate limiting and
storage failures. Browser tests start a real local Worker/D1, submit a signup, and check mobile
selection, keyboard dismissal, the 20-broker cap, failure recovery, reduced motion, security
headers and the privacy page. Test screenshots and runtime data are ignored. CI runs these alongside the existing Python checks.

## Deploy to Cloudflare

Deploy from the reviewed feature branch / merged PR. No production deployment, database or
domain is provisioned by committing this code. The checked-in database UUID is an explicit
placeholder; replace it before production deployment.

```bash
cd website
npm ci
npx wrangler login
npx wrangler d1 create flyrel-waitlist
```

Copy the returned `database_id` into `wrangler.jsonc`. A database ID is a resource identifier,
not a credential. Keep authentication tokens out of the checkout and Git. For automation use
Cloudflare's authenticated environment; do not put tokens in shell arguments or configuration.

```bash
npm run db:remote
npm run check
npm run deploy
```

Wrangler returns the deployed `workers.dev` URL. In the Cloudflare dashboard, open this Worker's
**Settings → Domains & Routes → Add → Custom Domain** and attach `flyrel.com` (or the desired
subdomain) after its DNS zone is active in that account. Add `www.flyrel.com` separately if needed.
The asset/API paths are relative, so no source change is needed for the custom domain. Verify a
single invented signup on the deployed domain, inspect it in D1, and delete that test entry.

The rate-limit namespace `1001` should be unique to this form in the account. Change it if
another Worker uses it. The configured binding allows five attempts per IP per minute per
Cloudflare location. Cloudflare describes these counters as permissive and eventually consistent;
this is basic spam mitigation, not a strict global quota. A hidden honeypot also drops obvious
bot submissions. Neither verifies email ownership. If abuse grows, add a separately configured
challenge such as Turnstile; do not treat consent or an email-shaped string as identity proof.

## Data and operation

`POST /api/waitlist` accepts same-origin JSON only. It validates email, explicit consent,
1–20 known broker IDs (or `other` plus a nonempty name), and an 8 KiB body limit. The response
reports success only after D1 accepts the insert (apart from deliberately discarded honeypot
submissions). Missing bindings or storage failures return 503.

Email addresses are trimmed and case-normalized and are unique in D1. A repeated signup returns
the same response and preserves the original broker preferences, consent and timestamp. There
is intentionally no unauthenticated update, membership check, subscriber list or export endpoint.
All SQL values are bound parameters. Rate-limit IP keys are not saved in D1. The handler logs
no submissions or error details, and Worker observability is disabled in the checked-in config.
Cloudflare may still process network/service metadata under the account's platform settings.

Use the authenticated Cloudflare D1 console to inspect entries and handle removal requests.
Restrict database/dashboard access to the people managing early access. Export personal data
only to a protected location outside this checkout; never commit it, attach it to a PR, or put
it into an issue. Delete requested records by exact email through the authenticated D1 console.
Review retained entries as the early-access program changes.

This release stores signups; it does **not** send confirmation, welcome or campaign emails.
Before sending early-access emails, use a monitored sender that handles replies/removal requests,
and update the privacy page if another data processor is introduced. Until a private support
mailbox is established, the privacy page links to the project's real issue tracker to request a
private contact channel and explicitly warns visitors not to publish personal data there.
It describes the implemented data flow; it is not a claim of regulatory certification.

## Broker catalog and sources

Edit `public/brokers.json` to maintain display names, stable IDs, region grouping, search hints
and official-site references. The browser and Worker share this exact catalog; there is no
mapping from waitlist IDs to trading adapters. Preserve stored IDs when changing display names.
Retired catalog IDs remain in existing records; don't repurpose them for another firm.

Broker websites are recorded per entry. Each of the 93 entries added for the redesign was requested
on October 30, 2026, and rebrands or dead links found that way were corrected or removed. That
check shows a site responds (some answer automated requests with 403, and BMO's redirect target
could not be reached from the check machine); it does not confirm current services. The original
79 entries' representative references from the same date:
[EasyEquities](https://www.easyequities.co.za/),
[Bamboo's availability notice](https://faq.investbamboo.com/en/articles/6884650-what-countries-is-bamboo-available-in),
[Hapi](https://hapi.trade/en), [trii](https://www.trii.co/blog/como-instalar-trii-y-tener-la-cuenta-lista-para-invertir-179),
[Stake](https://hellostake.com/), [Tiger Brokers](https://www.itiger.com/sg/), and
[Saxo](https://www.home.saxo/products/stocks). These support catalog discovery only. They are
not evidence of Flyrel connectivity, API access, legal eligibility or an exhaustive current
broker directory; users can supply names we missed through Other.

Cloudflare implementation references checked October 30, 2026:
[static asset bindings](https://developers.cloudflare.com/workers/static-assets/binding/),
[Wrangler configuration](https://developers.cloudflare.com/workers/wrangler/configuration/), and
[rate-limit bindings and their limits](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/).
