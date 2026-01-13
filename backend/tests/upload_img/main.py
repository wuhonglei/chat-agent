import os

from dotenv import load_dotenv
from qcloud_cos import CosConfig, CosS3Client

load_dotenv()

region = os.getenv("STORAGE_REGION")
secret_id = os.getenv("STORAGE_SECRET_ID")
secret_key = os.getenv("STORAGE_SECRET_KEY")
bucket = os.getenv("STORAGE_BUCKET")

config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
client = CosS3Client(config)

# 2. 上传图片文件


def upload_image(local_path, cos_path):
    try:
        response = client.upload_file(
            Bucket=bucket,
            LocalFilePath=local_path,
            Key=cos_path,
            PartSize=1,  # 分块大小(MB)
            MAXThread=10,  # 并发线程数
        )
        print(response)
    except Exception as e:
        print(f"上传失败: {e}")


# 3. 使用示例
if __name__ == "__main__":
    # 上传本地图片到COS
    upload_image("./imgs/1.png", "images/1.png")  # 本地路径和COS路径
