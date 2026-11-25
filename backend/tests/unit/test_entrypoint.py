from datetime import UTC, datetime

from app.entrypoint import build_app


def test_build_app_reads_settings_and_defaults_the_reporting_month(make_env):
    app = build_app(make_env())
    assert app.state.reporting_month_start == datetime(2026, 10, 1, tzinfo=UTC)
