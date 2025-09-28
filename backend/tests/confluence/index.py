from atlassian import Confluence
import os
from base import BasePreprocessor


def write_to_file(content, file_path):
    with open(file_path, 'w') as f:
        f.write(content)


def mkdir(dir_path: str):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


base_url = 'https://confluence.shopee.io'
# 如果是 Confluence Cloud（使用邮箱和API令牌）
confluence_client = Confluence(
    url=base_url,
    token='MjMwODI5NTgxMDYwOt1r0afzAeDn45aJ/zVi7MHYnPkS',  # 注意这里填API令牌，而非登录密码
    cloud=False,
)

preprocessor = BasePreprocessor(base_url=base_url)

title = '【PRD】DAP V7.0 Display & Video 360 solution'
# CQL搜索返回的是结果集
search_results = confluence_client.cql(f"""
siteSearch ~ "f{title}"
""")

# 从结果集中获取页面
pages = search_results.get('results', [])
if not pages:
    print(f"No pages found with title: {title}")
    exit(0)

print(f"Found {len(pages)} page(s)")
for i, page in enumerate(pages[:1]):
    # 获取第一个页面的内容
    # CQL 搜索结果中的页面内容在 content 字段里
    page_id = page.get('content', {}).get('id')
    if page_id:
        print(f"Getting full page content for ID: {page_id}")
        # 使用页面ID获取完整内容，包括body.storage
        full_page = confluence_client.get_page_by_id(
            page_id, expand='body.storage')
        html_content = full_page.get('body', {}).get(
            'storage', {}).get('value', '')
        pass
    else:
        continue

    processed_html, processed_markdown = preprocessor.process_html_content(
        html_content=html_content,
        confluence_client=confluence_client,
        image_prefix=f'{base_url}/download/attachments/{page_id}',
    )

    base_dir = f'data/{title}/{i}'
    mkdir(base_dir)
    if len(html_content) > 0:
        write_to_file(html_content, f'{base_dir}/original.html')
        print(f'Saved: {f'{base_dir}/original.html'}')
    else:
        print(f'No HTML content found for {title} {i}')

    if len(processed_html) > 0:
        write_to_file(processed_html, f'{base_dir}/processed.html')
        print(f'Saved: {f'{base_dir}/processed.html'}')
    else:
        print(f'No HTML content found for {title} {i}')
    if len(processed_markdown) > 0:
        write_to_file(processed_markdown, f'{base_dir}/processed.md')
        print(f'Saved: {f'{base_dir}/processed.md'}')
    else:
        print(f'No Markdown content found for {title} {i}')
