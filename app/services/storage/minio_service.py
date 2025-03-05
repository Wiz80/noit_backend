import os
import json
from io import BytesIO
from minio import Minio
from minio.error import S3Error
import logging
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinioService:
    def __init__(self, 
                 bucket_name: str,
                 endpoint: str = settings.MINIO_ENDPOINT,
                 access_key: str = settings.MINIO_ROOT_USER,
                 secret_key: str = settings.MINIO_ROOT_PASSWORD,
                 region: str =settings.MINIO_REGION):
                 #use_ssl: str = settings.MINIO_USE_SSL
                 
        
        #use_ssl = use_ssl.strip().lower()

        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            #secure= use_ssl in ("true", "1", "t", "y", "yes"),
            region=region
        )
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Bucket '{self.bucket_name}' created successfully.")
            else:
                logger.info(f"Bucket '{self.bucket_name}' already exists.")
        except S3Error as e:
            logger.error(f"Error checking/creating bucket '{self.bucket_name}': {e}")
            raise
    
    async def upload_content(
        self, 
        object_name: str, 
        data: bytes | str, 
        content_type: str = 'application/octet-stream',
        metadata: dict = None
    ):
        """
        Upload content directly from memory with optional metadata
        
        Args:
            object_name: The name/path of the object in MinIO
            data: The content to upload (can be bytes or string)
            content_type: The MIME type of the content
            metadata: Optional metadata dictionary to attach to the object
            
        Returns:
            bool: True if the upload was successful
        """
        try:
            # Convert string to bytes if necessary
            if isinstance(data, str):
                data = data.encode('utf-8')
                
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
                metadata=metadata
            )
            logger.info(f"Content uploaded successfully to '{object_name}'")
            return True
        except S3Error as e:
            logger.error(f"Error uploading content to '{object_name}': {e}")
            raise

    def download_file(self, object_name: str, file_path: str):
        try:
            self.client.fget_object(self.bucket_name, object_name, file_path)
            logger.info(f"File '{object_name}' downloaded successfully.")
        except S3Error as e:
            logger.error(f"Error downloading file '{object_name}': {e}")
            raise

    def get_object_data(self, object_name: str) -> bytes:
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Data for object '{object_name}' retrieved successfully.")
            return data
        except S3Error as e:
            logger.error(f"Error retrieving data for object '{object_name}': {e}")
            raise

    def object_exists(self, object_name: str) -> bool:
        try:
            self.client.stat_object(self.bucket_name, object_name)
            logger.info(f"Object '{object_name}' exists.")
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                logger.info(f"Object '{object_name}' does not exist.")
                return False
            else:
                logger.error(f"Error checking existence of object '{object_name}': {e}")
                raise

    def list_objects(self, prefix: str = "") -> list:
        try:
            objects = list(self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True))
            object_names = [obj.object_name for obj in objects]
            logger.info(f"Listed {len(object_names)} objects with prefix '{prefix}'.")
            return object_names
        except S3Error as e:
            logger.error(f"Error listing objects with prefix '{prefix}': {e}")
            raise

    def delete_object(self, object_name: str):
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"Object '{object_name}' deleted successfully.")
        except S3Error as e:
            logger.error(f"Error deleting object '{object_name}': {e}")
            raise

    def upload_json(self, object_name: str, data: dict):
        json_bytes = json.dumps(data, indent=4).encode('utf-8')
        self.upload_bytes(object_name, json_bytes, content_type='application/json')

    def download_json(self, object_name: str, default_value=None) -> dict:
        try:
            data = self.get_object_data(object_name)
            try:
                # Intento principal: decodificar como UTF-8
                return json.loads(data.decode('utf-8'))
            except UnicodeDecodeError:
                # Si falla, intentar decodificar como latin-1, que es más permisivo
                return json.loads(data.decode('latin-1'))
        except S3Error as e:
            if e.code == 'NoSuchKey' and default_value is not None:
                logger.info(f"JSON object '{object_name}' not found. Returning default value.")
                return default_value
            else:
                logger.error(f"Error downloading JSON object '{object_name}': {e}")
                raise
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON object '{object_name}': {e}")
            raise
