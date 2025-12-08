import requests
import time
import json
from typing import List, Dict, Any

prompts: List[str] = [
    'Where can I buy the latest Labubu figures online?',
    'Which Labubu editions are most collectible right now?',
    'Are there any limited edition Labubu available in Singapore?',
    'How to safely pre-order upcoming Labubu releases?',
    'Which online stores offer the best deals for Labubu collectibles?',
    'What is the average price range for Labubu figures?',
    'How to identify authentic Labubu products?',
    'Are there any seasonal Labubu releases to watch for?',
    'Where to sell or trade Labubu figures second-hand?',
    'Which Labubu figures have increased in value recently?',
    'Are there any online bundles or sets of Labubu collectibles?',
    'Which Labubu editions are considered rare or limited?',
    'How to compare Labubu prices across different online stores?',
    'What are the fan reviews of the newest Labubu releases?',
    'Are there international shipping options for Labubu figures?',
    'Which Chiikawa figures are currently trending among collectors?',
    'How do fans rate the latest Chiikawa series?',
    'What are the rarest Chiikawa editions in the market?',
    'Where to find Chiikawa pre-orders in Japan?',
    'What Chiikawa collaborations or special editions are available?',
    'How to track Chiikawa popularity across social media?',
    'Which Chiikawa characters have a growing fanbase?',
    'Are there any exclusive online-only Chiikawa figures?',
    'How has Chiikawa market value changed recently?',
    'What are the most collectible Chiikawa series for new collectors?',
    'Where can international collectors buy Chiikawa safely?',
    'Which Chiikawa releases are limited and highly sought after?',
    'Are there upcoming Chiikawa events or drops to watch?',
    'How to distinguish authentic Chiikawa figures from counterfeits?',
    'What platforms show price trends and sales for Chiikawa collectibles?',
    'Where can I buy the latest Labubu figures online?',
    'Which Labubu editions are most collectible right now?',
    'Are there any limited edition Labubu available in Singapore?',
    'How to safely pre-order upcoming Labubu releases?',
    'Which online stores offer the best deals for Labubu collectibles?',
    'What is the average price range for Labubu figures?',
    'How to identify authentic Labubu products?',
    'Are there any seasonal Labubu releases to watch for?',
    'Where to sell or trade Labubu figures second-hand?',
    'Which Labubu figures have increased in value recently?',
    'Are there any online bundles or sets of Labubu collectibles?',
    'Which Labubu editions are considered rare or limited?',
    'How to compare Labubu prices across different online stores?',
    'What are the fan reviews of the newest Labubu releases?',
    'Are there international shipping options for Labubu figures?',
    'Which Chiikawa figures are currently trending among collectors?',
    'How do fans rate the latest Chiikawa series?',
    'What are the rarest Chiikawa editions in the market?',
    'Where to find Chiikawa pre-orders in Japan?',
    'What Chiikawa collaborations or special editions are available?',
    'How to track Chiikawa popularity across social media?',
    'Which Chiikawa characters have a growing fanbase?',
    'Are there any exclusive online-only Chiikawa figures?',
    'How has Chiikawa market value changed recently?',
    'What are the most collectible Chiikawa series for new collectors?',
    'Where can international collectors buy Chiikawa safely?',
    'Which Chiikawa releases are limited and highly sought after?',
    'Are there upcoming Chiikawa events or drops to watch?',
    'How to distinguish authentic Chiikawa figures from counterfeits?',
    'What platforms show price trends and sales for Chiikawa collectibles?',
    'Where can I buy the latest Labubu figures online?',
    'Which Labubu editions are most collectible right now?',
    'Are there any limited edition Labubu available in Singapore?',
    'How to safely pre-order upcoming Labubu releases?',
    'Which online stores offer the best deals for Labubu collectibles?',
    'What is the average price range for Labubu figures?',
    'How to identify authentic Labubu products?',
    'Are there any seasonal Labubu releases to watch for?',
    'Where to sell or trade Labubu figures second-hand?',
    'Which Labubu figures have increased in value recently?',
    'Are there any online bundles or sets of Labubu collectibles?',
    'Which Labubu editions are considered rare or limited?',
    'How to compare Labubu prices across different online stores?',
    'What are the fan reviews of the newest Labubu releases?',
    'Are there international shipping options for Labubu figures?',
    'Which Chiikawa figures are currently trending among collectors?',
    'How do fans rate the latest Chiikawa series?',
    'What are the rarest Chiikawa editions in the market?',
    'Where to find Chiikawa pre-orders in Japan?',
    'What Chiikawa collaborations or special editions are available?',
    'How to track Chiikawa popularity across social media?',
    'Which Chiikawa characters have a growing fanbase?',
    'Are there any exclusive online-only Chiikawa figures?',
    'How has Chiikawa market value changed recently?',
    'What are the most collectible Chiikawa series for new collectors?',
    'Where can international collectors buy Chiikawa safely?',
    'Which Chiikawa releases are limited and highly sought after?',
    'Are there upcoming Chiikawa events or drops to watch?',
    'How to distinguish authentic Chiikawa figures from counterfeits?',
    'What platforms show price trends and sales for Chiikawa collectibles?',
]


def send_request(prompt: str) -> Dict[str, Any]:
    """发送 POST 请求并返回响应数据"""
    url = "http://localhost:5173/sampling_tools/api/v1/query"
    payload = {"message": prompt}

    try:
        response = requests.post(url, json=payload, timeout=120)
        return response.json()
    except requests.exceptions.RequestException:
        raise


def save_results(results: List[Dict[str, Any]]):
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def run_requests():
    """运行所有请求并统计结果"""
    total_requests = len(prompts)
    successful_requests = 0
    results: List[Dict[str, Any]] = []

    print(f"开始发送 {total_requests} 个请求")
    print("=" * 50)

    for i, prompt in enumerate(prompts, 1):
        print(f"\n请求 {i}/{total_requests}")
        print(f"Prompt: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")

        result = send_request(prompt)
        results.append(result)

        if result["success"]:
            successful_requests += 1
            print("✓ 成功")
        else:
            print("✗ 失败")
            if "error" in result:
                print(f"  错误: {result['error']}")

        save_results(results)
        print(f"保存结果到 results.json 文件中")


if __name__ == "__main__":
    run_requests()
