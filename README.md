# LocalFork

A marketplace where home cooks and small food businesses can list dishes and take orders — no storefront, no restaurant license required to get started. Think "Facebook Marketplace meets DoorDash," but for people who cook at home.

Working name only — rename anytime, it's just text in a couple of files (see "Renaming" below).

## Two sites, one database

This is built as **two separate websites that share one database**, the same way DoorDash's customer app and its merchant portal are two different products backed by the same orders:

- **`customer/`** — the public site. Browse cooks, view menus, cart, checkout, track orders.
- **`seller/`** — the seller portal. A different look (dark header, "LocalFork for Cooks" branding), separate signup flow, menu management, and incoming-order management.

They're separate Flask apps, on separate ports, with separate templates — but both read/write the same `instance/localfork.db`, so a dish added in the seller portal appears on the customer site instantly, and an order placed on the customer site appears in the seller portal instantly. In production these become two subdomains (e.g. `localfork.com` and `sell.localfork.com`) pointed at the same database — nothing about the app logic needs to change for that.

**Logins are independent between the two sites** — each uses its own session cookie, so you can be logged in as a different person on the customer site and the seller portal at the same time in the same browser (handy for testing: be "Buyer A" on one tab and "Seller B" on the other, with no incognito window needed). The underlying account table is still shared, though: if someone signs up as a buyer and later wants to sell, they log into the seller portal with the *same email/password* and get prompted to add a business profile to that existing account rather than creating a whole new one — same account, but each site remembers its own separate login.

## What's built

**Customer site:**
- Browse & search cooks by city
- Public seller pages with menu, prices, bio (business address stays private until you order — see below)
- Cart with +/- quantity steppers
- Checkout: pick a pickup date & time (as soon as the order can realistically be made, up to **7 days** out — see "Scheduling rules")
- Order page: seller's pickup address (revealed once you've ordered), a message thread with the cook, and a cancel button that enforces the cancellation policy
- Buyer signup/login, order history, and a "due soon" reminder banner for pickups within 24 hours

**Seller portal:**
- Dedicated signup (creates account + business profile together) or "add a seller profile" for an existing account
- Dashboard: add/edit/hide/delete menu items, each with a photo and an estimated prep time; orders sorted soonest-pickup-first with a "due soon" banner/badges
- Accept or decline each incoming order with one click
- Business page: photo, city, and a **pickup address that's private** until a customer actually orders
- Order page: update status (accepted → ready → completed), message the customer, see the late-cancellation-fee flag if a customer cancelled late

**Both sites:**
- `/account` — anyone can set their display name and upload a profile photo; it shows up as a small avatar in the nav on both sites (falls back to an initial-letter circle if no photo is set)
- In-app messaging per order (no email/SMS involved). Messages run through a small word filter — a blocked message never reaches the other person; the attempt is logged to a `flagged_messages` table (and the dev-side app log) instead of being silently dropped with no record.

### Scheduling rules

- A customer can book a pickup slot anywhere from **as soon as the order can be made** up to **7 days** ahead. "As soon as it can be made" is the *median* of the estimated prep times across the distinct dishes in the order (e.g. one dish takes 12 minutes, another takes 18 → the order is quoted at 15 minutes) — set per-dish by the seller in the menu form.
- **Cancelling** an order: free more than 24 hours before pickup; within 24 hours, the full order amount applies as a late-cancellation fee (recorded as a flag today — see "Going live" for wiring up a real charge); inside the last 15 minutes, cancellation is blocked entirely.
- There's no email/SMS reminder system connected, so "notify people a day ahead" is implemented as an **in-app banner**: anyone with a pickup due within 24 hours sees it right on their orders/dashboard page next time they load it. Wiring up real push/email/SMS reminders is a "Going live" step (needs a mail/SMS provider + a scheduler).

Uploaded photos (dish, business, profile) are stored in `static/uploads/` and shared between both apps automatically, since they read the same folder. Payment today is "pay the cook directly at pickup/delivery" — no card processing yet. See "Going live" below.

## Running it on your computer

You need Python 3 (already installed on this Mac). From the `localfork` folder, in **two separate terminal windows**:

```bash
# Terminal 1 — customer site
cd ~/localfork
python3 -m pip install -r requirements.txt
python3 customer/app.py
```

```bash
# Terminal 2 — seller portal
cd ~/localfork
python3 seller/app.py
```

- Customer site: **http://localhost:5050**
- Seller portal: **http://localhost:5051**

Sample seller accounts (password `password123` for all): `maria@example.com`, `priya@example.com`, `sam@example.com`. Log into the seller portal with one of these to see its dashboard, or sign up fresh as a buyer on the customer site and place an order.

To wipe and reseed the sample data at any point:
```bash
rm instance/localfork.db
python3 -c "from db import init_db; init_db()"
python3 seed.py
```

**If `python3` says "You have not agreed to the Xcode license agreements":** this is a one-time macOS thing, unrelated to this app. Run `sudo xcodebuild -license` in Terminal, accept it, and `python3` will work normally again.

## Project layout

```
db.py, schema.sql, seed.py   – shared database (used by both sites)
customer/
  app.py                     – buyer-facing routes
  templates/
seller/
  app.py                     – seller-facing routes
  templates/
static/
  style.css                  – shared design system
  seller.css                 – seller-portal-only accents (dark header, etc.)
  uploads/                   – uploaded photos land here (not in git)
uploads.py                   – shared photo upload/delete helper
wsgi_combined.py             – runs both sites in one process for the quick test deploy only
instance/                    – the database file lives here (not in git)
```

## Quick test deploy (free, ~15 minutes, one link to share)

Want a real public URL to try yourself or hand to someone else, without doing the full production setup below? Here's the fast path — no domain, no database migration, no payment setup.

**Why this needs a small tweak first:** the customer and seller sites share one SQLite file *only because they run on the same computer*. If you deployed them as two separate services on a host like Render, each one gets its own isolated disk — orders placed on the customer site would never show up for the seller. To keep them sharing one database for a quick test, this repo includes `wsgi_combined.py`, which runs both sites in a single process: the customer site at the root URL and the seller portal at `/seller`. I tested this locally (via gunicorn, the same server a host would use) — placing an order through the customer side and confirming it appeared instantly on the seller side — before writing these steps.

**Limitations worth knowing before you share the link:** free-tier services on most hosts "sleep" after ~15 minutes of no traffic, so the first visit after a quiet spell takes 30–50 seconds to wake up. Also, a restart can reset the SQLite file back to the seeded sample data — fine for a demo, not a place to leave data you care about.

1. **Push this code to GitHub** (create a free account at github.com if you don't have one, then create a new repository):
   ```bash
   cd ~/localfork
   git remote add origin https://github.com/YOUR-USERNAME/localfork.git
   git push -u origin main
   ```

2. **Create a free account at [render.com](https://render.com)** — signing in with GitHub is easiest, since it can then see your repo directly.

3. **New → Web Service → pick your repo**, then set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn wsgi_combined:application`
   - Instance type: Free
   - Environment variables: `SELLER_PORTAL_URL` = `/seller`, `CUSTOMER_SITE_URL` = `/`, and `SECRET_KEY` = a random string (generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"` — this signs login sessions, so don't leave it as the code's default once the app is public)

   Click **Create Web Service**. Render builds it and gives you one URL, e.g. `https://localfork-test.onrender.com`.

4. **Try it:** the customer site is at that URL directly; the seller portal is at `<that URL>/seller`.

This is genuinely one shared app for testing, not the two-independent-sites production architecture — see "Going live" below for deploying them as real separate services once you're past the testing stage.

## Going live (real public websites)

Everything above (aside from the quick test deploy) runs only on this computer. To get real public links as two properly independent sites, roughly in order:

1. **Put the code on GitHub.**
   ```bash
   cd ~/localfork
   git add . && git commit -m "Split into customer + seller sites"
   ```
   (already a git repo — just push to a GitHub repo you create)

2. **Deploy both apps.** [Render.com](https://render.com) (free tier, beginner-friendly), Railway, or Fly.io all work — you'd deploy `customer/app.py` and `seller/app.py` as two separate services. You'll need to create an account with whichever host you pick; that step only you can do.

3. **Point real domains/subdomains at each.** E.g. `localfork.com` → customer service, `sell.localfork.com` → seller service. Then set two environment variables so each app links to the other correctly:
   - Customer app: `SELLER_PORTAL_URL=https://sell.localfork.com`
   - Seller app: `CUSTOMER_SITE_URL=https://localfork.com`

4. **Logins stay independent, which is intentional.** Each app uses its own cookie name (`localfork_customer_session` / `localfork_seller_session`), so being logged into one site never logs you into the other, even on real subdomains — matching how most real customer-app/merchant-portal pairs work. If you'd rather have true single-sign-on between them later, that would mean switching both apps to the same cookie name plus `SESSION_COOKIE_DOMAIN=".localfork.com"`, but note it also brings back the "can't be two different people in one browser" limitation this setup was changed to avoid.

5. **Move off SQLite.** A single SQLite file is fine for testing but two separate deployed services hitting one file gets fragile fast. Use a hosted Postgres (Render, Railway, and Supabase all offer a free tier) — this is a change to `db.py` only, not to the app logic.

6. **Add real payments.** The natural fit is **Stripe Connect**, built for marketplaces where money needs to flow through to many different sellers. Each cook connects their own Stripe account for payouts. I can write the integration — creating the Stripe account and agreeing to its terms has to be done by you.

7. **Check food-selling regulations before real money changes hands.** Most US states have "cottage food laws" governing what home cooks can legally sell and whether they need a permit; this varies by state/country. Worth a quick search for your state's rules before treating this as a real business.

8. **Real reminder notifications.** Today "due soon" is a banner shown when someone happens to load the page. For an actual email/SMS/push reminder sent ~24h before pickup, you'd add a scheduler (e.g. a cron job or APScheduler) that periodically scans for orders in that window and sends through a provider like Postmark/SendGrid (email) or Twilio (SMS) — both require creating an account with that provider.

9. **Actually charge the late-cancellation fee.** Right now a late cancellation just flags the order (`late_cancellation = 1`) and shows the amount owed — no card is charged, since there's no payment processor connected yet. Once Stripe is wired up (step 6), this becomes a real charge against the card on file.

## Renaming

"LocalFork" appears in `customer/templates/base.html`, `seller/templates/base.html`, and this README. Change those and you're rebranded.
