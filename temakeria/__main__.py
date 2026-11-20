import argparse
import getpass
import os
import secrets
from contextlib import closing
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from waitress import create_server
from werkzeug.security import generate_password_hash

from . import ROOT, create_app
from .db import connect, initialize


def menu_address(value):
    try:
        parts = urlsplit(value)
        valid = (
            parts.scheme in {"http", "https"} and parts.hostname
            and parts.hostname not in {"127.0.0.1", "::1", "localhost", "0.0.0.0", "::"}
            and parts.username is None and parts.password is None
            and parts.path in {"", "/", "/cardapio", "/cardapio/"}
            and not parts.query and not parts.fragment
            and not any(char.isspace() for char in value)
        )
        if valid:
            parts.port  # Validate an explicitly supplied port.
            return f"{parts.scheme}://{parts.netloc}/cardapio"
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("informe uma URL HTTP(S) acessível pelo celular")


def main():
    parser = argparse.ArgumentParser(description="Cardápio local da Temakeria")
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "temakeria.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-admin", help="Define ou troca a senha do painel")
    serve = commands.add_parser("serve", help="Inicia o cardápio e o painel")
    serve.add_argument("--public-host", default="0.0.0.0")
    serve.add_argument("--public-port", type=int, default=8080)
    serve.add_argument("--admin-port", type=int, default=8081)
    serve.add_argument("--menu-url", type=menu_address, default=os.environ.get("TEMAKERIA_MENU_URL"))
    args = parser.parse_args()

    initialize(args.database)
    if args.command == "init-admin":
        password = getpass.getpass("Senha do painel (mínimo de 12 caracteres): ")
        if len(password) < 12 or len(password) > 128:
            parser.error("a senha deve ter entre 12 e 128 caracteres")
        if password != getpass.getpass("Repita a senha: "):
            parser.error("as senhas são diferentes")
        with closing(connect(args.database)) as db, db:
            db.execute(
                """INSERT INTO administrator (id, password_hash, session_key) VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET password_hash = excluded.password_hash,
                   session_key = excluded.session_key""",
                (generate_password_hash(password), secrets.token_hex(32)),
            )
        print("Senha configurada. Reinicie o servidor se ele estiver em execução.")
        return

    with closing(connect(args.database)) as db:
        credentials = db.execute("SELECT session_key FROM administrator WHERE id = 1").fetchone()
    if credentials is None:
        parser.error("configure a senha primeiro com python -m temakeria init-admin")

    public = create_server(
        create_app(args.database), host=args.public_host, port=args.public_port,
        max_request_body_size=64 * 1024,
    )
    admin = create_server(
        create_app(args.database, admin_key=credentials["session_key"], menu_url=args.menu_url),
        host="127.0.0.1", port=args.admin_port, max_request_body_size=9 * 1024 * 1024,
    )
    browser_host = "127.0.0.1" if args.public_host == "0.0.0.0" else args.public_host
    if ":" in browser_host:
        browser_host = f"[{browser_host}]"
    menu_url = args.menu_url or f"http://{browser_host}:{args.public_port}/cardapio"
    print(f"Cardápio: {menu_url}")
    print(f"Painel:   http://127.0.0.1:{args.admin_port}/admin", flush=True)
    Thread(target=admin.run, daemon=True).start()
    try:
        public.run()
    finally:
        admin.close()
        public.close()


if __name__ == "__main__":
    main()
