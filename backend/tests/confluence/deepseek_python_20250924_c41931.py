from atlassian import Confluence

# 如果是 Confluence Cloud（使用邮箱和API令牌）
confluence = Confluence(
    url='https://confluence.shopee.io/',
    token='MjMwODI5NTgxMDYwOt1r0afzAeDn45aJ/zVi7MHYnPkS',  # 注意这里填API令牌，而非登录密码
    cloud=False,
)

# 获取某个空间下的所有页面（注意处理分页，limit最大为100）
all_pages = confluence.get_all_pages_from_space(
    '2020', start=0, limit=100, expand='body.storage')

print(all_pages)

# # 根据页面ID获取特定页面的详细内容（存储格式，便于解析表格等结构化数据）:cite[3]:cite[9]
# page_data = confluence.get_page_by_id(page_id='123456', expand='body.storage')
# page_content = page_data['body']['storage']['value']  # 获取XHTML格式的内容
