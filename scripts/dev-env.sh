# Source me (". scripts/dev-env.sh") to point the backend at the compose Postgres. Paths only, no secrets.
_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DB_HOST=127.0.0.1 DB_PORT=5433 DB_NAME=wellbeing DB_USER=wellbeing
export DB_PASSWORD_FILE="$_root/secrets/postgres_password"
export JWT_SECRET_FILE="$_root/secrets/jwt_secret"
unset _root
