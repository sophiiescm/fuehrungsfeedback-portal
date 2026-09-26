from app.core.config import get_settings


def test_dev_personas_available_in_dev(client, seeded_users):
    p = client.get("/dev/personas").json()
    assert p and p[0]["title"].startswith("Admin")


def test_dev_endpoints_hidden_in_prod(client, seeded_users, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "prod")
    assert client.get("/dev/personas").status_code == 404
