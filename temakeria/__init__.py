import io
from pathlib import Path

from flask import Flask, abort, redirect, render_template, send_file, send_from_directory, url_for

from .db import close_db, get_db

ROOT = Path(__file__).resolve().parent.parent


def create_app(database, *, admin_key=None, menu_url=None):
    app = Flask(__name__)
    app.config.update(DATABASE=database, MENU_URL=menu_url)
    app.teardown_appcontext(close_db)
    app.jinja_env.filters["brl"] = format_brl

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        if admin_key is not None:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; form-action 'self'"
        elif response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/assets/<path:filename>")
    def asset(filename):
        if not filename.endswith(".webp"):
            abort(404)
        return send_from_directory(ROOT / "assets", filename)

    if admin_key is not None:
        from .admin import admin

        app.config.update(
            SECRET_KEY=admin_key,
            TRUSTED_HOSTS=["127.0.0.1", "localhost"],
            SESSION_COOKIE_NAME="temakeria_admin",
            SESSION_COOKIE_SAMESITE="Strict",
            MAX_CONTENT_LENGTH=9 * 1024 * 1024,
            MAX_FORM_MEMORY_SIZE=128 * 1024,
            MAX_FORM_PARTS=20,
        )
        app.register_blueprint(admin)
        app.add_url_rule("/", endpoint="start", view_func=lambda: redirect(url_for("admin.dashboard")))
        return app

    @app.get("/")
    def start():
        return redirect(url_for("menu"))

    @app.get("/institucional")
    def institutional():
        return send_from_directory(ROOT, "index.html", max_age=0)

    @app.get("/cardapio")
    def menu():
        products = get_db().execute(
            """SELECT p.id, p.name, p.description, p.price_cents, p.price_from,
                      p.asset IS NOT NULL OR p.photo IS NOT NULL AS has_photo,
                      c.id AS category_id, c.name AS category_name
               FROM products p JOIN categories c ON c.id = p.category_id
               WHERE p.available = 1 AND c.visible = 1
               ORDER BY c.id, p.id"""
        )
        categories = {}
        for product in products:
            category = categories.setdefault(
                product["category_id"], {"name": product["category_name"], "products": []}
            )
            category["products"].append(product)
        return render_template("menu.html", categories=categories)

    @app.get("/cardapio/fotos/<int:product_id>")
    def menu_photo(product_id):
        return product_photo(product_id, public=True)

    return app


def product_photo(product_id, *, public):
    query = """SELECT p.asset, p.photo FROM products p
               JOIN categories c ON c.id = p.category_id WHERE p.id = ?"""
    if public:
        query += " AND p.available = 1 AND c.visible = 1"
    product = get_db().execute(query, (product_id,)).fetchone()
    if not product:
        abort(404)
    if product["photo"] is not None:
        response = send_file(io.BytesIO(product["photo"]), mimetype="image/webp")
    elif product["asset"]:
        response = send_from_directory(ROOT / "assets", product["asset"], max_age=0)
    else:
        abort(404)
    response.headers["Cache-Control"] = "no-cache"
    return response


def format_brl(cents):
    whole, fraction = divmod(cents, 100)
    return f"R$ {whole:,}".replace(",", ".") + f",{fraction:02d}"
