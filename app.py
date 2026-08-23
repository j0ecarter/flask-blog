import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    author_id INTEGER NOT NULL REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id)
);
"""


def get_db() -> sqlite3.Connection:
    # one connection for this request
    if "db" not in g:
        g.db = sqlite3.connect(g.app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    path = Path(g.app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("BLOG_SECRET_KEY", "development-only-key"),
        DATABASE=os.environ.get("BLOG_DATABASE", str(Path("data/blog.sqlite"))),
    )
    if test_config:
        app.config.update(test_config)

    @app.before_request
    def load_user() -> None:
        g.app = app
        user_id = session.get("user_id")
        g.user = None if user_id is None else get_db().execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()

    app.teardown_appcontext(close_db)

    @app.get("/")
    def index():
        posts = get_db().execute(
            "SELECT posts.*, users.name AS author_name FROM posts JOIN users ON users.id = posts.author_id ORDER BY posts.id DESC"
        ).fetchall()
        return render_template("index.html", posts=posts)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not name or not email or len(password) < 6:
                flash("Name, email and a password of at least six characters are required.")
            else:
                try:
                    db = get_db()
                    db.execute(
                        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)),
                    )
                    db.commit()
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    flash("That email is already registered.")
        return render_template("auth.html", title="Register", action="Create account", include_name=True)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Incorrect email or password.")
            else:
                session.clear()
                session["user_id"] = user["id"]
                return redirect(url_for("index"))
        return render_template("auth.html", title="Log in", action="Log in", include_name=False)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    @app.route("/posts/new", methods=["GET", "POST"])
    @login_required
    def new_post():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            body = request.form.get("body", "").strip()
            if not title or not body:
                flash("A title and body are required.")
            else:
                db = get_db()
                db.execute("INSERT INTO posts (title, body, author_id) VALUES (?, ?, ?)", (title, body, g.user["id"]))
                db.commit()
                return redirect(url_for("index"))
        return render_template("editor.html", title="New post", post=None)

    @app.route("/posts/<int:post_id>", methods=["GET", "POST"])
    def post_detail(post_id: int):
        post = get_db().execute(
            "SELECT posts.*, users.name AS author_name FROM posts JOIN users ON users.id = posts.author_id WHERE posts.id = ?",
            (post_id,),
        ).fetchone()
        if post is None:
            abort(404)
        if request.method == "POST":
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            body = request.form.get("body", "").strip()
            if not body:
                flash("A comment cannot be empty.")
            else:
                db = get_db()
                db.execute("INSERT INTO comments (body, post_id, author_id) VALUES (?, ?, ?)", (body, post_id, g.user["id"]))
                db.commit()
                return redirect(url_for("post_detail", post_id=post_id))
        comments = get_db().execute(
            "SELECT comments.*, users.name AS author_name FROM comments JOIN users ON users.id = comments.author_id WHERE post_id = ? ORDER BY comments.id",
            (post_id,),
        ).fetchall()
        return render_template("post.html", post=post, comments=comments)

    @app.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_post(post_id: int):
        post = get_db().execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if post is None:
            abort(404)
        if post["author_id"] != g.user["id"]:
            abort(403)
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            body = request.form.get("body", "").strip()
            if not title or not body:
                flash("A title and body are required.")
            else:
                db = get_db()
                db.execute("UPDATE posts SET title = ?, body = ? WHERE id = ?", (title, body, post_id))
                db.commit()
                return redirect(url_for("post_detail", post_id=post_id))
        return render_template("editor.html", title="Edit post", post=post)

    @app.post("/posts/<int:post_id>/delete")
    @login_required
    def delete_post(post_id: int):
        post = get_db().execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if post is None:
            abort(404)
        if post["author_id"] != g.user["id"]:
            abort(403)
        db = get_db()
        db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        db.commit()
        return redirect(url_for("index"))

    with app.app_context():
        g.app = app
        init_db()
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
