import os
from apify_client import ApifyClient
import json
from collections import Counter
from app.services.storage.minio_service import MinioService
from app.models.business.competitive_analysis.instagram import InstagramUserInfo
from app.db.session import SessionLocal

session = SessionLocal()


class InstagramUserScraper:

    def __init__(self, username, post_limit, image_limit, output_folder):
        self.api_key = os.getenv("APIFY_API_KEY")
        self.username = username
        self.minio_service = MinioService(bucket_name="lattice-businesses")
        self.post_limit = post_limit
        self.image_limit = image_limit
        self.output_folder = output_folder

    async def scrape_instagram_profile(self):
        """
        Scrapes an Instagram profile using Apify and saves the raw data as a JSON file locally.
        The raw data is also returned to avoid reloading it from disk later.

        :param self.username: Instagram self.username to scrape.
        :param api_key: Apify API key.
        :return: Tuple containing the path of the raw JSON file and the scraped data as a dictionary.
        """
        # Define local output directory and file path
        output_dir = os.path.join(os.getcwd(), f"Instagram_{self.username}")
        output_path = os.path.join(output_dir, f"Basic_data_{self.username}.json")

        try:
            # Ensure the directory exists
            os.makedirs(output_dir, exist_ok=True)

            # Initialize Apify Client
            client = ApifyClient(self.api_key)

            # Define input parameters for the Apify Instagram Profile Scraper
            run_input = {
                "usernames": [self.username],
                "resultsLimit": 1,
                "scrapePosts": True  # Fetching posts to count types
            }

            # Execute the scraper
            run = client.actor("apify/instagram-profile-scraper").call(run_input=run_input)

            # Retrieve results from the dataset
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
            if dataset_items:
                profile_info = dataset_items[0]

                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/basic_data_{self.username}.json",
                    data=json.dumps(profile_info, indent=4),
                    content_type="application/json",
                    metadata={
                        "business_id": self.output_folder,
                        "username": self.username
                    }
                )

                print(f"✅ Raw data saved locally: {output_path}")
                return output_path, profile_info  # Return file path and scraped data for further processing
            else:
                print("⚠️ No data found for this username.")
                return None, None

        except Exception as e:
            print(f"❌ Error scraping data: {e}")
            return None, None

    async def process_instagram_data(self, data: dict, output_file: str):
        """
        Processes Instagram user data and extracts key information along with post type counts.
        Data is passed directly as a parameter instead of reading from a file.

        :param data: Dictionary containing Instagram profile data.
        :param output_file: Path to save the processed JSON output.
        """
        try:
            if not data:
                print("⚠️ No data provided for processing.")
                return

            # Extract essential user details
            user_data = {
                "id": data.get("id"),
                "username": data["username"],
                "full_name": data.get("fullName", ""),
                "biography": data.get("biography", ""),
                "followers_count": data.get("followersCount", 0),
                "follows_count": data.get("followsCount", 0),
                "verified": data.get("verified", False),
                "business_category": data.get("businessCategoryName"),
                "external_url": data.get("externalUrl", ""),
                "profile_pic_url": data.get("profilePicUrlHD") or data.get("profilePicUrl", ""),
                "total_posts": data.get("postsCount", 0),
                "igtv_videos": data.get("igtvVideoCount", 0),
                "highlight_reels": data.get("highlightReelCount", 0),
                "competitor_id": "bcd5cd06-e2d1-49d1-8802-131cea1e2247"  # Placeholder for competitor ID
            }

            # # Count post types
            # post_types = [post.get("type", "Unknown") for post in data.get("latestPosts", [])]
            # post_counts = dict(Counter(post_types))

            # # Construct final structured output
            # processed_data = {
            #     "UserInfo": user_info,
            #     "PostTypeCounts": post_counts
            # }

            try:
                # Usar bulk_insert_mappings aunque sea un solo registro para mantener consistencia
                session.bulk_insert_mappings(InstagramUserInfo, [user_data])
                session.commit()
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

            # # Save processed data to a new JSON file locally
            # with open(output_file, "w", encoding="utf-8") as f:
            #     json.dump(processed_data, f, indent=4, ensure_ascii=False)

            # print(f"✅ Processed data saved locally: {output_file}")

        except Exception as e:
            print(f"❌ Error processing data: {e}")

    async def basic_data_scraper(self):
        """
        Main function to execute the Instagram scraper and process data.

        :param self.username: Instagram self.username to scrape.
        :param api_key: Apify API key.
        """
        # Define local paths
        local_dir = os.path.join(os.getcwd(), f"Instagram_{self.username}")
        processed_data_path = os.path.join(local_dir, f"Processed_basic_data_{self.username}.json")

        # Step 1: Scrape Instagram Profile
        raw_file, raw_data = await self.scrape_instagram_profile()

        # Step 2: Process and save structured data if scraping was successful
        if raw_data:
            await self.process_instagram_data(raw_data, processed_data_path)