"""Replay task: 对评估集每条 query 调用真实 API 重新生成回答，再送裁判评分。

用法:
    # replay 模式（自动签发临时 token，无需手动传 --token）
    uv run python scripts/run_eval_gate.py --replay

    # 也可以手动指定 token（跳过自动签发）
    uv run python scripts/run_eval_gate.py --replay --token <jwt>

流程:
    1. 从 dataset item 提取 user query + 附件信息
    2. 自动签发临时 JWT token（读 .env 的 private key）
    3. POST /api/conversation/register 创建会话
    4. POST /api/chat/stream 发送 query（含附件 content_blocks），收集 SSE 流式回答
    5. 将新回答作为 judge 输入

附件处理:
    dataset item 的 user message XML 中包含 <attachment_uploads>，
    记录了文件名、类型、虚拟路径等元信息。
    replay 时构造对应的 content_blocks（pdf/markdown 类型），
    服务器会从 user data 目录读取文件并处理。
    注意：文件需要在 replay 服务器的 user data 目录中存在。
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET

import httpx


def _load_jwt_keys_from_nacos() -> tuple[str, str]:
    """从 Nacos 本地缓存读取 JWT 私钥（env vars 未配置时的 fallback）。"""
    from pathlib import Path

    nacos_dir = Path(__file__).resolve().parent.parent / "nacos-data" / "config"
    for config_file in nacos_dir.iterdir():
        if "@@DEFAULT_GROUP@@" not in config_file.name:
            continue
        try:
            import yaml

            with open(config_file) as f:
                config = yaml.safe_load(f)
            jwt_cfg = (config or {}).get("security", {}).get("jwt", {})
            pk = jwt_cfg.get("private_key", "")
            algo = jwt_cfg.get("algorithm", "RS256")
            if pk:
                return pk, algo
        except Exception:
            continue
    return "", "RS256"


def _find_eval_user() -> str:
    """从数据库找一个可用的 user_id（用于签发 eval token）。"""
    import os

    for line in open(".env"):
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v

    from sqlmodel import Session, select

    from app.core.db import engine
    from app.models import UserDb

    with Session(engine) as db:
        user = db.exec(select(UserDb).limit(1)).first()
        if user:
            return user.id
    raise RuntimeError("数据库中无可用用户，请先创建用户或指定 --user-id")


def generate_eval_token(user_id: str = "") -> str:
    """签发一个临时 eval token（有效期 1 小时）。

    读取顺序：环境变量 SECURITY__JWT__PRIVATE_KEY → Nacos 本地缓存。
    """
    import os

    private_key = os.environ.get("SECURITY__JWT__PRIVATE_KEY", "")
    algorithm = os.environ.get("SECURITY__JWT__ALGORITHM", "")
    if not private_key:
        private_key, algorithm = _load_jwt_keys_from_nacos()
    if not algorithm:
        algorithm = "RS256"
    if not private_key:
        raise RuntimeError(
            "未找到 JWT 私钥。请在 .env 中设置 SECURITY__JWT__PRIVATE_KEY，"
            "或确保 nacos-data/config/ 目录下有 Nacos 配置缓存。"
        )
    if not user_id:
        user_id = _find_eval_user()

    import jwt as pyjwt

    now = int(time.time())
    payload = {
        "user_id": user_id,
        "iat": now,
        "exp": now + 3600,  # 1 小时有效期
    }
    return pyjwt.encode(payload, private_key, algorithm=algorithm)


def extract_query_from_item(item_input: dict) -> str:
    """从 dataset item 的 input.messages 中提取用户 query。"""
    user_content = _get_user_content(item_input)
    return _parse_query(user_content)


def extract_attachments_from_item(item_input: dict) -> list[dict]:
    """从 dataset item 的 input.messages 中提取附件信息。

    返回格式:
        [{"name": "file.pdf", "type": "pdf", "virtual_path": "/mnt/...", "markdown": {...}}, ...]
    """
    user_content = _get_user_content(item_input)
    return _parse_attachments(user_content)


def _get_user_content(item_input: dict) -> str:
    """获取 user message 的 content。"""
    messages = item_input.get("messages", [])
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            return msg["content"]
    return ""


def _parse_query(user_content: str) -> str:
    """从 XML 中提取 <query> 文本。"""
    match = re.search(r"<query>(.*?)</query>", user_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 没有 XML 格式，直接返回
    return user_content.strip()


def _parse_attachments(user_content: str) -> list[dict]:
    """从 XML 中解析 <attachment_uploads> 里的文件信息。"""
    attachments = []
    # 提取 <user_message> 部分
    um_match = re.search(r"<user_message>(.*?)</user_message>", user_content, re.DOTALL)
    if not um_match:
        return attachments

    xml_str = um_match.group(0)
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return attachments

    for file_elem in root.findall(".//file"):
        att: dict = {
            "name": _elem_text(file_elem, "name", ""),
            "type": _elem_text(file_elem, "type", ""),
            "virtual_path": _elem_text(file_elem, "virtual_path", ""),
            "file_size": _elem_text(file_elem, "file_size", ""),
        }
        md_elem = file_elem.find("markdown")
        if md_elem is not None:
            att["markdown"] = {
                "name": _elem_text(md_elem, "name", ""),
                "virtual_path": _elem_text(md_elem, "virtual_path", ""),
                "file_size": _elem_text(md_elem, "file_size", ""),
                "token_size": _elem_text(md_elem, "token_size", ""),
                "lines_count": _elem_text(md_elem, "lines_count", ""),
            }
        attachments.append(att)

    return attachments


def _elem_text(parent, tag: str, default: str = "") -> str:
    """安全提取 XML 子元素文本。"""
    elem = parent.find(tag)
    return elem.text.strip() if elem is not None and elem.text else default


def build_content_blocks(query: str, attachments: list[dict]) -> list[dict]:
    """构造 ChatRequest.content_blocks：text + 文件 block。"""
    import uuid

    blocks: list[dict] = [
        {
            "id": f"cb_user_text_{uuid.uuid4().hex[:12]}",
            "type": "text",
            "text": query,
        }
    ]

    for att in attachments:
        file_type = att.get("type", "")
        file_id = uuid.uuid4().hex

        if file_type == "pdf":
            block: dict = {
                "id": file_id,
                "type": "pdf",
                "name": att["name"],
                "url": "",  # 服务器根据 storage_key 解析
                "storage_key": "",  # 需要从 virtual_path 推导
                "mime": "application/pdf",
            }
            # 如果有 markdown 派生文件，附加
            if att.get("markdown"):
                md = att["markdown"]
                block["markdown"] = {
                    "id": uuid.uuid4().hex,
                    "type": "markdown",
                    "name": md["name"],
                    "url": "",
                    "storage_key": "",
                    "mime": "text/markdown",
                }
            blocks.append(block)
        elif file_type == "markdown":
            blocks.append(
                {
                    "id": file_id,
                    "type": "markdown",
                    "name": att["name"],
                    "url": "",
                    "storage_key": "",
                    "mime": "text/markdown",
                }
            )

    return blocks


def build_content_blocks_from_uploads(
    query: str, uploaded_files: list[dict]
) -> list[dict]:
    """用已上传文件的 AttachmentBlock 响应构造 content_blocks。"""
    import uuid

    blocks: list[dict] = [
        {
            "id": f"cb_user_text_{uuid.uuid4().hex[:12]}",
            "type": "text",
            "text": query,
        }
    ]
    for uf in uploaded_files:
        blocks.append(uf)
    return blocks


def _get_auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def upload_file(
    base_url: str,
    token: str,
    conversation_id: str,
    file_path: str,
) -> dict | None:
    """上传文件到会话，返回 AttachmentBlock dict（含 id, url, storage_key 等）。

    Args:
        file_path: 本地文件路径（如 data/eval_set/attachments/xxx.pdf）
    Returns:
        AttachmentBlock dict，或 None（上传失败时）
    """
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        return None

    mime_map = {
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    mime = mime_map.get(path.suffix.lower(), "application/octet-stream")

    try:
        with open(path, "rb") as f:
            r = httpx.post(
                f"{base_url}/api/file/upload",
                headers={"Authorization": f"Bearer {token}"},
                data={"conversation_id": conversation_id},
                files={"file": (path.name, f, mime)},
                timeout=60,
            )
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == 0 and data.get("data"):
                return data["data"]
        return None
    except Exception:
        return None


def create_conversation(
    base_url: str, token: str, title: str = "eval-replay"
) -> str | None:
    """创建会话，返回 conversation_id。"""
    try:
        r = httpx.post(
            f"{base_url}/api/conversation/register",
            headers=_get_auth_headers(token),
            json={"title": title},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == 0 and data.get("data"):
                return data["data"].get("id") or data["data"].get("conversation_id")
        return None
    except Exception:
        return None


def replay_query(
    base_url: str,
    token: str,
    conversation_id: str,
    query: str,
    attachments: list[dict] | None = None,
    uploaded_files: list[dict] | None = None,
    agent_mode: int = 0,
    timeout: float = 120,
) -> str:
    """发送 query 到 chat/stream API，等 done 事件后从 DB 获取完整回答。

    流程：发请求 → 监听 done 事件拿 assistant_message_id → 查 DB 拿 content_blocks。
    比拼接 delta 更可靠，且能获取完整结构化内容（含工具调用结果）。
    """
    import time as _time

    if uploaded_files:
        content_blocks = build_content_blocks_from_uploads(query, uploaded_files)
    else:
        content_blocks = build_content_blocks(query, attachments or [])

    payload = {
        "content_blocks": content_blocks,
        "conversation_id": conversation_id,
        "agent_mode": agent_mode,
        "history_ids": [],
    }

    try:
        with httpx.stream(
            "POST",
            f"{base_url}/api/chat/stream",
            headers=_get_auth_headers(token),
            json=payload,
            timeout=timeout,
        ) as response:
            if response.status_code != 200:
                return f"[ERROR] HTTP {response.status_code}"

            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                    event_type = event.get("type", "")
                    event_data = event.get("data", {})
                    if event_type == "done":
                        assistant_message_id = event_data.get("assistant_message_id")
                        break
                    elif event_type == "error":
                        # error 事件也可能携带 conversation_id，继续查 DB
                        break
                except json.JSONDecodeError:
                    continue

    except httpx.TimeoutException:
        return f"[ERROR] Timeout after {timeout}s"
    except Exception as exc:
        return f"[ERROR] {type(exc).__name__}: {exc}"

    # 等待 DB 写入完成
    _time.sleep(1)

    # 取最后一条助手消息（done 事件正常时就是刚生成的那条）
    return _fetch_last_assistant_answer(base_url, token, conversation_id)


def _fetch_last_assistant_answer(
    base_url: str, token: str, conversation_id: str
) -> str:
    """从会话消息列表中获取最后一条助手回答。"""
    try:
        r = httpx.get(
            f"{base_url}/api/conversation/{conversation_id}/messages",
            headers=_get_auth_headers(token),
            timeout=10,
        )
        if r.status_code != 200:
            return f"[ERROR] messages API HTTP {r.status_code}"

        data = r.json()
        messages = data.get("data", {}).get("messages", [])

        # 找最后一条 assistant 消息
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return _extract_text_from_blocks(msg.get("content_blocks", []))

        return "[ERROR] no assistant message found"
    except Exception as exc:
        return f"[ERROR] fetch last answer: {exc}"


def _extract_text_from_blocks(blocks: list[dict]) -> str:
    """从 content_blocks 中提取最后一个 TextBlock 的文本（模型最终回答）。"""
    for block in reversed(blocks):
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text:
                return text.strip()
    return ""


def cleanup_conversation(base_url: str, token: str, conversation_id: str) -> None:
    """删除评估用的临时会话。"""
    try:
        httpx.delete(
            f"{base_url}/api/conversation/delete/{conversation_id}",
            headers=_get_auth_headers(token),
            timeout=5,
        )
    except Exception:
        pass
