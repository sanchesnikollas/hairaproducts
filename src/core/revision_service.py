from __future__ import annotations
import json
from sqlalchemy.orm import Session
from src.storage.ops_models import RevisionHistoryORM


def _serialize(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def create_revisions(
    session: Session,
    entity_type: str,
    entity_id: str,
    old_values: dict[str, object],
    new_values: dict[str, object],
    changed_by: str | None,
    change_source: str,
    change_reason: str | None = None,
) -> list[RevisionHistoryORM]:
    """Compare old and new values, create RevisionHistory for each changed field."""
    revisions = []
    for field in new_values:
        old_val = old_values.get(field)
        new_val = new_values[field]
        if _serialize(old_val) == _serialize(new_val):
            continue
        rev = RevisionHistoryORM(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field,
            old_value=_serialize(old_val),
            new_value=_serialize(new_val),
            changed_by=changed_by,
            change_source=change_source,
            change_reason=change_reason,
        )
        session.add(rev)
        revisions.append(rev)
    if revisions:
        session.flush()
    return revisions


def get_entity_history(
    session: Session,
    entity_type: str,
    entity_id: str,
    field_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RevisionHistoryORM]:
    """Return revision history for an entity, ordered by created_at."""
    q = session.query(RevisionHistoryORM).filter(
        RevisionHistoryORM.entity_type == entity_type,
        RevisionHistoryORM.entity_id == entity_id,
    )
    if field_name:
        q = q.filter(RevisionHistoryORM.field_name == field_name)
    return q.order_by(RevisionHistoryORM.created_at.asc()).offset(offset).limit(limit).all()


def count_entity_history(
    session: Session,
    entity_type: str,
    entity_id: str,
) -> int:
    """Return total revision count for an entity."""
    from sqlalchemy import func
    return session.query(func.count(RevisionHistoryORM.revision_id)).filter(
        RevisionHistoryORM.entity_type == entity_type,
        RevisionHistoryORM.entity_id == entity_id,
    ).scalar() or 0
