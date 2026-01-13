# Please install OpenAI SDK first: `pip3 install openai`
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_API_BASE"))

response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "please help search the weather in the shanghai"},
        # 如果 messages 列表中，存在工具调用时，model 会回退为 deepseek-chat
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_00_i9XOmYzAhm51wf8sKrus8mry",
                    "function": {
                        "arguments": '{"location": "shanghai"}',
                        "name": "get_weather_forecast",
                    },
                    "type": "function",
                    "index": 0,
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_00_i9XOmYzAhm51wf8sKrus8mry",
            "content": '[{"fxDate":"2025-10-25","sunrise":"06:25","sunset":"17:52","moonrise":"09:32","moonset":"20:16","moonPhase":"蛾眉月","moonPhaseIcon":"801","tempMax":"28","tempMin":"21","iconDay":"101","textDay":"多云","ic...":"1-3","windSpeedDay":"3","wind360Night":"45","windDirNight":"东北风","windScaleNight":"1-3","windSpeedNight":"16","precip":"0.0","uvIndex":"6","humidity":"66","pressure":"1008","vis":"25","cloud":"8"}]',
        },
    ],
    stream=False,
)

print(response.model)
print(response.choices[0].message.content)
