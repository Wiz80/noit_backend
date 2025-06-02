from app.services.storage.minio_service import MinioService
from app.core.config import settings
import io
from typing import List
from minio.error import S3Error

class MinioBusinessService(MinioService):
    def __init__(self):
        super().__init__(bucket_name=settings.MINIO_BUSINESS_BUCKET)
    
    async def initialize_business_folders(self, business_id: int) -> bool:
        """
        Initialize business folders structure in MinIO
        """
        folders = [
            f"{business_id}/state-of-art/",
            f"{business_id}/business-understanding/",
            f"{business_id}/competitor-analysis/",
            f"{business_id}/resources/images/",
            f"{business_id}/resources/documents/",
            f"{business_id}/resources/data/"
        ]

        try:
            # Create a keep file in each folder to ensure it exists
            for folder in folders:
                self.client.put_object(
                    self.bucket_name,
                    f"{folder}.keep",
                    io.BytesIO(b""),
                    0
                )
            return True
        except S3Error as e:
            raise Exception(f"Error initializing folders: {e}")

    async def list_business_folders(self, business_id: int) -> List[str]:
        """
        List business folders in MinIO
        """
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=f"{business_id}/",
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            raise Exception(f"Error listing folders: {e}")