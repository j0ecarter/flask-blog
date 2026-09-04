# Flask Blog

A small full-stack Flask blog with SQLite persistence, account registration, password hashing, login sessions, author-owned posts and reader comments.

![Flask blog home page](docs/homepage.jpg)

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BLOG_SECRET_KEY=choose-a-random-value
flask --app app run
```

Open `http://127.0.0.1:5000`. The local database is created automatically under `data/` and ignored by Git. Run tests with `pytest`.
