# LocalFork

A marketplace where home cooks and small food businesses can list dishes and take orders — no storefront, no restaurant license required to get started. Think "Facebook Marketplace meets DoorDash," but for people who cook at home.

Working name only — rename anytime, it's just text in a few places (see "Renaming" below).

## What's built

- **Browse & search** — buyers see all cooks, or search by city/neighborhood
- **Seller pages** — each cook has a public page with their menu, prices, and bio
- **Cart & checkout** — buyers build a cart from one cook at a time and place an order (pickup or delivery)
- **Accounts** — signup/login for buyers; any account can also become a seller
- **Seller dashboard** — cooks add/edit/hide/delete menu items and manage incoming orders (placed → accepted → ready → completed)
- **Real shared data** — everything lives in one database, so what a seller lists is what every buyer sees, and orders placed by buyers show up for the seller live. This is a real multi-user app, not a personal demo.

Payment today is "pay the cook directly at pickup/delivery" — no card processing yet. See "Going live" below for adding real online payments.

## Running it on your computer

You need Python 3 (already installed on this Mac). From the `localfork` folder:

```bash
cd ~/localfork
python3 -m pip install -r requirements.txt
python3 app.py
```

Then open **http://localhost:5050** in your browser.

Sample accounts (already seeded — password is `password123` for all):
- `maria@example.com` — Maria's Kitchen (Mexican)
- `priya@example.com` — Priya's Tiffin (South Indian)
- `sam@example.com` — Sam's Backyard BBQ

Or sign up as a new buyer and place an order against one of them, then log in as that seller to see the order arrive in their dashboard.

To wipe and reseed the sample data at any point:
```bash
rm instance/localfork.db
python3 -c "from db import init_db; init_db()"
python3 seed.py
```

## Project layout

```
app.py           – routes / all the logic
db.py            – SQLite connection helper
schema.sql       – database tables
seed.py          – sample cooks & menu items
templates/       – HTML pages (Jinja2)
static/style.css – all styling
instance/        – the database file lives here (not in git)
```

## Going live (real public website)

Everything above runs only on this computer. To get a real public link real people can use, here's the path, roughly in order:

1. **Put the code on GitHub.** Most hosts deploy straight from a git repo.
   ```bash
   cd ~/localfork
   git init && git add . && git commit -m "Initial LocalFork app"
   ```
   Then create a repo on github.com and push to it.

2. **Pick a host and deploy.** [Render.com](https://render.com) has a free tier for small Flask apps and is beginner-friendly: connect your GitHub repo, tell it to run `python app.py`, done. Railway and Fly.io are similar alternatives. You'll need to create an account on whichever you choose — that's a step only you can do.

3. **Move off SQLite for real traffic.** SQLite (the current database) is a single file and works fine for testing, but a production app with multiple people using it at once should use a hosted Postgres database (Render, Railway, and Supabase all offer a free Postgres instance). This mainly means swapping `db.py` to connect to Postgres instead of a local file — the rest of the app's logic doesn't change.

4. **Add real payments.** The natural fit here is **Stripe Connect**, built specifically for marketplaces where money needs to flow through to many different sellers, not just one business owner. Each cook would connect their own Stripe account to receive payouts. This requires you (the platform owner) to create a Stripe account and enable Connect — I can write the integration code, but creating that account and agreeing to Stripe's terms has to be done by you.

5. **Get a domain** (e.g. from Namecheap or Google Domains) and point it at your host once step 2 is live.

6. **Check food-selling regulations before real money changes hands.** Most US states have "cottage food laws" governing what home cooks can legally sell, whether they need a permit, and what foods are restricted (this varies a lot by state/country). This isn't a coding step, but it matters before treating this as a real business — worth a quick search for your state's cottage food law before launching to the public.

## Renaming

The name "LocalFork" only appears in `templates/base.html` (site title/logo) and `README.md`. Change those two and you're rebranded.
