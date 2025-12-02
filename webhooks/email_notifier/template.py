from jinja2 import Template

success_template = Template("""
<h1>部署任务已成功完成！</h1>
<p>仓库路径: {{ repo_path }}</p>
<p>部署脚本: {{ deploy_script }}</p>
<p>提交 SHA: {{ commit_sha or 'N/A' }}</p>
<p>提交信息: {{ commit_message or 'N/A' }}</p>
<p>部署时间: {{ deploy_time }}</p>
""")

failed_template = Template("""
<h1>部署任务已失败！</h1>
<p>仓库路径: {{ repo_path }}</p>
<p>部署脚本: {{ deploy_script }}</p>
<p>提交 SHA: {{ commit_sha or 'N/A' }}</p>
<p>提交信息: {{ commit_message or 'N/A' }}</p>
<p>部署时间: {{ deploy_time }}</p>
<p>错误信息: {{ error_message }}</p>
""")
