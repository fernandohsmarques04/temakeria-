import hmac
import io
import os
import re
import secrets
import sqlite3
from functools import wraps

import qrcode
from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request, send_file,
    session, url_for,
)
from PIL import Image, ImageOps
from werkzeug.security import check_password_hash

from . import product_photo
from .db import get_db

admin = Blueprint("admin", __name__, url_prefix="/admin")
PRICE_PATTERN = re.compile(r"([0-9]{1,7})(?:[,.]([0-9]{1,2}))?")


@admin.before_request
def verify_form_token():
    if request.method == "POST":
        expected = session.get("csrf", "")
        supplied = request.form.get("csrf", "")
        if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
            abort(400)


@admin.app_context_processor
def form_helpers():
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    return {"csrf_token": csrf_token}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped


@admin.route("/entrar", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        credentials = get_db().execute("SELECT password_hash FROM administrator WHERE id = 1").fetchone()
        password = request.form.get("password", "")
        if credentials and len(password) <= 128 and check_password_hash(credentials["password_hash"], password):
            session.clear()
            session["authenticated"] = True
            return redirect(url_for("admin.dashboard"), code=303)
        return render_template("login.html", error="Senha incorreta."), 401
    return render_template("login.html")


@admin.post("/sair")
@login_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"), code=303)


@admin.get("")
@login_required
def dashboard():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY id").fetchall()
    products = db.execute(
        """SELECT p.id, p.name, p.price_cents, p.price_from, p.available,
                  p.asset IS NOT NULL OR p.photo IS NOT NULL AS has_photo, c.name AS category,
                  c.visible AS category_visible
           FROM products p JOIN categories c ON c.id = p.category_id
           ORDER BY c.id, p.id"""
    ).fetchall()
    return render_template("dashboard.html", categories=categories, products=products)


@admin.route("/categorias/nova", methods=["GET", "POST"])
@admin.route("/categorias/<int:category_id>", methods=["GET", "POST"])
@login_required
def edit_category(category_id=None):
    db = get_db()
    category = {"name": "", "visible": True}
    if category_id is not None:
        row = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if row is None:
            abort(404)
        category = dict(row)

    error = None
    if request.method == "POST":
        category.update(name=request.form.get("name", "").strip(), visible="visible" in request.form)
        values = category["name"], category["visible"]
        if not 1 <= len(category["name"]) <= 80:
            error = "Informe um nome de categoria com até 80 caracteres."
        else:
            try:
                with db:
                    if category_id is None:
                        db.execute("INSERT INTO categories (name, visible) VALUES (?, ?)", values)
                    else:
                        db.execute("UPDATE categories SET name = ?, visible = ? WHERE id = ?", (*values, category_id))
            except sqlite3.IntegrityError:
                error = "Já existe uma categoria com esse nome."
            else:
                flash("Categoria salva.")
                return redirect(url_for("admin.dashboard"), code=303)
    return render_template("category.html", category=category, category_id=category_id, error=error), 400 if error else 200


def parse_price(value):
    if not value:
        return None
    match = PRICE_PATTERN.fullmatch(value)
    if not match:
        raise ValueError("Informe o preço sem separador de milhar, como 29,90.")
    whole, fraction = match.groups()
    return 100 * int(whole) + int((fraction or "").ljust(2, "0"))


def read_photo(upload):
    if upload.stream.seek(0, os.SEEK_END) > 8 * 1024 * 1024:
        raise ValueError("A foto deve ter até 8 MB.")
    upload.stream.seek(0)
    try:
        with Image.open(upload.stream, formats=["JPEG", "PNG", "WEBP"]) as source:
            if source.width * source.height > 24_000_000:
                raise ValueError("A foto deve ter até 24 megapixels.")
            photo = ImageOps.exif_transpose(source)
            photo.thumbnail((1600, 1600))
            has_alpha = "A" in photo.getbands() or "transparency" in photo.info
            output = io.BytesIO()
            photo.convert("RGBA" if has_alpha else "RGB").save(output, format="WEBP", quality=84)
            return output.getvalue()
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("Envie uma foto válida em JPEG, PNG ou WebP.") from error


@admin.route("/produtos/novo", methods=["GET", "POST"])
@admin.route("/produtos/<int:product_id>", methods=["GET", "POST"])
@login_required
def edit_product(product_id=None):
    db = get_db()
    categories = db.execute("SELECT id, name FROM categories ORDER BY id").fetchall()
    product = {
        "category_id": None, "name": "", "description": "", "price": "", "price_from": False,
        "available": False, "has_photo": False,
    }
    if product_id is not None:
        row = db.execute(
            """SELECT id, category_id, name, description, price_cents, price_from, available,
                      asset IS NOT NULL OR photo IS NOT NULL AS has_photo
               FROM products WHERE id = ?""", (product_id,)
        ).fetchone()
        if row is None:
            abort(404)
        product.update(dict(row))
        if row["price_cents"] is not None:
            whole, fraction = divmod(row["price_cents"], 100)
            product["price"] = f"{whole},{fraction:02d}"

    error = None
    if request.method == "POST":
        form = request.form
        category_id = next((item["id"] for item in categories if str(item["id"]) == form.get("category_id")), None)
        product.update(
            category_id=category_id,
            name=form.get("name", "").strip(),
            description=form.get("description", "").strip(),
            price=form.get("price", "").strip(),
            price_from="price_from" in form,
            available="available" in form,
        )
        try:
            if category_id is None:
                raise ValueError("Selecione uma categoria existente.")
            if not 1 <= len(product["name"]) <= 120 or len(product["description"]) > 600:
                raise ValueError("Informe um nome de até 120 caracteres e uma descrição de até 600.")
            price_cents = parse_price(product["price"])
            if price_cents is None and product["available"]:
                raise ValueError("Informe um preço antes de publicar o produto.")
            upload = request.files.get("photo")
            new_photo = read_photo(upload) if upload and upload.filename else None
        except ValueError as invalid:
            error = str(invalid)
        else:
            values = (
                category_id, product["name"], product["description"], price_cents,
                product["price_from"] and price_cents is not None, product["available"],
            )
            with db:
                if product_id is None:
                    db.execute(
                        """INSERT INTO products
                           (category_id, name, description, price_cents, price_from, available, photo)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""", (*values, new_photo),
                    )
                else:
                    db.execute(
                        """UPDATE products SET category_id = ?, name = ?, description = ?,
                           price_cents = ?, price_from = ?, available = ? WHERE id = ?""",
                        (*values, product_id),
                    )
                    if new_photo is not None or "remove_photo" in form:
                        db.execute("UPDATE products SET asset = NULL, photo = ? WHERE id = ?", (new_photo, product_id))
            flash("Produto salvo.")
            return redirect(url_for("admin.dashboard"), code=303)
    return render_template(
        "product.html", product=product, product_id=product_id, categories=categories, error=error
    ), 400 if error else 200


@admin.get("/produtos/<int:product_id>/foto")
@login_required
def photo(product_id):
    return product_photo(product_id, public=False)


@admin.get("/qr.png")
@login_required
def qr():
    address = current_app.config["MENU_URL"]
    if not address:
        abort(404)
    image = qrcode.make(address, box_size=10, border=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", download_name="temakeria-cardapio.png")


@admin.app_errorhandler(413)
def photo_too_large(error):
    return render_template(
        "error.html", title="Envio muito grande", message="Volte ao formulário e escolha uma foto de até 8 MB."
    ), 413
