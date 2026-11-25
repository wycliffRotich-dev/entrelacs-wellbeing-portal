"""A racing first save must converge on one draft instead of surfacing as a 500."""
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.services import CheckInService
from app.domain.check_ins.check_in import CheckIn
from app.infrastructure.persistence.repositories import PostgresRepository


class RacingRepository(PostgresRepository):
    """After the first draft lookup finds nothing, a rival request creates the draft."""

    def __init__(self, conn: Any, rival: Callable[[], None]) -> None:
        super().__init__(conn)
        self._rival = rival
        self._fired = False

    def find_draft(self, employee_id: UUID, *, for_update: bool = False) -> CheckIn | None:
        found = super().find_draft(employee_id, for_update=for_update)
        if not self._fired:
            self._fired = True
            self._rival()
        return found


def test_racing_first_saves_converge_on_one_draft(
    world: Any, connect: Callable[[], Any], now: datetime
) -> None:
    main_conn, rival_conn = connect(), connect()
    try:
        user = PostgresRepository(main_conn).get_user(world.user_id("e1"))
        assert user is not None
        main_conn.rollback()

        def rival_saves_first() -> None:
            CheckInService(PostgresRepository(rival_conn), lambda: now).save_draft(
                user, connectedness=3, support=None, workload=None
            )

        saved = CheckInService(RacingRepository(main_conn, rival_saves_first), lambda: now).save_draft(
            user, connectedness=None, support=7, workload=None
        )
    finally:
        main_conn.close()
        rival_conn.close()

    with connect() as conn:
        rows = conn.execute(
            "select connectedness, support, status from check_ins where employee_id = %s",
            (user.id,),
        ).fetchall()
    assert len(rows) == 1
    assert (rows[0]["connectedness"], rows[0]["support"], rows[0]["status"]) == (3, 7, "DRAFT")
    assert (saved.connectedness, saved.support) == (3, 7)
