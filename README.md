<div align="center">

# AjoVault

**Your group savings. Protected by crypto. Trusted by all.**

A full-stack, crypto-powered Ajo/Susu group savings platform for Nigeria and Ghana.

</div>

---

## Stack

- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS** + **Framer Motion** + **Lucide React**
- **Prisma** + **SQLite** (local dev)
- **NextAuth.js** — credentials + Google
- **Coinbase Commerce** — USDT / USDC / ETH / BTC deposits
- **Recharts** — savings charts
- **qrcode.react** — crypto deposit QR codes
- **React Hot Toast** — notifications

---

## 1. Run locally (step by step)

```bash
# 1. Install deps
npm install

# 2. Copy env and edit as needed
cp .env.example .env

# 3. Push schema to SQLite
npx prisma db push

# 4. Seed demo data (3 users, 5 groups, 20+ transactions)
npm run db:seed

# 5. Start dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Demo login:** `adaeze@demo.com` / `password123`
Other seeded users: `kwame@demo.com`, `chinedu@demo.com`, `fatima@demo.com`, `akosua@demo.com` — all use `password123`.

---

## 2. Get a Coinbase Commerce API key

1. Go to [commerce.coinbase.com](https://commerce.coinbase.com) and create a merchant account.
2. Verify your business email.
3. Navigate to **Settings → Security → API keys**.
4. Click **Create an API key** and copy the generated key.
5. Paste it into `.env`:

   ```bash
   COINBASE_COMMERCE_API_KEY="your_key_here"
   ```

6. Restart the dev server. The Wallet page will switch from demo-mode to live charges.

> Without the key, the Deposit Modal still works — it creates a simulated charge so you can walk through every step of the UI. Demo charges auto-confirm after 30s.

---

## 3. Set up webhooks

Coinbase Commerce fires real-time events when a payment confirms. Wire them up so balances update automatically.

1. In the Coinbase Commerce dashboard, go to **Settings → Notifications → Webhook subscriptions**.
2. Click **Add an endpoint** and enter:

   ```
   https://<your-domain>.com/api/webhooks/coinbase
   ```

   For local development, expose your server with `ngrok http 3000` and use the forwarding URL.

3. Click **Show shared secret** and copy it. Paste into `.env`:

   ```bash
   COINBASE_COMMERCE_WEBHOOK_SECRET="your_secret_here"
   ```

4. Subscribe the endpoint to at least these events:
   - `charge:confirmed`
   - `charge:failed`
   - `charge:delayed`
   - `charge:pending`

The handler at `/api/webhooks/coinbase` verifies the `X-CC-Webhook-Signature` header using HMAC-SHA256 before touching the database.

---

## 4. Test payments

Coinbase Commerce does not ship a sandbox mode, so there are two practical options for testing end-to-end:

**Option A — Small live payment:** Create a charge for `$1`, scan the QR in your own wallet, send USDT. The webhook fires in ~1 minute.

**Option B — Webhook replay:** In Coinbase Commerce **Settings → Webhooks → Recent deliveries**, replay a past `charge:confirmed` event against your local `ngrok` URL. This tests the full credit flow without spending crypto.

**Option C — Demo mode:** Leave `COINBASE_COMMERCE_API_KEY` unset. The Deposit Modal will generate a simulated charge that auto-confirms after 30 seconds so you can exercise the full UI flow (QR, countdown, polling, success screen) without any money changing hands.

---

## 5. Deploy to Vercel (free)

1. Push this repo to GitHub.
2. Go to [vercel.com/new](https://vercel.com/new) and import the repo.
3. In **Environment Variables**, add:

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | `file:./dev.db` (for demo) or your Postgres URL |
   | `NEXTAUTH_SECRET` | Generate: `openssl rand -base64 32` |
   | `NEXTAUTH_URL` | `https://your-app.vercel.app` |
   | `COINBASE_COMMERCE_API_KEY` | From Coinbase Commerce |
   | `COINBASE_COMMERCE_WEBHOOK_SECRET` | From Coinbase Commerce |
   | `GOOGLE_CLIENT_ID` (optional) | From Google Cloud Console |
   | `GOOGLE_CLIENT_SECRET` (optional) | From Google Cloud Console |

4. Click **Deploy**.

> **Production note:** SQLite is fine for development and demos but won't persist across Vercel serverless instances. Switch `DATABASE_URL` to a hosted Postgres (Vercel Postgres, Supabase, Neon, Railway) and update the Prisma datasource `provider` to `postgresql` before going live.

5. After deploy, go back to Coinbase Commerce and point your webhook at:

   ```
   https://your-app.vercel.app/api/webhooks/coinbase
   ```

---

## Project layout

```
app/
  page.tsx                     # Landing page
  auth/login, auth/register    # Auth
  dashboard/                   # Authenticated app
    page.tsx                   # Home (stats + chart + recent activity)
    groups/                    # My groups list + [id] detail
    create/                    # Create group with live preview
    transactions/              # Filterable tx table + CSV export
    wallet/                    # Balance, deposit modal, withdraw, history
    settings/                  # Profile, security, notifications, bank
  api/
    auth/[...nextauth]         # NextAuth handler
    auth/register              # Credential signup
    groups                     # Create group
    user/profile               # Update profile
    wallet/deposit             # POST — create Coinbase charge
    wallet/charge/[chargeId]   # GET — status + auto-credit on confirm
    wallet/withdraw            # POST — off-ramp request
    webhooks/coinbase          # POST — Coinbase Commerce webhook

components/
  landing/*                    # Navbar, Hero, HowItWorks, Stats, Features,
                               # Testimonials, Pricing, FAQ, Footer
  dashboard/*                  # Shell, StatCard, SavingsChart, TransactionsView,
                               # WalletView, SettingsView, CopyInviteLink,
                               # PayoutCountdown
  wallet/DepositModal.tsx      # 4-step deposit flow with QR + polling
  Logo.tsx, Providers.tsx

lib/
  prisma.ts                    # Singleton Prisma client
  auth.ts                      # NextAuth options
  coinbase.ts                  # createCharge, getCharge, listCharges, verifyWebhookSignature
  utils.ts                     # Formatting helpers

prisma/
  schema.prisma                # User, Wallet, Group, GroupMember, Contribution,
                               # Transaction, Charge, Notification + NextAuth tables
  seed.ts                      # 5 users, 5 groups, contributions, 20+ tx, notifications
```

---

## Brand

| | |
|---|---|
| Primary | `#D4A017` Deep Gold |
| Secondary | `#0A0A0A` Rich Black |
| Accent | `#10B981` Emerald |
| Background | `#0F0F0F` |
| Card | `#1A1A1A` |
| Font | Inter |

Dark mode throughout. Fully responsive. Mobile sidebar collapses to a bottom nav.

---

## Scripts

```bash
npm run dev        # Start dev server
npm run build      # Production build
npm run start      # Start production server
npm run db:push    # Sync Prisma schema to DB
npm run db:seed    # Seed demo data
npm run db:reset   # Wipe DB and re-seed
```
