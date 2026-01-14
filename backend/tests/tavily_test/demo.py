import os

from openai import OpenAI
from tavily import TavilyClient


# ---------------------- 初始化客户端 ----------------------
def init_clients():
    """初始化 Tavily 和 OpenAI 客户端（环境变量加载 API Key）"""
    # 初始化 Tavily 客户端
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        raise ValueError("请先配置 TAVILY_API_KEY 环境变量")
    tavily_client = TavilyClient(api_key=tavily_api_key)

    # 初始化 OpenAI 客户端（可选，用于 LLM 结果聚合）
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

    return tavily_client, openai_client


# ---------------------- Tavily Search 实现 ----------------------
def run_tavily_search(tavily_client, query, search_depth="advanced", max_results=5):
    """
    执行 Tavily Search，获取高相关性 URL 与摘要
    :param tavily_client: 已初始化的 Tavily 客户端
    :param query: 构造好的搜索查询词
    :param search_depth: 搜索深度（basic/advanced）
    :param max_results: 返回结果数量（3-8 最佳）
    :return: 筛选后的有效搜索结果列表（包含 url、summary、score）
    """
    try:
        # 调用 Tavily Search API
        search_response = tavily_client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=False,  # 关闭直接答案，后续用 Extract 深度解析
            include_summary=True,  # 开启摘要，用于前期 URL 筛选
            include_raw_content=False,  # 暂不获取原始内容，减少数据冗余
            include_links=True,  # 必须开启，返回 URL 用于后续 Extract 调用
        )

        # 筛选有效结果（相关性 score >= 0.7，剔除无 URL 记录）
        valid_results = []
        for result in search_response.get("results", []):
            url = result.get("url")
            score = result.get("score", 0)
            if url and score >= 0.7:
                valid_results.append(
                    {"url": url, "summary": result.get("summary", ""), "score": score}
                )

        print(f"✅ Tavily Search 完成，获取 {len(valid_results)} 条有效结果")
        return valid_results

    except Exception as e:
        print(f"❌ Tavily Search 执行失败：{str(e)}")
        return []


# ---------------------- Tavily Extract 实现 ----------------------
def run_tavily_extract_batch(tavily_client, url_list, extract_type="text"):
    """
    批量执行 Tavily Extract，提取网页结构化内容
    :param tavily_client: 已初始化的 Tavily 客户端
    :param url_list: 筛选后的 URL 列表
    :param extract_type: 提取类型（text/table/all）
    :return: 提取结果字典（key=url，value=提取内容）
    """
    extract_results = {}
    if not url_list:
        print("⚠️ 无有效 URL 可供提取，跳过 Tavily Extract")
        return extract_results

    try:
        for url in url_list:
            # 调用 Tavily Extract API
            extract_response = tavily_client.extract(
                url=url,
                extract_type=extract_type,
                clean_html=True,  # 开启 HTML 清理，去除广告/导航噪音
            )

            # 提取核心内容，处理空结果
            core_content = extract_response.get("content", "")
            if core_content:
                extract_results[url] = core_content
                print(f"✅ 成功提取 URL 内容：{url[:50]}...")
            else:
                extract_results[url] = "无法提取有效内容"
                print(f"⚠️ 无法提取 URL 内容：{url[:50]}...")

        print(
            f"\n✅ Tavily Extract 批量处理完成，有效提取 {len([v for v in extract_results.values() if v != '无法提取有效内容'])} 条 URL"
        )
        return extract_results

    except Exception as e:
        print(f"❌ Tavily Extract 执行失败：{str(e)}")
        return extract_results


# ---------------------- LLM 结果聚合（可选） ----------------------
def aggregate_results_with_llm(openai_client, query, search_results, extract_results):
    """
    利用 LLM 聚合 Search 摘要和 Extract 深度内容，生成最终回答
    :param openai_client: 已初始化的 OpenAI 客户端
    :param query: 原始搜索查询词
    :param search_results: Search 结果列表
    :param extract_results: Extract 结果字典
    :return: LLM 生成的结构化回答
    """
    if not openai_client:
        return "⚠️ 未配置 OpenAI API Key，跳过 LLM 结果聚合"

    try:
        # 构造 LLM 上下文（结构化输入，提升推理准确性）
        prompt_context = f"""
        你的任务是基于以下联网查询结果，回答用户问题：{query}

        ## 第一步：搜索摘要（高相关性）
        {chr(10).join([f"- URL：{r['url'][:50]}... | 摘要：{r['summary'][:200]}..." for r in search_results])}

        ## 第二步：深度提取内容（核心数据）
        {chr(10).join([f"- URL：{url[:50]}... | 提取内容：{content[:500]}..." for url, content in extract_results.items() if content != "无法提取有效内容"])}

        ## 回答要求
        1.  优先基于深度提取内容，结合搜索摘要，确保信息准确、全面
        2.  去除重复信息，对冲突内容标注来源差异
        3.  结构化输出（使用 Markdown 分段），语言简洁易懂
        """

        # 调用 OpenAI GPT 模型进行推理
        completion = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "你是专业的信息聚合分析师，擅长整合多来源联网信息生成精准回答",
                },
                {"role": "user", "content": prompt_context},
            ],
            temperature=0.3,  # 低温度，保证回答的严谨性
        )

        return completion.choices[0].message.content

    except Exception as e:
        print(f"❌ LLM 结果聚合失败：{str(e)}")
        return f"LLM 聚合出错：{str(e)}"


# ---------------------- 主流程（Search + Extract 联动） ----------------------
def main():
    # 1. 初始化客户端
    tavily_client, openai_client = init_clients()

    # 2. 构造精准查询词（遵循最佳实践：明确约束条件）
    user_query = "2025-2026 人工智能大模型 工业领域 最新应用进展 与 落地案例"

    # 3. 执行 Tavily Search
    search_results = run_tavily_search(
        tavily_client=tavily_client,
        query=user_query,
        search_depth="advanced",
        max_results=5,
    )
    if not search_results:
        print("❌ 无有效搜索结果，流程终止")
        return

    # 4. 提取有效 URL 列表
    valid_urls = [result["url"] for result in search_results]

    # 5. 执行 Tavily Extract 批量提取
    extract_results = run_tavily_extract_batch(
        tavily_client=tavily_client, url_list=valid_urls, extract_type="text"
    )

    # 6. （可选）LLM 结果聚合与结构化输出
    print("\n" + "=" * 80)
    print("📋 最终结果（LLM 聚合后）：")
    print("=" * 80)
    final_answer = aggregate_results_with_llm(
        openai_client=openai_client,
        query=user_query,
        search_results=search_results,
        extract_results=extract_results,
    )
    print(final_answer)


# ---------------------- 运行程序 ----------------------
if __name__ == "__main__":
    main()
