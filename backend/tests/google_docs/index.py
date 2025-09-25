# 片段0：通用鉴权与服务构建
from __future__ import annotations
import os
from typing import List
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# 根据需要选择最小权限
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


def get_services():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    drive = build("drive", "v3", credentials=creds)
    docs = build("docs", "v1", credentials=creds)
    return drive, docs

# 片段1：检索 Google Docs 文档（按名称关键词、类型过滤）


def search_docs(drive, query_text: str, page_size: int = 10):
    # MIME type for Google Docs
    mime_gdoc = "application/vnd.google-apps.document"
    # Drive 查询语法示例：name contains 'xxx' and mimeType='...'
    q = f"name contains '{query_text}' and mimeType='{mime_gdoc}' and trashed = false"
    results = drive.files().list(q=q, pageSize=page_size,
                                 fields="files(id, name, owners(displayName), modifiedTime)").execute()
    return results.get("files", [])

# 片段2：使用 Docs API 解析文档结构并抽取纯文本


def extract_doc_text(docs, document_id: str) -> str:
    doc = docs.documents().get(documentId=document_id).execute()
    content = doc.get("body", {}).get("content", [])
    texts = []

    def read_elements(elements):
        for e in elements:
            if "paragraph" in e:
                for elem in e["paragraph"].get("elements", []):
                    txt = elem.get("textRun", {}).get("content", "")
                    texts.append(txt)
            elif "table" in e:
                for row in e["table"]["tableRows"]:
                    for cell in row["tableCells"]:
                        read_elements(cell.get("content", []))
            elif "tableOfContents" in e:
                read_elements(e["tableOfContents"].get("content", []))

    read_elements(content)
    return "".join(texts)

# 片段3：通过 Drive API 导出为 TXT 或 HTML


def export_doc(drive, file_id: str, mime: str = "text/plain") -> bytes:
    # txt: text/plain, html: text/html, markdown 官方不支持需第三方转换
    resp = drive.files().export(fileId=file_id, mimeType=mime).execute()
    return resp


if __name__ == "__main__":
    drive, docs = get_services()
    files = search_docs(drive, "需求文档", page_size=5)
    for f in files:
        print(f"- {f['name']} ({f['id']}) | updated: {f['modifiedTime']}")
        text = extract_doc_text(docs, f["id"])
        print("Preview:", text[:200].replace("\n", " "), "...\n")
        html_bytes = export_doc(drive, f["id"], "text/html")
        with open(f"{f['id']}.html", "wb") as fp:
            fp.write(html_bytes)
        print("Saved:", f"{f['id']}.html")
