"""评估领域服务"""

from app.services.eval.bad_case_service import BadCaseService
from app.services.eval.batch_eval_service import BatchEvalService

__all__ = ["BadCaseService", "BatchEvalService"]
