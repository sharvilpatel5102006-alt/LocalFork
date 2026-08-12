import os
import sys
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db, init_db  # noqa: E402

app = Flask(__name__, static_folder="../static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Where the seller portal lives. In production this becomes something like
# https://sell.localfork.com — set the SELLER_PORTAL_URL env var to point there.
SELLER_PORTAL_URL = os.environ.get("SELLER_PORTAL_URL", "http://localhost:5051")

STATUS_LABELS = {
    "placed": "Order placed",
    "accepted": "Accepted by cook",
    "ready": "Ready",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


def usd(cents):
    return f"${cents / 100:,.2f}"


app.jinja_env.filters["usd"] = usd
app.jinja_env.globals["SELLER_PORTAL_URL"] = SELLER_PORTAL_URL


@app.before_request
def load_user():
    g.db = get_db()
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = g.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    cart = session.get("cart")
    g.cart_count = sum(cart["items"].values()) if cart else 0


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Please log in first.")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


# ---------- Browse / home ----------

@app.route("/")
def home():
    city = request.args.get("city", "").strip()
    query = """
        SELECT sp.*, u.name AS owner_name,
               (SELECT COUNT(*) FROM menu_items mi WHERE mi.seller_id = sp.id AND mi.is_available = 1) AS item_count
        FROM seller_profiles sp
        JOIN users u ON u.id = sp.user_id
    """
    params = ()
    if city:
        query += " WHERE sp.city LIKE ?"
        params = (f"%{city}%",)
    query += " ORDER BY sp.created_at DESC"
    sellers = g.db.execute(query, params).fetchall()
    return render_template("home.html", sellers=sellers, city=city)


@app.route("/seller/<int:seller_id>")
def seller_public(seller_id):
    seller = g.db.execute(
        "SELECT sp.*, u.name AS owner_name FROM seller_profiles sp JOIN users u ON u.id = sp.user_id WHERE sp.id = ?",
        (seller_id,),
    ).fetchone()
    if not seller:
        abort(404)
    items = g.db.execute(
        "SELECT * FROM menu_items WHERE seller_id = ? AND is_available = 1 ORDER BY created_at",
        (seller_id,),
    ).fetchall()
    return render_template("seller_public.html", seller=seller, items=items)


# ---------- Auth ----------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Please fill in every field (password needs 6+ characters).")
            return render_template("signup.html", name=name, email=email)
        existing = g.db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists.")
            return render_template("signup.html", name=name, email=email)
        cur = g.db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
        )
        g.db.commit()
        session["user_id"] = cur.lastrowid
        flash(f"Welcome to LocalFork, {name}!")
        return redirect(url_for("home"))
    return render_template("signup.html", name="", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = g.db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.")
            return render_template("login.html", email=email)
        session["user_id"] = user["id"]
        flash(f"Welcome back, {user['name']}!")
        return redirect(request.args.get("next") or url_for("home"))
    return render_template("login.html", email="")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("home"))


# ---------- Cart ----------

def get_cart():
    return session.get("cart") or {"seller_id": None, "items": {}}


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


@app.route("/cart/add/<int:seller_id>/<int:item_id>", methods=["POST"])
def cart_add(seller_id, item_id):
    item = g.db.execute(
        "SELECT * FROM menu_items WHERE id = ? AND seller_id = ? AND is_available = 1",
        (item_id, seller_id),
    ).fetchone()
    if not item:
        abort(404)
    cart = get_cart()
    if cart["seller_id"] is not None and cart["seller_id"] != seller_id:
        flash("Your cart had items from another cook, so we started a fresh cart for this one.")
        cart = {"seller_id": seller_id, "items": {}}
    cart["seller_id"] = seller_id
    key = str(item_id)
    cart["items"][key] = cart["items"].get(key, 0) + 1
    save_cart(cart)
    flash(f"Added {item['name']} to your cart.")
    return redirect(url_for("seller_public", seller_id=seller_id))


@app.route("/cart")
def cart_view():
    cart = get_cart()
    lines = []
    total = 0
    if cart["items"]:
        ids = list(cart["items"].keys())
        placeholders = ",".join("?" * len(ids))
        rows = g.db.execute(
            f"SELECT * FROM menu_items WHERE id IN ({placeholders})", ids
        ).fetchall()
        rows_by_id = {str(r["id"]): r for r in rows}
        for item_id, qty in cart["items"].items():
            row = rows_by_id.get(item_id)
            if not row:
                continue
            subtotal = row["price_cents"] * qty
            total += subtotal
            lines.append({"item": row, "qty": qty, "subtotal": subtotal})
    seller = None
    if cart["seller_id"]:
        seller = g.db.execute(
            "SELECT * FROM seller_profiles WHERE id = ?", (cart["seller_id"],)
        ).fetchone()
    return render_template("cart.html", lines=lines, total=total, seller=seller)


@app.route("/cart/update/<int:item_id>", methods=["POST"])
def cart_update(item_id):
    cart = get_cart()
    key = str(item_id)
    qty = max(0, int(request.form.get("qty", 0)))
    if qty == 0:
        cart["items"].pop(key, None)
    else:
        cart["items"][key] = qty
    if not cart["items"]:
        cart = {"seller_id": None, "items": {}}
    save_cart(cart)
    return redirect(url_for("cart_view"))


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    save_cart({"seller_id": None, "items": {}})
    return redirect(url_for("home"))


# ---------- Checkout ----------

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = get_cart()
    if not cart["items"]:
        flash("Your cart is empty.")
        return redirect(url_for("home"))

    ids = list(cart["items"].keys())
    placeholders = ",".join("?" * len(ids))
    rows = g.db.execute(f"SELECT * FROM menu_items WHERE id IN ({placeholders})", ids).fetchall()
    rows_by_id = {str(r["id"]): r for r in rows}
    total = sum(rows_by_id[i]["price_cents"] * q for i, q in cart["items"].items() if i in rows_by_id)

    if request.method == "POST":
        fulfillment = request.form.get("fulfillment", "pickup")
        notes = request.form.get("notes", "").strip()
        cur = g.db.execute(
            "INSERT INTO orders (buyer_id, seller_id, status, fulfillment, notes, total_cents) VALUES (?, ?, 'placed', ?, ?, ?)",
            (g.user["id"], cart["seller_id"], fulfillment, notes, total),
        )
        order_id = cur.lastrowid
        for item_id, qty in cart["items"].items():
            row = rows_by_id.get(item_id)
            if not row:
                continue
            g.db.execute(
                "INSERT INTO order_items (order_id, menu_item_id, name, price_cents, qty) VALUES (?, ?, ?, ?, ?)",
                (order_id, row["id"], row["name"], row["price_cents"], qty),
            )
        g.db.commit()
        save_cart({"seller_id": None, "items": {}})
        flash("Order placed! The cook has been notified.")
        return redirect(url_for("order_detail", order_id=order_id))

    seller = g.db.execute("SELECT * FROM seller_profiles WHERE id = ?", (cart["seller_id"],)).fetchone()
    return render_template("checkout.html", total=total, seller=seller)


@app.route("/orders")
@login_required
def my_orders():
    orders = g.db.execute(
        """SELECT o.*, sp.business_name FROM orders o
           JOIN seller_profiles sp ON sp.id = o.seller_id
           WHERE o.buyer_id = ? ORDER BY o.created_at DESC""",
        (g.user["id"],),
    ).fetchall()
    return render_template("orders.html", orders=orders, status_labels=STATUS_LABELS)


@app.route("/order/<int:order_id>")
@login_required
def order_detail(order_id):
    order = g.db.execute(
        """SELECT o.*, sp.business_name FROM orders o
           JOIN seller_profiles sp ON sp.id = o.seller_id WHERE o.id = ?""",
        (order_id,),
    ).fetchone()
    if not order:
        abort(404)
    if order["buyer_id"] != g.user["id"]:
        abort(403)
    items = g.db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return render_template("order_detail.html", order=order, items=items, status_labels=STATUS_LABELS)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
