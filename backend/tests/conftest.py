import pytest


@pytest.fixture
def make_env(tmp_path):
    def _make_env(**overrides):
        pw = tmp_path / "db_pw"
        pw.write_text("db-secret-value\n")
        jwt = tmp_path / "jwt"
        jwt.write_text("j" * 64 + "\n")
        env = {
            "DB_HOST": "db",
            "DB_PORT": "5432",
            "DB_NAME": "wellbeing",
            "DB_USER": "wellbeing",
            "DB_PASSWORD_FILE": str(pw),
            "JWT_SECRET_FILE": str(jwt),
        }
        env.update(overrides)
        return env

    return _make_env
