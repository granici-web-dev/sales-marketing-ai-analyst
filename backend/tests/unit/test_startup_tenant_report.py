"""Отчёт о непривязанных клиентах при запуске.

Непривязанный арендатор — это клиент, которого движок пустит, а аналитик не
найдёт: человек получит отказ без объяснения. Пока о привязке напоминал только
комментарий в исходниках, узнать о ней было неоткуда.

Проверяется здесь и то, что отчёт произносится, и то, что он не мешает
приложению подняться: это сведения о состоянии, а не условие работы. Молчать
о собственном отказе он при этом не вправе — иначе «непривязанных нет» будет
означать сразу две разные вещи.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.main import _report_unlinked_tenants


class _FakeEngine:
    """Движок, отдающий одно соединение и запоминающий, что его закрыли."""

    def __init__(self, conn: object | None = None, fail: Exception | None = None) -> None:
        self._conn = conn
        self._fail = fail
        self.disposed = False

    def connect(self):
        if self._fail is not None:
            raise self._fail
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=self._conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    async def dispose(self) -> None:
        self.disposed = True


def _rows(n: int) -> list[object]:
    return [object()] * n


@pytest.mark.asyncio
async def test_unlinked_tenants_are_reported_with_the_command_to_fix_them() -> None:
    engine = _FakeEngine(conn=object())
    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=engine),
        patch("app.services.tenants.directory.count_unlinked", AsyncMock(return_value=2)),
        patch("app.services.tenants.directory.list_all", AsyncMock(return_value=_rows(5))),
        patch("app.main.logger") as log,
    ):
        await _report_unlinked_tenants()

    log.warning.assert_called_once()
    _, kwargs = log.warning.call_args
    assert kwargs["unlinked"] == 2
    assert kwargs["total"] == 5
    assert "app.cli tenants link" in kwargs["hint"], (
        "предупреждение обязано называть команду: сообщение без выхода "
        "заставляет искать его в исходниках, что и было исходной бедой"
    )
    assert engine.disposed


@pytest.mark.asyncio
async def test_all_linked_is_said_out_loud_too() -> None:
    """Тишина означала бы «всё в порядке» и «проверка не выполнялась» разом."""
    engine = _FakeEngine(conn=object())
    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=engine),
        patch("app.services.tenants.directory.count_unlinked", AsyncMock(return_value=0)),
        patch("app.services.tenants.directory.list_all", AsyncMock(return_value=_rows(3))),
        patch("app.main.logger") as log,
    ):
        await _report_unlinked_tenants()

    log.warning.assert_not_called()
    log.info.assert_called_once()
    assert log.info.call_args.kwargs["total"] == 3


@pytest.mark.asyncio
async def test_a_dead_database_does_not_stop_startup_and_is_not_swallowed() -> None:
    engine = _FakeEngine(fail=OSError("connection refused"))
    with (
        patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=engine),
        patch("app.main.logger") as log,
    ):
        await _report_unlinked_tenants()  # не должно бросить

    log.exception.assert_called_once()
    log.info.assert_not_called()
    log.warning.assert_not_called()
    assert engine.disposed, "движок обязан закрыться и на пути отказа"
