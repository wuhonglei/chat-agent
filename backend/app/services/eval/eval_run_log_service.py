"""评估运行日志查询服务。"""

from __future__ import annotations

from sqlmodel import Session, col, desc, func, select

from app.models.eval_run_log_db import EvalRunLog
from app.schemas.eval import (
    EvalRunLogListResponse,
    EvalRunLogResponse,
    EvalRunStatus,
    EvalRunType,
)


class EvalRunLogService:
    """eval_run_logs 列表 / 详情查询。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def has_running(self) -> bool:
        """是否存在进行中的评估运行。"""
        stmt = (
            select(func.count())
            .select_from(EvalRunLog)
            .where(EvalRunLog.status == EvalRunStatus.RUNNING.value)
        )
        return int(self.db.exec(stmt).one()) > 0

    def get_run_log(self, run_id: str) -> EvalRunLog | None:
        return self.db.get(EvalRunLog, run_id)

    def list_run_logs(
        self,
        *,
        status: EvalRunStatus | None = None,
        run_type: EvalRunType | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> EvalRunLogListResponse:
        stmt = select(EvalRunLog)
        if status:
            stmt = stmt.where(EvalRunLog.status == status.value)
        if run_type:
            stmt = stmt.where(EvalRunLog.run_type == run_type.value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.exec(count_stmt).one()

        stmt = stmt.order_by(desc(col(EvalRunLog.started_at)))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.exec(stmt).all())

        return EvalRunLogListResponse(
            items=[self.to_response(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def to_response(item: EvalRunLog) -> EvalRunLogResponse:
        return EvalRunLogResponse.model_validate(item.model_dump(mode="json"))
