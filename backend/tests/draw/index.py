import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
import numpy as np

# Create figure and axis
fig, ax = plt.subplots(figsize=(14, 10))

# Define components and their positions
components = {
    'Cron Job': 0,
    'Visibility Service': 1,
    'Topic Service': 2,
    'Kafka': 3,
    'Sampling Tool': 4,
    'AI Platform': 5,
    'MySQL': 6,
    'S3': 7,
    'DataStudio': 8
}

# Draw vertical lines for each component
for comp, x in components.items():
    ax.axvline(x=x, color='black', linewidth=2)
    ax.text(x, -0.1, comp, ha='center', va='top',
            fontsize=10, fontweight='bold')

# Define timeline
start_time = 0
end_time = 10
time_steps = np.linspace(start_time, end_time, 100)

# Draw sequence of events
# 1. Cron Job triggers Visibility Service
ax.arrow(components['Cron Job'], 0.5, components['Visibility Service'] - components['Cron Job'], 0,
         head_width=0.1, head_length=0.1, fc='blue', ec='blue', linewidth=2)
ax.text((components['Cron Job'] + components['Visibility Service'])/2, 0.6, '触发调度',
        ha='center', va='bottom', fontsize=9, color='blue')

# 2. Visibility Service queries Topic Service
ax.arrow(components['Visibility Service'], 1.0, components['Topic Service'] - components['Visibility Service'], 0,
         head_width=0.1, head_length=0.1, fc='green', ec='green', linewidth=2)
ax.text((components['Visibility Service'] + components['Topic Service'])/2, 1.1, '查询采样Prompt',
        ha='center', va='bottom', fontsize=9, color='green')

# 3. Topic Service returns prompts
ax.arrow(components['Topic Service'], 1.5, components['Visibility Service'] - components['Topic Service'], 0,
         head_width=0.1, head_length=0.1, fc='green', ec='green', linewidth=2)
ax.text((components['Visibility Service'] + components['Topic Service'])/2, 1.6, '返回Prompt列表',
        ha='center', va='bottom', fontsize=9, color='green')

# 4. Visibility Service publishes to Kafka
ax.arrow(components['Visibility Service'], 2.0, components['Kafka'] - components['Visibility Service'], 0,
         head_width=0.1, head_length=0.1, fc='red', ec='red', linewidth=2)
ax.text((components['Visibility Service'] + components['Kafka'])/2, 2.1, '发布采样任务',
        ha='center', va='bottom', fontsize=9, color='red')

# 5. Sampling Tool consumes from Kafka
ax.arrow(components['Kafka'], 2.5, components['Sampling Tool'] - components['Kafka'], 0,
         head_width=0.1, head_length=0.1, fc='orange', ec='orange', linewidth=2)
ax.text((components['Kafka'] + components['Sampling Tool'])/2, 2.6, '消费任务',
        ha='center', va='bottom', fontsize=9, color='orange')

# 6. Sampling Tool calls AI Platform
ax.arrow(components['Sampling Tool'], 3.0, components['AI Platform'] - components['Sampling Tool'], 0,
         head_width=0.1, head_length=0.1, fc='purple', ec='purple', linewidth=2)
ax.text((components['Sampling Tool'] + components['AI Platform'])/2, 3.1, '调用AI平台',
        ha='center', va='bottom', fontsize=9, color='purple')

# 7. AI Platform returns response
ax.arrow(components['AI Platform'], 3.5, components['Sampling Tool'] - components['AI Platform'], 0,
         head_width=0.1, head_length=0.1, fc='purple', ec='purple', linewidth=2)
ax.text((components['Sampling Tool'] + components['AI Platform'])/2, 3.6, '返回AI答案',
        ha='center', va='bottom', fontsize=9, color='purple')

# 8. Sampling Tool saves screenshot to S3
ax.arrow(components['Sampling Tool'], 4.0, components['S3'] - components['Sampling Tool'], 0,
         head_width=0.1, head_length=0.1, fc='brown', ec='brown', linewidth=2)
ax.text((components['Sampling Tool'] + components['S3'])/2, 4.1, '存储截图',
        ha='center', va='bottom', fontsize=9, color='brown')

# 9. Sampling Tool saves data to MySQL
ax.arrow(components['Sampling Tool'], 4.5, components['MySQL'] - components['Sampling Tool'], 0,
         head_width=0.1, head_length=0.1, fc='teal', ec='teal', linewidth=2)
ax.text((components['Sampling Tool'] + components['MySQL'])/2, 4.6, '存储数据',
        ha='center', va='bottom', fontsize=9, color='teal')

# 10. DataStudio syncs from MySQL
ax.arrow(components['MySQL'], 5.0, components['DataStudio'] - components['MySQL'], 0,
         head_width=0.1, head_length=0.1, fc='darkblue', ec='darkblue', linewidth=2)
ax.text((components['MySQL'] + components['DataStudio'])/2, 5.1, '定时同步数据',
        ha='center', va='bottom', fontsize=9, color='darkblue')

# Set up the plot
ax.set_xlim(-0.5, 8.5)
ax.set_ylim(-0.5, 5.5)
ax.set_title('GEO Portal 可见性模块时序图\nVisibility Module Sequence Diagram',
             fontsize=14, fontweight='bold', pad=20)
ax.set_xlabel('系统组件', fontsize=12)
ax.set_ylabel('时间序列', fontsize=12)

# Remove axis ticks
ax.set_xticks([])
ax.set_yticks([])

# Add legend
legend_elements = [
    plt.Line2D([0], [0], color='blue', linewidth=2, label='调度触发'),
    plt.Line2D([0], [0], color='green', linewidth=2, label='查询服务'),
    plt.Line2D([0], [0], color='red', linewidth=2, label='任务分发'),
    plt.Line2D([0], [0], color='orange', linewidth=2, label='任务消费'),
    plt.Line2D([0], [0], color='purple', linewidth=2, label='AI平台交互'),
    plt.Line2D([0], [0], color='brown', linewidth=2, label='文件存储'),
    plt.Line2D([0], [0], color='teal', linewidth=2, label='数据存储'),
    plt.Line2D([0], [0], color='darkblue', linewidth=2, label='数据同步')
]
ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1))

plt.tight_layout()
plt.show()

# Print the sequence description
print("\n=== GEO Portal 可见性模块时序流程 ===")
print("1. Cron Job → Visibility Service: 触发调度任务")
print("2. Visibility Service → Topic Service: 查询需要采样的Prompt")
print("3. Topic Service → Visibility Service: 返回Prompt列表")
print("4. Visibility Service → Kafka: 发布采样任务到消息队列")
print("5. Kafka → Sampling Tool: 多个采样工具实例消费任务")
print("6. Sampling Tool → AI Platform: 调用AI平台获取答案")
print("7. AI Platform → Sampling Tool: 返回AI答案内容")
print("8. Sampling Tool → S3: 存储截图文件")
print("9. Sampling Tool → MySQL: 存储结构化数据")
print("10. MySQL → DataStudio: 定时同步数据用于指标计算")
print("\n关键特性：")
print("- 异步处理：通过Kafka实现任务分发")
print("- 水平扩展：多个Sampling Tool实例并行处理")
print("- 数据持久化：截图(S3) + 结构化数据(MySQL)")
print("- 监控分析：DataStudio进行指标计算")
