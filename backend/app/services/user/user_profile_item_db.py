"""用户画像条目 DB 服务：单条事实/偏好 + 语义检索"""

from __future__ import annotations

import hashlib

from sqlmodel import col, select

from app.core.config import settings
from app.models import UserProfileItemDb
from app.services.base_service import BaseService
from app.services.infrastructure.embedding_service import EmbeddingService
from app.utils.logger import logger

# 1=事实, 2=偏好
TYPE_FACT = 1
TYPE_PREFERENCE = 2

# 写入前单条 text 最大 token 估算（约 4 字符/token，512 token ≈ 2048 字符）
MAX_TEXT_LENGTH = 2048


def _normalized_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().lower().encode()).hexdigest()[:64]


def _normalize_text(text: str) -> str:
    t = (text or "").strip()
    if len(t) > MAX_TEXT_LENGTH:
        t = t[:MAX_TEXT_LENGTH]
    return t


class UserProfileItemDbService(BaseService):
    """用户画像条目 DB：按条存储 + pgvector 语义检索"""

    def _current_embedding_model_name(self) -> str:
        return settings.embedding_model.model_name

    async def add_item(
        self,
        user_id: str,
        text: str,
        item_type: int,
        embedding_model: str,
        embedding_vector: list[float],
    ) -> UserProfileItemDb:
        """插入或更新一条画像条目；归一化 text、长度检查、计算 embedding，ON CONFLICT DO UPDATE。"""
        normalized = _normalize_text(text)
        if not normalized:
            raise ValueError("text 为空或仅空白")
        text_hash = _normalized_hash(normalized)
        db = self._ensure_db()
        stmt = select(UserProfileItemDb).where(
            UserProfileItemDb.user_id == user_id,
            UserProfileItemDb.text_normalized_hash == text_hash,
            UserProfileItemDb.type == item_type,
        )
        row = db.exec(stmt).first()
        if row:
            row.text = normalized
            row.embedding_vector = embedding_vector
            row.embedding_model = embedding_model
            row.deleted_at = None
            db.add(row)
        else:
            row = UserProfileItemDb(
                user_id=user_id,
                text=normalized,
                type=item_type,
                embedding_vector=embedding_vector,
                embedding_model=embedding_model,
                text_normalized_hash=text_hash,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    async def batch_upsert_items(
        self,
        user_id: str,
        facts: list[str],
        preferences: list[str],
    ) -> None:
        """归纳后批量写入：先批量计算 facts/preferences 向量，再逐条 add_item，减少网络调用。"""
        normalized_facts = []
        for t in facts:
            if nt := _normalize_text(t):
                normalized_facts.append(nt)

        normalized_preferences = []
        for t in preferences:
            if nt := _normalize_text(t):
                normalized_preferences.append(nt)

        if not normalized_facts and not normalized_preferences:
            return

        embedding_svc = EmbeddingService()
        model_name = self._current_embedding_model_name()

        all_texts = normalized_facts + normalized_preferences
        all_vectors = await embedding_svc.embed_documents(all_texts)
        n_facts = len(normalized_facts)
        vectors_facts = all_vectors[:n_facts]
        vectors_prefs = all_vectors[n_facts:]

        for text, vec in zip(normalized_facts, vectors_facts):
            if not vec:
                continue
            try:
                await self.add_item(user_id, text, TYPE_FACT, model_name, vec)
            except Exception as e:
                logger.warning(
                    "UserProfileItemDbService.add_item fact failed",
                    user_id=user_id,
                    text_preview=text[:100],
                    error=e,
                )

        for text, vec in zip(normalized_preferences, vectors_prefs):
            if not vec:
                continue
            try:
                await self.add_item(user_id, text, TYPE_PREFERENCE, model_name, vec)
            except Exception as e:
                logger.warning(
                    "UserProfileItemDbService.add_item preference failed",
                    user_id=user_id,
                    text_preview=text[:100],
                    error=e,
                )

    def get_existing_texts(
        self,
        user_id: str,
    ) -> tuple[list[str], list[str]]:
        """返回该用户当前未删除的事实与偏好文本列表，用于归纳时合并已有内容。"""
        db = self._ensure_db()
        stmt = select(UserProfileItemDb.text, UserProfileItemDb.type).where(
            UserProfileItemDb.user_id == user_id,
            col(UserProfileItemDb.deleted_at).is_(None),
        )
        rows = db.exec(stmt).all()
        facts = [r[0] for r in rows if r[1] == TYPE_FACT]
        prefs = [r[0] for r in rows if r[1] == TYPE_PREFERENCE]
        return (facts, prefs)

    async def get_relevant_items(
        self,
        user_id: str,
        query_embedding: list[float],
        embedding_model: str,
        top_k_facts: int = 5,
        top_k_preferences: int = 5,
        relevance_threshold: float = 0.7,
    ) -> tuple[list[str], list[str]]:
        """按 query_embedding 语义检索 top-k 事实与偏好；仅使用 embedding_model 一致且 deleted_at IS NULL 的条目；相似度低于阈值不注入。"""
        if not query_embedding:
            return ([], [])

        db = self._ensure_db()
        # 余弦距离 <=> ；相似度 = 1 - 距离；阈值 0.7 即 距离 <= 0.3
        max_distance = 1.0 - relevance_threshold
        # 取候选数略多以便按 type 分别取 top_k 后过滤阈值
        limit = (top_k_facts + top_k_preferences) * 2
        stmt = (
            select(
                UserProfileItemDb.text,
                UserProfileItemDb.type,
                UserProfileItemDb.embedding_vector.cosine_distance(
                    query_embedding
                ).label("dist"),
            )
            .where(
                UserProfileItemDb.user_id == user_id,
                col(UserProfileItemDb.deleted_at).is_(None),
                UserProfileItemDb.embedding_model == embedding_model,
                col(UserProfileItemDb.embedding_vector).isnot(None),
            )
            .order_by(
                UserProfileItemDb.embedding_vector.cosine_distance(query_embedding)
            )
            .limit(limit)
        )
        rows = db.exec(stmt).all()
        facts: list[str] = []
        prefs: list[str] = []
        for text, itype, dist in rows:
            if dist is None or dist > max_distance:
                continue
            if itype == TYPE_FACT and len(facts) < top_k_facts:
                facts.append(text)
            elif itype == TYPE_PREFERENCE and len(prefs) < top_k_preferences:
                prefs.append(text)
            if len(facts) >= top_k_facts and len(prefs) >= top_k_preferences:
                break
        return (facts, prefs)
