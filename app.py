import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

STATUS_FLOW = ["placed", "accepted", "ready", "completed"]
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


@app.before_request
def load_user():
    g.db = get_db()
    g.user = None
    g.seller = None
    user_id = session.get("user_id")
    if user_id:
        g.user = g.db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if g.user:
            g.seller = g.db.execute(
                "SELECT * FROM seller_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
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


def seller_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Please log in first.")
            return redirect(url_for("login", next=request.path))
        if not g.seller:
            flash("You need a seller page first.")
            return redirect(url_for("become_seller"))
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


# ---------- Become a seller ----------

@app.route("/sell", methods=["GET", "POST"])
@login_required
def become_seller():
    if g.seller:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()
        city = request.form.get("city", "").strip()
        cuisine = request.form.get("cuisine", "").strip()
        bio = request.form.get("bio", "").strip()
        emoji = request.form.get("emoji", "🍽️").strip() or "🍽️"
        if not business_name or not city:
            flash("Business name and city are required.")
            return render_template("become_seller.html", form=request.form)
        g.db.execute(
            "INSERT INTO seller_profiles (user_id, business_name, bio, cuisine, city, emoji) VALUES (?, ?, ?, ?, ?, ?)",
            (g.user["id"], business_name, bio, cuisine, city, emoji),
        )
        g.db.commit()
        flash("Your seller page is live! Add some menu items to get started.")
        return redirect(url_for("dashboard"))
    return render_template("become_seller.html", form={})


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
        """SELECT o.*, sp.business_name, sp.id AS seller_id, sp.user_id AS seller_user_id
           FROM orders o JOIN seller_profiles sp ON sp.id = o.seller_id WHERE o.id = ?""",
        (order_id,),
    ).fetchone()
    if not order:
        abort(404)
    if order["buyer_id"] != g.user["id"] and order["seller_user_id"] != g.user["id"]:
        abort(403)
    items = g.db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return render_template(
        "order_detail.html", order=order, items=items, status_flow=STATUS_FLOW, status_labels=STATUS_LABELS
    )


# ---------- Seller dashboard ----------

@app.route("/dashboard")
@seller_required
def dashboard():
    items = g.db.execute(
        "SELECT * FROM menu_items WHERE seller_id = ? ORDER BY created_at DESC", (g.seller["id"],)
    ).fetchall()
    orders = g.db.execute(
        """SELECT o.*, u.name AS buyer_name FROM orders o
           JOIN users u ON u.id = o.buyer_id
           WHERE o.seller_id = ? ORDER BY o.created_at DESC""",
        (g.seller["id"],),
    ).fetchall()
    return render_template(
        "dashboard.html", items=items, orders=orders, status_labels=STATUS_LABELS
    )


@app.route("/dashboard/menu/new", methods=["GET", "POST"])
@seller_required
def menu_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        emoji = request.form.get("emoji", "🍲").strip() or "🍲"
        try:
            price_cents = int(round(float(price) * 100))
        except ValueError:
            price_cents = -1
        if not name or price_cents <= 0:
            flash("Please provide a dish name and a valid price.")
            return render_template("menu_form.html", form=request.form, mode="new")
        g.db.execute(
            "INSERT INTO menu_items (seller_id, name, description, price_cents, emoji) VALUES (?, ?, ?, ?, ?)",
            (g.seller["id"], name, description, price_cents, emoji),
        )
        g.db.commit()
        flash(f"Added {name} to your menu.")
        return redirect(url_for("dashboard"))
    return render_template("menu_form.html", form={}, mode="new")


@app.route("/dashboard/menu/<int:item_id>/edit", methods=["GET", "POST"])
@seller_required
def menu_edit(item_id):
    item = g.db.execute(
        "SELECT * FROM menu_items WHERE id = ? AND seller_id = ?", (item_id, g.seller["id"])
    ).fetchone()
    if not item:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        emoji = request.form.get("emoji", "🍲").strip() or "🍲"
        try:
            price_cents = int(round(float(price) * 100))
        except ValueError:
            price_cents = -1
        if not name or price_cents <= 0:
            flash("Please provide a dish name and a valid price.")
            return render_template("menu_form.html", form=request.form, mode="edit", item=item)
        g.db.execute(
            "UPDATE menu_items SET name=?, description=?, price_cents=?, emoji=? WHERE id=?",
            (name, description, price_cents, emoji, item_id),
        )
        g.db.commit()
        flash("Menu item updated.")
        return redirect(url_for("dashboard"))
    return render_template("menu_form.html", form=dict(item), mode="edit", item=item)


@app.route("/dashboard/menu/<int:item_id>/toggle", methods=["POST"])
@seller_required
def menu_toggle(item_id):
    item = g.db.execute(
        "SELECT * FROM menu_items WHERE id = ? AND seller_id = ?", (item_id, g.seller["id"])
    ).fetchone()
    if not item:
        abort(404)
    g.db.execute(
        "UPDATE menu_items SET is_available = ? WHERE id = ?", (0 if item["is_available"] else 1, item_id)
    )
    g.db.commit()
    return redirect(url_for("dashboard"))


@app.route("/dashboard/menu/<int:item_id>/delete", methods=["POST"])
@seller_required
def menu_delete(item_id):
    g.db.execute("DELETE FROM menu_items WHERE id = ? AND seller_id = ?", (item_id, g.seller["id"]))
    g.db.commit()
    flash("Menu item removed.")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/orders/<int:order_id>/status", methods=["POST"])
@seller_required
def order_status(order_id):
    order = g.db.execute(
        "SELECT * FROM orders WHERE id = ? AND seller_id = ?", (order_id, g.seller["id"])
    ).fetchone()
    if not order:
        abort(404)
    new_status = request.form.get("status")
    if new_status not in STATUS_LABELS:
        abort(400)
    g.db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    g.db.commit()
    return redirect(request.referrer or url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
