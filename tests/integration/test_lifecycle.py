import pytest

from app.application.dto import CreateRequestInput
from app.application.use_cases import (
    cancel_request,
    confirm_full_received,
    confirm_partial_received,
    create_request,
    mark_purchased,
    mark_shipped,
    pause_resume_request,
    pdo_process_excel,
    return_to_pdo,
    take_request,
)
from app.domain.enums import EventType, Role, StageCode
from app.infrastructure.db.sqlite import Database
from app.infrastructure.repositories.request_repository import RequestRepository


async def test_ig24_full_lifecycle(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    await db.migrate()
    repo = RequestRepository(db)

    req = await create_request.execute(
        repo,
        CreateRequestInput(
            chat_id=1,
            foreman_user_id=10,
            object_name="Игора",
            description="Сетка рабица 2000 м",
            requested_qty=2000,
            unit="м",
            subobject_name="Забор",
        ),
    )
    req = await take_request.take_by_pdo(repo, req["id"], actor_user_id=20)
    rows = [
        {
            "subobject_name": "Забор",
            "name_from_foreman": "Сетка рабица",
            "nomenclature_1c": "Сетка рабица 23а/22",
            "code_1c": "001",
            "requested_qty": 2000.0,
            "unit": "м",
            "from_stock_qty": 250.0,
            "to_purchase_qty": 1750.0,
            "need_by": "2026-03-01",
        }
    ]
    items = await pdo_process_excel.execute(repo, req, rows, actor_user_id=20)
    req = items[0]
    req = await take_request.take_by_procurement(repo, req["id"], actor_user_id=30)
    req = await mark_purchased.execute(repo, req["id"], actor_user_id=30, eta_shipping="2026-02-22")
    req = await mark_shipped.execute(repo, req["id"], actor_user_id=30, eta_arrival="2026-02-24")
    req = await confirm_partial_received.execute(repo, req["id"], actor_user_id=10, delta_qty=1500)
    req = await confirm_full_received.execute(repo, req["id"], actor_user_id=10)

    assert req["stage_code"] == StageCode.FULLY_RECEIVED.value
    assert req["remaining_qty"] == 0.0


async def test_ig27_container_split(tmp_path) -> None:
    db = Database(str(tmp_path / "test2.db"))
    await db.migrate()
    repo = RequestRepository(db)
    parent = await create_request.execute(
        repo,
        CreateRequestInput(chat_id=1, foreman_user_id=10, object_name="Игора", description="Excel", requested_qty=0, unit="шт"),
    )
    rows = [
        {
            "subobject_name": "Фундамент",
            "name_from_foreman": "Доска",
            "nomenclature_1c": "Доска 25x100x6000",
            "code_1c": "A1",
            "requested_qty": 1000.0,
            "unit": "шт",
            "from_stock_qty": 300.0,
            "to_purchase_qty": 700.0,
            "need_by": "2026-02-20",
        },
        {
            "subobject_name": "Фундамент",
            "name_from_foreman": "Саморез",
            "nomenclature_1c": "Саморез 5x70",
            "code_1c": "A2",
            "requested_qty": 50.0,
            "unit": "шт",
            "from_stock_qty": 50.0,
            "to_purchase_qty": 0.0,
            "need_by": "2026-02-20",
        },
    ]
    children = await pdo_process_excel.execute(repo, parent, rows, actor_user_id=20)
    assert len(children) == 2
    assert children[0]["request_code"].endswith("-1")
    assert children[1]["request_code"].endswith("-2")


async def test_paused_request_blocks_non_manager_actions(tmp_path) -> None:
    db = Database(str(tmp_path / "test3.db"))
    await db.migrate()
    repo = RequestRepository(db)
    req = await create_request.execute(
        repo,
        CreateRequestInput(
            chat_id=1,
            foreman_user_id=10,
            object_name="Игора",
            description="Блок паузы",
            requested_qty=100,
            unit="шт",
        ),
    )
    paused = await pause_resume_request.pause(repo, req["id"], actor_user_id=99, reason="Проверка")
    assert paused is not None

    with pytest.raises(ValueError, match="на паузе"):
        await take_request.take_by_pdo(repo, req["id"], actor_user_id=20)
    with pytest.raises(ValueError, match="на паузе"):
        await cancel_request.execute(
            requests=repo,
            request_id=req["id"],
            actor_user_id=10,
            actor_role=Role.FOREMAN,
            reason="Нельзя",
        )


async def test_return_to_pdo_event_is_logged(tmp_path) -> None:
    db = Database(str(tmp_path / "test4.db"))
    await db.migrate()
    repo = RequestRepository(db)
    req = await create_request.execute(
        repo,
        CreateRequestInput(
            chat_id=1,
            foreman_user_id=10,
            object_name="Игора",
            description="Возврат ПДО",
            requested_qty=10,
            unit="шт",
        ),
    )
    await take_request.take_by_pdo(repo, req["id"], actor_user_id=20)
    req = await pdo_process_excel.execute(
        repo,
        req,
        [
            {
                "subobject_name": "Фундамент",
                "name_from_foreman": "Тест",
                "nomenclature_1c": "Тест 1С",
                "code_1c": "R1",
                "requested_qty": 10.0,
                "unit": "шт",
                "from_stock_qty": 0.0,
                "to_purchase_qty": 10.0,
                "need_by": "2026-03-01",
            }
        ],
        actor_user_id=20,
    )
    req = await take_request.take_by_procurement(repo, req[0]["id"], actor_user_id=30)
    req = await return_to_pdo.execute(repo, req["id"], actor_user_id=30)
    assert req is not None
    assert req["stage_code"] == StageCode.PDO_PROCESSING.value

    events = await repo.get_events(req["id"])
    assert events[-1]["event_type"] == EventType.RETURNED_TO_PDO.value


async def test_latest_message_link_selection(tmp_path) -> None:
    db = Database(str(tmp_path / "test5.db"))
    await db.migrate()
    repo = RequestRepository(db)
    req = await create_request.execute(
        repo,
        CreateRequestInput(
            chat_id=1,
            foreman_user_id=10,
            object_name="Игора",
            description="Линки сообщений",
            requested_qty=5,
            unit="шт",
        ),
    )
    event_1 = await repo.append_event(
        request_id=req["id"],
        event_type=EventType.MANAGER_COMMENTED,
        actor_user_id=99,
        actor_role=Role.MANAGER,
        payload={"comment": "a"},
    )
    await repo.add_message_link(req["id"], event_1, chat_id=1, message_id=100)
    event_2 = await repo.append_event(
        request_id=req["id"],
        event_type=EventType.MANAGER_COMMENTED,
        actor_user_id=99,
        actor_role=Role.MANAGER,
        payload={"comment": "b"},
    )
    await repo.add_message_link(req["id"], event_2, chat_id=1, message_id=101)

    latest = await repo.get_latest_message_id(req["id"], chat_id=1)
    assert latest == 101


async def test_foreman_attachments_saved_and_visible_in_history(tmp_path) -> None:
    db = Database(str(tmp_path / "test5.db"))
    await db.migrate()
    repo = RequestRepository(db)

    req = await create_request.execute(
        repo,
        CreateRequestInput(
            chat_id=1,
            foreman_user_id=10,
            object_name="Игора",
            description="Фото и голос",
            requested_qty=1,
            unit="шт",
            attachments=[
                {"file_id": "photo_1", "file_unique_id": "uphoto_1", "attachment_type": "photo"},
                {"file_id": "voice_1", "file_unique_id": "uvoice_1", "attachment_type": "voice"},
            ],
        ),
    )

    attachments = await repo.list_attachments(req["id"])
    assert len(attachments) == 2

    summary = await repo.get_attachment_summary(req["id"])
    assert summary["total"] == 2
    assert summary["by_type"]["photo"] == 1
    assert summary["by_type"]["voice"] == 1

    events = await repo.get_events_with_attachment_counts(req["id"])
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.REQUEST_CREATED.value
    assert events[0]["attachments_count"] == 2
