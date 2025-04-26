import os
import json
import re
from app.services.storage.minio_service import MinioService

class BaseInstagramAnalyzer:
    def __init__(self, username: str, output_folder: str, post_limit: int = 3, image_limit: int = 3):
        self.api_key = os.getenv("APIFY_API_KEY")
        self.username = username
        self.output_folder = output_folder
        self.post_limit = post_limit
        self.image_limit = image_limit
        self.minio_service = MinioService(bucket_name="lattice-businesses")

    async def load_comments(self):
        """Loads Instagram comments from MinIO."""
        try:
            object_path = f"{self.output_folder}/processed_comments_data.json"
            comments_json = self.minio_service.get_object_data(object_path)
            comments_data = json.loads(comments_json)

            comments = []
            for post in comments_data:
                for comment in post.get("comments", []):
                    comments.append(comment["commentText"])

            return comments
        except Exception as e:
            print(f"❌ Error loading comments: {e}")
            return []

    def clean_text(self, text: str) -> str:
        """Cleans text by removing mentions, hashtags, URLs, and special characters."""
        text = text.lower()
        text = re.sub(r"http\S+|www\S+|https\S+", "", text)
        text = re.sub(r"\@\w+|\#", "", text)
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\d+", "", text)
        return text.strip()