"""Populate LocalFork with a few sample cooks and dishes so the site isn't empty on first run."""
from werkzeug.security import generate_password_hash

from db import get_db, init_db

SELLERS = [
    {
        "name": "Maria Alvarez",
        "email": "maria@example.com",
        "business_name": "Maria's Kitchen",
        "bio": "Family recipes from Oaxaca, made fresh every morning.",
        "cuisine": "Homestyle Mexican",
        "city": "Austin",
        "address": "142 Cesar Chavez St, Austin, TX",
        "emoji": "🌮",
        "items": [
            ("Tamales (3-pack)", "Pork and salsa verde, wrapped in banana leaf.", 900, 20, "🫔"),
            ("Chicken Mole", "Slow-simmered mole negro over rice.", 1400, 15, "🍛"),
            ("Elote Cup", "Grilled corn, crema, cotija, chile lime.", 500, 8, "🌽"),
        ],
    },
    {
        "name": "Priya Nair",
        "email": "priya@example.com",
        "business_name": "Priya's Tiffin",
        "bio": "South Indian home cooking, tiffin-style.",
        "cuisine": "South Indian",
        "city": "Austin",
        "address": "88 Rainey St, Austin, TX",
        "emoji": "🍛",
        "items": [
            ("Masala Dosa", "Crispy dosa with spiced potato filling.", 850, 12, "🥞"),
            ("Chana Masala Bowl", "Chickpea curry with rice and pickle.", 1100, 18, "🍲"),
            ("Mango Lassi", "Fresh mango yogurt drink.", 450, 5, "🥭"),
        ],
    },
    {
        "name": "Sam Okafor",
        "email": "sam@example.com",
        "business_name": "Sam's Backyard BBQ",
        "bio": "Weekend smoker, weekday day job. Order ahead!",
        "cuisine": "BBQ",
        "city": "Round Rock",
        "address": "410 Oak Hollow Dr, Round Rock, TX",
        "emoji": "🍖",
        "items": [
            ("Brisket Plate", "Smoked 14 hours, with two sides.", 1600, 10, "🍖"),
            ("Pulled Pork Sandwich", "House slaw, pickles, brioche bun.", 1100, 6, "🥪"),
        ],
    },
]


def run():
    init_db()
    db = get_db()
    for s in SELLERS:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (s["email"],)).fetchone()
        if existing:
            continue
        cur = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (s["name"], s["email"], generate_password_hash("password123", method="pbkdf2:sha256")),
        )
        user_id = cur.lastrowid
        cur = db.execute(
            "INSERT INTO seller_profiles (user_id, business_name, bio, cuisine, city, address, emoji) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, s["business_name"], s["bio"], s["cuisine"], s["city"], s["address"], s["emoji"]),
        )
        seller_id = cur.lastrowid
        for name, desc, price_cents, prep_minutes, emoji in s["items"]:
            db.execute(
                "INSERT INTO menu_items (seller_id, name, description, price_cents, prep_minutes, emoji) VALUES (?, ?, ?, ?, ?, ?)",
                (seller_id, name, desc, price_cents, prep_minutes, emoji),
            )
        db.commit()
        print(f"Seeded {s['business_name']} (login: {s['email']} / password123)")
    db.close()


if __name__ == "__main__":
    run()
