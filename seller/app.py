import os
import sys
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db, init_db  # noqa: E402
from uploads import save_upload, delete_upload  # noqa: E402

app = Flask(__name__, static_folder="../static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB per upload

# Where the customer-facing site lives. In production this becomes something like
# https://localfork.com — set the CUSTOMER_SITE_URL env var to point there.
CUSTOMER_SITE_URL = os.environ.get("CUSTOMER_SITE_URL", "http://localhost:5050")

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
app.jinja_env.globals["CUSTOMER_SITE_URL"] = CUSTOMER_SITE_URL


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


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def seller_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Please log in first.")
            return redirect(url_for("login", next=request.path))
        if not g.seller:
            return redirect(url_for("become"))
        return view(*args, **kwargs)

    return wrapped


# ---------- Landing / auth ----------

@app.route("/")
def landing():
    if g.user and g.seller:
        return redirect(url_for("dashboard"))
    if g.user and not g.seller:
        return redirect(url_for("become"))
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    # Already have an account (maybe from the customer site, shared login)?
    # Just need to add a seller profile, not a whole new account.
    if g.user:
        return redirect(url_for("become"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        business_name = request.form.get("business_name", "").strip()
        city = request.form.get("city", "").strip()
        cuisine = request.form.get("cuisine", "").strip()
        bio = request.form.get("bio", "").strip()
        emoji = request.form.get("emoji", "🍽️").strip() or "🍽️"

        if not name or not email or len(password) < 6 or not business_name or not city:
            flash("Please fill in your name, email, password, business name, and city.")
            return render_template("signup.html", form=request.form)
        existing = g.db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists — log in instead.")
            return render_template("signup.html", form=request.form)

        photo_filename = save_upload(request.files.get("photo"))

        cur = g.db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
        )
        user_id = cur.lastrowid
        g.db.execute(
            "INSERT INTO seller_profiles (user_id, business_name, bio, cuisine, city, emoji, photo_filename) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, business_name, bio, cuisine, city, emoji, photo_filename),
        )
        g.db.commit()
        session["user_id"] = user_id
        flash(f"Welcome to LocalFork, {business_name}!")
        return redirect(url_for("dashboard"))
    return render_template("signup.html", form={})


@app.route("/become", methods=["GET", "POST"])
def become():
    """For someone who already has a LocalFork account (e.g. from the customer
    site, since login is shared) but doesn't have a seller profile yet."""
    if not g.user:
        flash("Please log in or sign up first.")
        return redirect(url_for("login"))
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
            return render_template("become.html", form=request.form)
        photo_filename = save_upload(request.files.get("photo"))
        g.db.execute(
            "INSERT INTO seller_profiles (user_id, business_name, bio, cuisine, city, emoji, photo_filename) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["id"], business_name, bio, cuisine, city, emoji, photo_filename),
        )
        g.db.commit()
        flash("Your seller page is live! Add some menu items to get started.")
        return redirect(url_for("dashboard"))
    return render_template("become.html", form={})


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
        seller = g.db.execute("SELECT id FROM seller_profiles WHERE user_id = ?", (user["id"],)).fetchone()
        if not seller:
            return redirect(url_for("become"))
        return redirect(request.args.get("next") or url_for("dashboard"))
    return render_template("login.html", email="")


@app.route("/account", methods=["GET", "POST"])
def account():
    if not g.user:
        flash("Please log in first.")
        return redirect(url_for("login", next=request.path))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name can't be empty.")
            return render_template("account.html")
        new_photo = save_upload(request.files.get("photo"))
        photo_filename = g.user["photo_filename"]
        if request.form.get("remove_photo") == "1":
            delete_upload(photo_filename)
            photo_filename = None
        if new_photo:
            delete_upload(photo_filename)
            photo_filename = new_photo
        g.db.execute(
            "UPDATE users SET name=?, photo_filename=? WHERE id=?", (name, photo_filename, g.user["id"])
        )
        g.db.commit()
        flash("Profile updated.")
        return redirect(url_for("account"))
    return render_template("account.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("login"))


@app.route("/business/edit", methods=["GET", "POST"])
@seller_required
def business_edit():
    if request.method == "POST":
        business_name = request.form.get("business_name", "").strip()
        city = request.form.get("city", "").strip()
        cuisine = request.form.get("cuisine", "").strip()
        bio = request.form.get("bio", "").strip()
        emoji = request.form.get("emoji", "🍽️").strip() or "🍽️"
        if not business_name or not city:
            flash("Business name and city are required.")
            return render_template("business_form.html", form=request.form)
        new_photo = save_upload(request.files.get("photo"))
        photo_filename = g.seller["photo_filename"]
        if request.form.get("remove_photo") == "1":
            delete_upload(photo_filename)
            photo_filename = None
        if new_photo:
            delete_upload(photo_filename)
            photo_filename = new_photo
        g.db.execute(
            "UPDATE seller_profiles SET business_name=?, city=?, cuisine=?, bio=?, emoji=?, photo_filename=? WHERE id=?",
            (business_name, city, cuisine, bio, emoji, photo_filename, g.seller["id"]),
        )
        g.db.commit()
        flash("Business page updated.")
        return redirect(url_for("dashboard"))
    return render_template("business_form.html", form=dict(g.seller))


# ---------- Dashboard ----------

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
    return render_template("dashboard.html", items=items, orders=orders, status_labels=STATUS_LABELS)


@app.route("/menu/new", methods=["GET", "POST"])
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
        photo_filename = save_upload(request.files.get("photo"))
        g.db.execute(
            "INSERT INTO menu_items (seller_id, name, description, price_cents, emoji, photo_filename) VALUES (?, ?, ?, ?, ?, ?)",
            (g.seller["id"], name, description, price_cents, emoji, photo_filename),
        )
        g.db.commit()
        flash(f"Added {name} to your menu.")
        return redirect(url_for("dashboard"))
    return render_template("menu_form.html", form={}, mode="new")


@app.route("/menu/<int:item_id>/edit", methods=["GET", "POST"])
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
        new_photo = save_upload(request.files.get("photo"))
        photo_filename = item["photo_filename"]
        if request.form.get("remove_photo") == "1":
            delete_upload(photo_filename)
            photo_filename = None
        if new_photo:
            delete_upload(photo_filename)
            photo_filename = new_photo
        g.db.execute(
            "UPDATE menu_items SET name=?, description=?, price_cents=?, emoji=?, photo_filename=? WHERE id=?",
            (name, description, price_cents, emoji, photo_filename, item_id),
        )
        g.db.commit()
        flash("Menu item updated.")
        return redirect(url_for("dashboard"))
    return render_template("menu_form.html", form=dict(item), mode="edit", item=item)


@app.route("/menu/<int:item_id>/toggle", methods=["POST"])
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


@app.route("/menu/<int:item_id>/delete", methods=["POST"])
@seller_required
def menu_delete(item_id):
    item = g.db.execute(
        "SELECT * FROM menu_items WHERE id = ? AND seller_id = ?", (item_id, g.seller["id"])
    ).fetchone()
    if item:
        delete_upload(item["photo_filename"])
    g.db.execute("DELETE FROM menu_items WHERE id = ? AND seller_id = ?", (item_id, g.seller["id"]))
    g.db.commit()
    flash("Menu item removed.")
    return redirect(url_for("dashboard"))


@app.route("/orders/<int:order_id>")
@seller_required
def order_detail(order_id):
    order = g.db.execute(
        """SELECT o.*, u.name AS buyer_name FROM orders o
           JOIN users u ON u.id = o.buyer_id WHERE o.id = ? AND o.seller_id = ?""",
        (order_id, g.seller["id"]),
    ).fetchone()
    if not order:
        abort(404)
    items = g.db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    return render_template(
        "order_detail.html", order=order, items=items, status_flow=STATUS_FLOW, status_labels=STATUS_LABELS
    )


@app.route("/orders/<int:order_id>/status", methods=["POST"])
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
    return redirect(url_for("order_detail", order_id=order_id))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5051)
