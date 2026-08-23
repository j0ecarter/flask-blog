import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "blog.sqlite"), "SECRET_KEY": "test"})
    return app.test_client()


def register(client, name="Jo", email="jo@example.com", password="secret1"):
    return client.post("/register", data={"name": name, "email": email, "password": password}, follow_redirects=True)


def login(client, email="jo@example.com", password="secret1"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def test_register_login_and_logout(client):
    assert b"Log in" in register(client).data
    assert b"Hello, Jo" in login(client).data
    assert b"Log in" in client.post("/logout", follow_redirects=True).data


def test_short_password_is_rejected(client):
    response = register(client, password="short")
    assert b"at least six" in response.data


def test_post_create_edit_comment_and_delete(client):
    register(client)
    login(client)
    created = client.post("/posts/new", data={"title": "First note", "body": "A useful first post."}, follow_redirects=True)
    assert b"First note" in created.data
    edited = client.post("/posts/1/edit", data={"title": "Updated note", "body": "Changed body."}, follow_redirects=True)
    assert b"Updated note" in edited.data
    commented = client.post("/posts/1", data={"body": "Nice note"}, follow_redirects=True)
    assert b"Nice note" in commented.data
    deleted = client.post("/posts/1/delete", follow_redirects=True)
    assert b"No posts yet" in deleted.data


def test_another_user_cannot_edit_or_delete(client):
    register(client)
    login(client)
    client.post("/posts/new", data={"title": "Owned", "body": "By Jo"})
    client.post("/logout")
    register(client, name="Sam", email="sam@example.com")
    login(client, email="sam@example.com")
    assert client.get("/posts/1/edit").status_code == 403
    assert client.post("/posts/1/delete").status_code == 403


def test_missing_post_is_404(client):
    assert client.get("/posts/999").status_code == 404
