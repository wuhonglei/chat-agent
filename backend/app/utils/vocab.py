import re
from pathlib import Path


def _load_all_stopwords() -> set[str]:
    """
    从 app/utils/stopwords 目录加载所有 txt 文件中的停用词

    Returns:
        set[str]: 所有停用词的集合
    """
    stopwords_dir = Path(__file__).parent / "stopwords"
    all_stopwords: set[str] = set()

    if stopwords_dir.exists():
        for txt_file in stopwords_dir.glob("*.txt"):
            try:
                with open(txt_file, encoding="utf-8") as file:
                    all_stopwords.update(
                        {line.strip() for line in file if line.strip()}
                    )
            except Exception:
                # 忽略加载失败的文件
                continue

    return all_stopwords


class VocabProcessor:
    """词汇处理器，用于处理文本关键词提取和查询相似度计算"""

    stop_words: set[str] = _load_all_stopwords()

    def remove_stopwords(self, text: str) -> set[str]:
        """
        提取关键词（去除停用词）

        Args:
            text: 输入文本

        Returns:
            set[str]: 关键词集合
        """
        # 简单的分词：按空格和标点符号分割
        words = re.findall(r"\b\w+\b", text.lower())
        return {w for w in words if w not in VocabProcessor.stop_words and len(w) > 1}

    def calculate_query_similarity(self, query1: str, query2: str) -> float:
        """
        计算两个查询的相似度（基于关键词重叠）

        Args:
            query1: 第一个查询
            query2: 第二个查询

        Returns:
            float: 相似度（0-1），1 表示完全相同
        """
        keywords1 = self.remove_stopwords(query1)
        keywords2 = self.remove_stopwords(query2)

        if not keywords1 and not keywords2:
            # 如果两个查询都没有关键词，检查原始文本是否相同
            return 1.0 if query1.strip().lower() == query2.strip().lower() else 0.0

        if not keywords1 or not keywords2:
            return 0.0

        # 计算关键词重叠率
        common_keywords = keywords1 & keywords2
        max_keywords = max(len(keywords1), len(keywords2))
        similarity = len(common_keywords) / max_keywords if max_keywords > 0 else 0.0

        return similarity
