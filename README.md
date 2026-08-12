# LocalFork

A marketplace where home cooks and small food businesses can list dishes and take orders — no storefront, no restaurant license required to get started. Think "Facebook Marketplace meets DoorDash," but for people who cook at home.

Working name only — rename anytime, it's just text in a couple of files (see "Renaming" below).

## Two sites, one database

This is built as **two separate websites that share one database**, the same way DoorDash's customer app and its merchant portal are two different products backed by the same orders:

- **`customer/`** — the public site. Browse cooks, view menus, cart, checkout, track orders.
- **`seller/`** — the seller portal. A different look (dark header, "LocalFork for Cooks" branding), separate signup flow, menu management, and incoming-order management.

They're separate Flask apps, on separate ports, with separate templates — but both read/write the same `instance/localfork.db`, so a dish added in the seller portal appears on the customer site instantly, and an order placed on the customer site appears in the seller portal instantly. In production these become two subdomains (e.g. `localfork.com` and `sell.localfork.com`) pointed at the same database — nothing about the app logic needs to change for that.

**Login is shared between the two sites** (same session cookie, same user table). If someone already has a buyer account and visits the seller portal, they're prompted to add a business profile to their existing account rather than creating a whole new one — again, exactly like Airbnb host/guest or Uber rider/driver sharing one identity.

## What's built

**Customer site:**
- Browse & search cooks by city
- Public seller pages with menu, prices, bio
- Cart with +/- quantity steppers, checkout (pickup or delivery)
- Buyer signup/login and order history/tracking

**Seller portal:**
- Dedicated signup (creates account + business profile together) or "add a seller profile" for an existing account
- Dashboard: add/edit/hide/delete menu items
- Incoming orders with status updates (placed → accepted → ready → completed)

Payment today is "pay the cook directly at pickup/delivery" — no card processing yet. See "Going live" below.

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
instance/                    – the database file lives here (not in git)
```

## Going live (real public websites)

Everything above runs only on this computer. To get real public links, roughly in order:

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

4. **Share login across the two subdomains.** Right now the shared-cookie trick works because both apps run on `localhost` (browsers ignore port when matching cookies). Once these are on real subdomains, set `SESSION_COOKIE_DOMAIN=".localfork.com"` (both apps, same `SECRET_KEY`) so the login cookie is valid on both `localfork.com` and `sell.localfork.com`.

5. **Move off SQLite.** A single SQLite file is fine for testing but two separate deployed services hitting one file gets fragile fast. Use a hosted Postgres (Render, Railway, and Supabase all offer a free tier) — this is a change to `db.py` only, not to the app logic.

6. **Add real payments.** The natural fit is **Stripe Connect**, built for marketplaces where money needs to flow through to many different sellers. Each cook connects their own Stripe account for payouts. I can write the integration — creating the Stripe account and agreeing to its terms has to be done by you.

7. **Check food-selling regulations before real money changes hands.** Most US states have "cottage food laws" governing what home cooks can legally sell and whether they need a permit; this varies by state/country. Worth a quick search for your state's rules before treating this as a real business.

## Renaming

"LocalFork" appears in `customer/templates/base.html`, `seller/templates/base.html`, and this README. Change those and you're rebranded.
