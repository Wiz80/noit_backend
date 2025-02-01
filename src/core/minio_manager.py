import os
import json
from io import BytesIO
from minio import Minio
from minio.error import S3Error
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinioManager:
    def __init__(self, bucket_name: str):
        
        use_ssl = os.getenv("MINIO_USE_SSL", "False").strip().lower()

        self.client = Minio(
            endpoint=str(os.getenv("MINIO_ENDPOINT")),
            access_key=str(os.getenv("MINIO_ROOT_USER")),
            secret_key=str(os.getenv("MINIO_ROOT_PASSWORD")),
            secure= use_ssl in ("true", "1", "t", "y", "yes"),
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

    def upload_file(self, object_name: str, file_path: str):
        try:
            self.client.fput_object(self.bucket_name, object_name, file_path)
            logger.info(f"File '{object_name}' uploaded successfully.")
        except S3Error as e:
            logger.error(f"Error uploading file '{object_name}': {e}")
            raise

    def upload_bytes(self, object_name: str, data: bytes, content_type: str = 'application/octet-stream'):
        try:
            self.client.put_object(
                self.bucket_name,
                object_name,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type
            )
            logger.info(f"Bytes object '{object_name}' uploaded successfully.")
        except S3Error as e:
            logger.error(f"Error uploading bytes object '{object_name}': {e}")
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
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            object_list = [obj.object_name for obj in objects]
            logger.info(f"Listed {len(object_list)} objects with prefix '{prefix}'.")
            return object_list
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
            return json.loads(data.decode('utf-8'))
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
