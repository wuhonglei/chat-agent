"""Object storage service"""

from __future__ import annotations

import asyncio
import types

from qcloud_cos import CosConfig, CosS3Client

from app.core.config import settings


class ObjectStorageService:
    """Object storage service"""

    def __init__(
        self,
        region: str = settings.storage.tencent_cos.region,
        secret_id: str = settings.storage.tencent_cos.secret_id,
        secret_key: str = settings.storage.tencent_cos.secret_key,
        bucket: str = settings.storage.tencent_cos.bucket,
    ) -> None:
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
        self.bucket = bucket
        self.config = config
        self.client = CosS3Client(config)

    def __enter__(self) -> ObjectStorageService:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        if self.client:
            self.client = None

    def get_object_url(self, cos_path: str) -> str:
        url: str = self.client.get_object_url(
            Bucket=self.bucket,
            Key=cos_path,
        )
        return url

    def upload_file_sync(self, local_path: str, cos_path: str) -> str:
        self.client.upload_file(
            Bucket=self.bucket,
            LocalFilePath=local_path,
            Key=cos_path,
            PartSize=1,  # 分块大小(MB)
            MAXThread=10,  # 并发线程数
        )
        return self.get_object_url(cos_path)

    async def upload_file(self, local_path: str, cos_path: str) -> str:
        def _upload() -> str:
            return self.upload_file_sync(local_path, cos_path)

        return await asyncio.to_thread(_upload)
