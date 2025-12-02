import os
from jinja2 import Template

# 获取模板文件所在目录
_template_dir = os.path.dirname(os.path.abspath(__file__))


def _load_template(filename):
    """加载 HTML 模板文件并创建 Jinja2 模板对象

    Args:
        filename: 模板文件名（相对于模板目录）

    Returns:
        Template: Jinja2 模板对象
    """
    template_path = os.path.join(_template_dir, filename)
    with open(template_path, 'r', encoding='utf-8') as f:
        return Template(f.read())


# 读取成功部署模板
success_template = _load_template('email-success.html')

# 读取失败部署模板
failed_template = _load_template('email-failed.html')
