import os
import json
import pandas as pd
from collections import Counter
from datetime import datetime
from app.models.business.competitive_analysis.instagram import InstagramUserInfo
from app.services.storage.minio_service import MinioService
from app.db.session import SessionLocal
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer

session = SessionLocal()

class InstagramStatistics(BaseInstagramAnalyzer):

    def __init__(self, username, post_limit, image_limit, output_folder):
        super().__init__(username, output_folder, post_limit, image_limit)

    def extract_post_info(self, posts_data: dict):
        """
        Extracts key information from the posts dataset.

        :param posts_file: Path to the JSON file containing posts.
        :return: List of processed posts with relevant engagement metrics.
        """

        if not posts_data:
            return []

        processed_posts = []
        for post in posts_data:
            processed_posts.append({
                "id": post.get("id"),
                "type": post.get("type"),
                "likesCount": post.get("likesCount"),
                "commentsCount": post.get("commentsCount"),
                "timestamp": post.get("timestamp", ""),
                "caption": post.get("caption", "")
            })

        return processed_posts

    def calculate_engagement(self, posts, followers):
        """
        Computes engagement metrics for each post.

        :param posts: List of processed posts.
        :param followers: Number of followers of the user.
        :return: Sorted list of posts by engagement rate.
        """
        for post in posts:
            total_interactions = post["likesCount"] + post["commentsCount"]
            post["engagement_rate"] = (total_interactions / followers) * 100 if followers > 0 else 0
            post["total_interactions"] = total_interactions

            # Convert timestamp to date format
            if post["timestamp"]:
                try:
                    post["post_date"] = datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ").date().isoformat()
                except ValueError:
                    post["post_date"] = None  # Handle invalid timestamps gracefully

        return sorted(posts, key=lambda x: x["engagement_rate"], reverse=True)

    def analyze_post_types(self, posts):
        """
        Analyzes the distribution of post types.

        :param posts: List of processed posts.
        :return: Dictionary mapping post types to their counts.
        """
        post_types = [post.get("type", "Unknown") for post in posts]
        return dict(Counter(post_types))

    def engagement_over_time(self, posts):
        """
        Creates a time-series of engagement rates to analyze trends.

        :param posts: List of processed posts.
        :return: List of engagement trends over time.
        """
        df = pd.DataFrame(posts)
        df["post_date"] = pd.to_datetime(df["post_date"], errors='coerce')
        df.dropna(subset=["post_date"], inplace=True)
        df["post_date"] = df["post_date"].astype(str)  # Convert to string for JSON compatibility
        df = df.groupby("post_date")["engagement_rate"].mean().reset_index()
        return df.to_dict(orient="records")

    def engagement_by_day_of_week(self, posts):
        """
        Computes average engagement rates by day of the week.

        :param posts: List of processed posts.
        :return: Dictionary mapping weekdays to average engagement rates.
        """
        df = pd.DataFrame(posts)
        df["post_date"] = pd.to_datetime(df["post_date"], errors='coerce')
        df.dropna(subset=["post_date"], inplace=True)
        df["day_of_week"] = df["post_date"].dt.day_name()
        return df.groupby("day_of_week")["engagement_rate"].mean().to_dict()
    
    def serialize_posts(self, posts_file):
        try:
            # Si el contenido viene como bytes, primero decodificarlo a string
            if isinstance(posts_file, bytes):
                posts_string = posts_file.decode('utf-8')
            else:
                posts_string = posts_file

            # Parsear el string JSON
            posts_data = json.loads(posts_string)
            
            # Si necesitas volver a convertirlo a string JSON formateado
            formatted_json = json.dumps(posts_data, indent=2, ensure_ascii=False)
            
            return posts_data  # Retorna el objeto Python
            # O return formatted_json  # Si necesitas el string JSON formateado
            
        except json.JSONDecodeError as e:
            print(f"Error decodificando JSON: {e}")
            return None
        except Exception as e:
            print(f"Error inesperado: {e}")
            return None

    async def generate_statistics(self):
        """
        Generates and saves engagement and statistical analyses for a given Instagram username.

        :param username: Instagram username for which statistics will be generated.
        :return: Path of the saved statistics JSON file.
        """
        # Define local file paths
        base_dir = os.path.join(os.getcwd(), f"Instagram_{self.username}")
        os.makedirs(base_dir, exist_ok=True)  # Ensure directory exists

        posts_data = self.serialize_posts(self.minio_service.get_object_data(f"{self.output_folder}/img_posts.json"))

        # Load user and post data
        user_data = session.query(InstagramUserInfo).filter(
            InstagramUserInfo.username == self.username
        ).first()

        posts = self.extract_post_info(posts_data)

        if not user_data or not posts:
            print("❌ Missing necessary data files.")
            return None

        # Extract follower count
        followers = user_data.followers_count

        # Compute statistics
        ranked_posts = self.calculate_engagement(posts, followers)
        post_type_distribution = self.analyze_post_types(posts)
        engagement_trends = self.engagement_over_time(ranked_posts)
        engagement_by_weekday = self.engagement_by_day_of_week(ranked_posts)

        # Aggregate engagement metrics
        total_likes = sum(post["likesCount"] for post in posts)
        total_comments = sum(post["commentsCount"] for post in posts)
        avg_likes_per_post = total_likes / len(posts) if posts else 0
        avg_comments_per_post = total_comments / len(posts) if posts else 0
        avg_engagement_rate = sum(post["engagement_rate"] for post in ranked_posts) / len(ranked_posts) if ranked_posts else 0

        # Structure final report
        statistics = {
            "total_followers": followers,
            "total_posts": len(posts),
            "total_likes": total_likes,
            "total_comments": total_comments,
            "avg_likes_per_post": avg_likes_per_post,
            "avg_comments_per_post": avg_comments_per_post,
            "avg_engagement_rate": avg_engagement_rate,
            "top_posts": ranked_posts[:10],  # Top 10 posts by engagement
            "post_type_distribution": post_type_distribution,
            "engagement_trends": engagement_trends,
            "engagement_by_day_of_week": engagement_by_weekday
        }

        await self.minio_service.upload_content(
            object_name=f"{self.output_folder}/statistics.json",
            data=json.dumps(statistics, indent=4),
            content_type="application/json",
            metadata={
                "business_id": self.output_folder,
                "username": self.username
            }
        )

        print(f"✅ Statistics saved locally: {self.output_folder}/statistics.json")
        return f"{self.output_folder}/statistics.json"