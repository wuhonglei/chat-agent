from langchain.document_loaders import ConfluenceLoader

# 配置加载器
loader = ConfluenceLoader(
    url="https://confluence.shopee.io/",
    cloud=False,
    username="honglei.wu@shopee.com",
    api_key="MjMwODI5NTgxMDYwOt1r0afzAeDn45aJ/zVi7MHYnPkS"
)

# 加载一个空间下的所有文档（甚至可以自动提取附件中的文本）:cite[4]
documents = loader.load(space_key="2020", include_attachments=True, limit=50)

# 加载到的 documents 可以直接用于后续的AI应用流程
for doc in documents:
    print(doc.page_content)  # 页面的文本内容
    print(doc.metadata)      # 元数据，如标题、URL等
