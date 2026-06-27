from datetime import date

import app.services.update_service as svc
from app.utils import count_missed_trading_days


def test_friday_completion_is_healthy_on_monday():
    assert count_missed_trading_days(
        date(2026, 6, 19),
        today=date(2026, 6, 22),
    ) == 0


def test_friday_completion_is_overdue_on_tuesday():
    assert count_missed_trading_days(
        date(2026, 6, 19),
        today=date(2026, 6, 23),
    ) == 1


def _health(status, finished_at, *, today=date(2026, 6, 22)):
    return svc._compute_schedule_health(status, finished_at, today=today)


def test_schedule_health_never_run():
    result = _health(None, None)

    assert result["schedule_health_status"] == "never_run"
    assert result["schedule_is_overdue"] is False
    assert result["schedule_health_message"]


def test_schedule_health_running_takes_priority_over_missing_timestamp():
    result = _health("running", None)

    assert result["schedule_health_status"] == "running"
    assert result["schedule_is_overdue"] is False


def test_schedule_health_failed_takes_priority_over_old_timestamp():
    result = _health("failed", "2026-06-01T15:30:00")

    assert result["schedule_health_status"] == "failed"
    assert result["schedule_is_overdue"] is False


def test_schedule_health_terminal_status_requires_finished_timestamp():
    result = _health("success", None)

    assert result["schedule_health_status"] == "invalid_timestamp"
    assert result["schedule_is_overdue"] is False


def test_schedule_health_rejects_malformed_finished_timestamp():
    result = _health("success", "not-a-date")

    assert result["schedule_health_status"] == "invalid_timestamp"
    assert result["schedule_is_overdue"] is False


def test_schedule_health_friday_completion_is_healthy_on_monday():
    result = _health("success", "2026-06-19T15:35:00")

    assert result["schedule_health_status"] == "healthy"
    assert result["schedule_is_overdue"] is False


def test_schedule_health_friday_completion_is_overdue_on_tuesday():
    result = _health(
        "success",
        "2026-06-19T15:35:00",
        today=date(2026, 6, 23),
    )

    assert result["schedule_health_status"] == "overdue"
    assert result["schedule_is_overdue"] is True
    assert "1" in result["schedule_health_message"]
