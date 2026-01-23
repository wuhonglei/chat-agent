import time

from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox

load_dotenv()

start_time = time.perf_counter()
with Sandbox.create() as sandbox:
    execution = sandbox.run_code("""
# 这是一个简单的 Python 程序

# 打印 Hello, World!
print("Hello, World!")

# 定义两个变量
a = 10
b = 5

# 进行一些基本运算
sum_result = a + b
difference = a - b
product = a * b
quotient = a / b

# 打印结果
print(f"a = {a}, b = {b}")
print(f"a + b = {sum_result}")
print(f"a - b = {difference}")
print(f"a * b = {product}")
print(f"a / b = {quotient}")

# 使用条件语句
if a > b:
    print("a 大于 b")
else:
    print("a 不大于 b")

# 使用循环
print("从 1 到 5 的数字：")
for i in range(1, 6):
    print(i)""")
    print(execution.logs)  # outputs 2
elapsed = time.perf_counter() - start_time
print(f"脚本运行时长: {elapsed:.3f} 秒")
