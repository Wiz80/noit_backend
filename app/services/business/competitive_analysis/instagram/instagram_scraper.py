import os
import json
import traceback
from apify_client import ApifyClient
from app.services.storage.minio_service import MinioService
import os
import json
import requests
from apify_client import ApifyClient
from urllib.parse import urlparse, unquote
import re
from app.services.storage.minio_service import MinioService

from datetime import datetime, UTC
import os
import json
from collections import defaultdict
from apify_client import ApifyClient
from app.services.storage.minio_service import MinioService

from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramPostInfo
from app.db.session import SessionLocal
from sqlalchemy import select
from app.services.business.competitive_analysis.instagram.instagram_image_analyzer import InstagramImageAnalyzer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

session = SessionLocal()


class InstagramScraper:
    def __init__(self, api_key, output_folder="/content/Instagram_Scraper", bucket_name="lattice-businesses"):
        """
        Initialize InstagramScraper class.

        :param api_key: Apify API key.
        :param output_folder: Base folder path for storing data in MinIO.
        :param bucket_name: MinIO bucket name to store data.
        """
        if not api_key:
            raise ValueError("❌ The Apify API key cannot be empty.")

        self.api_key = api_key
        self.output_folder = output_folder
        self.client = ApifyClient(api_key)
        
        # Initialize MinIO service
        self.minio_service = MinioService(bucket_name=bucket_name)
        
        logger.info(f"📂 Output folder path set to: {self.output_folder} in MinIO bucket: {bucket_name}")

    async def scrape_instagram_profile(self, usernames):
        """
        Scrapes Instagram profile information and saves the data to MinIO.

        :param usernames: List of Instagram usernames to scrape.
        :return: Profile information dictionary.
        """
        actor_id = "apify/instagram-profile-scraper"
        filename = "instagram_profile.json"

        try:
            # Validate input parameters
            if not usernames or not isinstance(usernames, list):
                raise ValueError("❌ 'usernames' must be a non-empty list of Instagram usernames.")

            logger.info("🚀 Starting Apify client...")

            # Prepare input for the Apify actor
            run_input = {"usernames": usernames}
            logger.info(f"📸 Running actor '{actor_id}' for users: {usernames}")

            # Execute Apify actor
            run = self.client.actor(actor_id).call(run_input=run_input)
            if not run:
                raise RuntimeError("❌ Actor execution failed or returned no results.")

            # Retrieve dataset ID
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                raise ValueError("❌ No dataset generated. Check actor input parameters.")
            logger.info(f"✅ Dataset ID obtained: {dataset_id}")

            # Fetch dataset items
            dataset_items = list(self.client.dataset(dataset_id).iterate_items())
            if not dataset_items:
                raise ValueError("❌ Dataset is empty. No profiles found for the provided usernames.")
            logger.info(f"📄 Found {len(dataset_items)} profiles to save.")


            if dataset_items:
                profile_info = dataset_items[0]

                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{usernames[0]}/{filename}",
                    data=json.dumps(profile_info, indent=4),
                    content_type="application/json",
                    metadata={
                        "business_id": self.output_folder,
                        "username": usernames[0]
                    }
                )

                logger.info(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{usernames[0]}/{filename}")

            return profile_info

        except ValueError as ve:
            logger.error(f"🔍 Validation error: {ve}")
        except RuntimeError as re:
            logger.error(f"🚨 Actor execution error: {re}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            logger.info("🔚 Process completed.")
            
    async def scrape_instagram_posts(self, usernames, results_limit):
        """
        Scrapes Instagram posts from user profiles, saves the data as JSON, and uploads to MinIO.

        :param usernames: List of Instagram usernames to scrape posts from.
        :param results_limit: Maximum number of posts to extract per user.
        :return: Dictionary with usernames and their corresponding dataset IDs.
        """
        actor_id = "apify/instagram-post-scraper"
        dataset_ids = {}

        try:
            # Validate input parameters
            if not usernames or not isinstance(usernames, list):
                raise ValueError("❌ 'usernames' must be a non-empty list of Instagram usernames.")
            if not isinstance(results_limit, int) or results_limit <= 0:
                raise ValueError("❌ 'results_limit' must be a positive integer.")

            logger.info("🚀 Starting Apify client for Instagram posts...")

            # Execute the scraper for each username
            for username in usernames:
                run_input = {
                    "username": [username],
                    "resultsLimit": results_limit
                }
                logger.info(f"📸 Running actor '{actor_id}' for user: {username} with limit: {results_limit} posts.")

                # Execute Apify actor
                run = self.client.actor(actor_id).call(run_input=run_input)
                if not run:
                    raise RuntimeError(f"❌ Actor execution failed for user '{username}'.")

                # Retrieve dataset ID
                dataset_id = run.get("defaultDatasetId")
                if not dataset_id:
                    raise ValueError(f"❌ No dataset generated for user '{username}'.")

                logger.info(f"✅ Dataset ID obtained for '{username}': {dataset_id}")
                dataset_ids[username] = dataset_id

                # Fetch dataset items
                dataset_items = list(self.client.dataset(dataset_id).iterate_items())
                if not dataset_items:
                    logger.warning(f"⚠️ No posts found for user '{username}'.")
                    continue

                logger.info(f"📄 Found {len(dataset_items)} posts for '{username}'.")

                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{usernames[0]}/instagram_posts.json",
                    data=json.dumps(dataset_items, indent=4),
                    content_type="application/json",
                    metadata={
                        "business_id": self.output_folder,
                        "username": usernames
                    }
                )

                logger.info(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{usernames[0]}/instagram_posts.json")

            # Return dataset IDs per user
            return dataset_ids, dataset_items

        except ValueError as ve:
            logger.error(f"🔍 Validation error: {ve}")
        except RuntimeError as re:
            logger.error(f"🚨 Actor execution error: {re}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            logger.info("🔚 Process completed.")

    def get_valid_filename(self, url):
        """
        Generates a valid filename from a URL by removing invalid characters.

        :param url: Image URL.
        :return: Clean and safe filename.
        """
        try:
            path = urlparse(url).path
            filename = os.path.basename(path)
            filename = unquote(filename)
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            if not filename:
                raise ValueError(f"❌ Unable to generate a valid filename for URL: {url}")
            return filename
        except Exception as e:
            raise RuntimeError(f"❌ Error generating filename for '{url}': {e}")

    async def download_images_from_dataset(self, usernames, dataset_id):
        """
        Download images from a dataset.

        :param usernames: list of usernames
        :param dataset_id: ID of the dataset generated by the scraper.
        """
        if not dataset_id:
            raise ValueError("❌ The dataset ID cannot be empty.")

        total_images = 0
        failed_images = 0

        try:
            logger.info(f"📥 Downloading images from dataset ID: {dataset_id}...")
            for item in self.client.dataset(dataset_id).iterate_items():
                post_id = item.get('id')  # ID of the post
                images = item.get('images', [])  # List of image URLs in the post

                if not post_id:
                    logger.warning(f"⚠️ Post without ID : {item['inputUrl']}")
                    continue

                # Check if the post is a carousel
                if len(images) > 1:
                    for index, image_url in enumerate(images):
                        try:
                            # Generate a filename using the post ID and the image index
                            image_name = f"{post_id}_{index + 1}.jpg"

                            # Download the image
                            response = requests.get(image_url, timeout=10)
                            response.raise_for_status()

                            await self.minio_service.upload_content(
                                object_name=f"{self.output_folder}/{usernames[0]}/images/{image_name}",
                                data=response.content,
                                content_type="image/jpeg"
                            )
                            total_images += 1
                            logger.info(f"☁️ Image uploaded to MinIO: {self.output_folder}/{usernames[0]}/images/{image_name}")

                        except requests.exceptions.RequestException as re:
                            logger.error(f"❌ Error downloading '{image_url}': {re}")
                            failed_images += 1
                        except Exception as e:
                            logger.error(f"❌ Unexpected error processing '{image_url}': {e}")
                            failed_images += 1
                else:
                    # Handle posts with a single image
                    image_url = item['displayUrl']
                    try:
                        # Generate a filename using only the post ID
                        image_name = f"{post_id}.jpg"

                        # Download the image
                        response = requests.get(image_url, timeout=10)
                        response.raise_for_status()

                        await self.minio_service.upload_content(
                            object_name=f"{self.output_folder}/{usernames[0]}/images/{image_name}",
                            data=response.content,
                            content_type="image/jpeg"
                        )
                        total_images += 1
                        logger.info(f"☁️ Image uploaded to MinIO: {self.output_folder}/{usernames[0]}/images/{image_name}")

                    except requests.exceptions.RequestException as re:
                        logger.error(f"❌ Error downloading '{image_url}': {re}")
                        failed_images += 1
                    except Exception as e:
                        logger.error(f"❌ Unexpected error processing '{image_url}': {e}")
                        failed_images += 1

            logger.info(f"🎉 Download completed: {total_images} images downloaded successfully.")
            if failed_images > 0:
                logger.warning(f"⚠️ {failed_images} images could not be downloaded.")

        except ValueError as ve:
            logger.error(f"🔍 Validation error: {ve}")
        except RuntimeError as re:
            logger.error(f"🚨 Execution error: {re}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
        finally:
            logger.info("🔚 Image download process completed.")

    async def scrape_instagram_comments(self, usernames, results_limit: int = 10, max_comments: int = 10):
        """
        Extracts comments from Instagram posts using an Apify actor.
        First gets posts from usernames, then extracts comments from those posts.
        Saves the data in a JSON file in MinIO and also returns it as a list of dictionaries.

        :param usernames: List of Instagram usernames to extract posts and comments from.
        :param results_limit: Maximum number of posts to extract comments from.
        :param max_comments: Maximum number of comments per post to extract.
        :return: List of dictionaries with extracted data or None if an error occurs.
        """
        try:
            if not usernames:
                logger.warning("⚠️ No usernames provided for comment extraction.")
                return None

            logger.info(f"🔍 Starting Instagram comments extraction for users: {usernames}")
            logger.info(f"📊 Parameters: posts limit={results_limit}, maximum comments per post={max_comments}")

            # First, get the posts from the usernames
            logger.info(f"📥 Getting posts for users: {usernames}")
            _, posts_data = await self.scrape_instagram_posts(usernames, results_limit)
            
            if not posts_data or len(posts_data) == 0:
                logger.warning(f"⚠️ No posts found for the provided usernames.")
                return None
                
            # Extract post URLs from the posts data
            post_urls = [post.get("url") for post in posts_data if post.get("url")]
            
            if not post_urls:
                logger.warning(f"⚠️ No valid post URLs found in the retrieved posts.")
                return None
                
            logger.info(f"✅ Found {len(post_urls)} posts to extract comments from.")

            # Initialize Apify client
            client = ApifyClient(self.api_key)

            # Define input parameters for the actor
            run_input = {
                "directUrls": post_urls,
                "resultsLimit": max_comments,  # Use max_comments for the comments limit per post
            }

            logger.info(f"🚀 Executing Apify actor for {len(post_urls)} posts.")
            # Execute the actor and wait for completion
            run = client.actor("SbK00X0JYCPblD2wp").call(run_input=run_input)

            if not run:
                logger.warning(f"⚠️ Apify actor execution failed.")
                return None

            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                logger.warning(f"⚠️ No dataset ID received from Apify.")
                return None

            logger.info(f"✅ Apify actor execution completed. Dataset ID: {dataset_id}")

            # Get dataset items
            logger.info(f"📥 Getting dataset items.")
            dataset_items = client.dataset(dataset_id).list_items().items

            if not dataset_items:
                logger.warning(f"⚠️ No data found in the dataset.")
                return None

            logger.info(f"✅ {len(dataset_items)} dataset items retrieved")
            
            # Log comments found per post for debugging
            post_comment_counts = {}
            for item in dataset_items:
                post_url = item.get("postInfo", {}).get("url", "Unknown URL")
                if post_url in post_comment_counts:
                    post_comment_counts[post_url] += 1
                else:
                    post_comment_counts[post_url] = 1
                    
            for idx, (post, count) in enumerate(post_comment_counts.items(), 1):
                logger.info(f"Post {idx}: {post}")
                logger.info(f"Comments retrieved: {count}")
                
            # If no comments were found, try to log more detailed information
            if len(dataset_items) == 0:
                logger.warning("⚠️ No comments found. Potential issues:")
                logger.warning("1. Posts may be too recent or have no comments")
                logger.warning("2. Instagram's API restrictions")
                logger.warning("3. Apify actor configuration needs adjustment")
                logger.warning("4. Post URLs format may be incorrect")
                logger.warning(f"Post URLs being used: {post_urls[:5]}..." if len(post_urls) > 5 else post_urls)

            # Save data to MinIO with appropriate path including username
            if usernames and len(usernames) > 0:
                username = usernames[0]
                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{username}/comments_data.json",
                    data=json.dumps(dataset_items, indent=4),
                    content_type="application/json",
                    metadata={
                        "source": "Instagram",
                        "username": username
                    }
                )
                logger.info(f"✅ Comments data saved to MinIO: {self.output_folder}/{username}/comments_data.json")
            else:
                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/comments_data.json",
                    data=json.dumps(dataset_items, indent=4),
                    content_type="application/json",
                    metadata={
                        "source": "Instagram"
                    }
                )
                logger.info(f"✅ Comments data saved to MinIO: {self.output_folder}/comments_data.json")

            return dataset_items

        except Exception as e:
            logger.error(f"❌ Error extracting comments: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def transform_instagram_comments(self, usernames, raw_data: list):
        """
        Transforms raw Instagram comments data into a structured format grouped by post.

        :param usernames: List of usernames related to the data processing.
        :param raw_data: List containing raw Instagram comment data.
        """
        try:
            if not raw_data:
                logger.warning("⚠️ No data provided for processing.")
                return

            # Dictionary to store posts grouped by postUrl
            posts_dict = defaultdict(lambda: {
                "postUrl": None,
                "postId": None,
                "ownerUsername": None,
                "ownerFullName": None,
                "ownerProfilePicUrl": None,
                "timestamp": None,
                "likesCount": 0,
                "comments": []
            })

            # Iterate through comments and organize by post
            for comment in raw_data:
                # Skip if comment is None or has an error
                if not isinstance(comment, dict) or "error" in comment:
                    logger.warning("⚠️ Skipping invalid or error entry:", comment)
                    continue
                
                # Extract post info
                post_url = comment.get("postUrl")
                post_id = comment.get("id")
                if not post_url or not post_id:
                    logger.warning("⚠️ Skipping comment with missing post URL or ID")
                    continue

                # Populate post information
                posts_dict[post_url]["postUrl"] = post_url
                posts_dict[post_url]["postId"] = post_id
                posts_dict[post_url]["ownerUsername"] = comment.get("ownerUsername")
                posts_dict[post_url]["ownerFullName"] = comment.get("owner", {}).get("full_name")
                posts_dict[post_url]["ownerProfilePicUrl"] = comment.get("ownerProfilePicUrl")
                posts_dict[post_url]["timestamp"] = comment.get("timestamp")
                posts_dict[post_url]["likesCount"] = comment.get("likesCount", 0)

                # Add comment details
                posts_dict[post_url]["comments"].append({
                    "commentId": comment.get("id"),
                    "text": comment.get("text"),
                    "commentatorUsername": comment.get("ownerUsername"),
                    "commentatorProfilePicUrl": comment.get("ownerProfilePicUrl"),
                    "timestamp": comment.get("timestamp"),
                    "likesCount": comment.get("likesCount", 0),
                    "repliesCount": comment.get("repliesCount", 0),
                    "replies": [
                        {
                            "replyId": reply.get("id"),
                            "text": reply.get("text"),
                            "replyUsername": reply.get("ownerUsername"),
                            "replyProfilePicUrl": reply.get("ownerProfilePicUrl"),
                            "timestamp": reply.get("timestamp"),
                            "likesCount": reply.get("likesCount", 0)
                        }
                        for reply in comment.get("replies", [])
                    ]
                })

            # Convert dictionary to list
            structured_data = list(posts_dict.values())

            # Only proceed if we have data to save
            if structured_data:
                object_name = f"{self.output_folder}/{usernames[0]}/processed_comments_data.json"
                await self.minio_service.upload_content(
                    object_name=object_name,
                    data=json.dumps(structured_data, indent=4),
                    content_type="application/json",
                    metadata={"username": usernames[0]}
                )

                logger.info(f"✅ Transformed data saved: {object_name}")
            else:
                logger.warning("⚠️ No structured data to save after processing.")

        except Exception as e:
            logger.error(f"❌ Error processing data: {e}")
            import traceback
            traceback.print_exc()

    async def run_instagram_comments_scraper(self, usernames, result_limit, max_comments):
        """
        Main function to scrape Instagram comments and process the data.

        :param usernames: List of Instagram usernames to scrape.
        :param result_limit: Maximum number of posts to extract.
        :param max_comments: Maximum number of comments per post.
        :return: Dataset ID or identifier for the scraped data.
        """
        try:
            if not usernames or not usernames[0]:
                logger.warning("⚠️ No valid username provided for comment scraping.")
                return None
                
            logger.info(f"🚀 Starting comment scraping for user: {usernames[0]}")
            
            # Step 1: Scrape Instagram Comments - now passes usernames directly
            raw_data = await self.scrape_instagram_comments(
                usernames=usernames, 
                results_limit=result_limit, 
                max_comments=max_comments
            )

            if raw_data:
                logger.info(f"✅ Successfully scraped comments data for {usernames[0]}. Processing...")
                # Step 2: Transform the raw data
                await self.transform_instagram_comments(usernames=usernames, raw_data=raw_data)
                return {"status": "success", "username": usernames[0], "dataset_id": str(hash(str(raw_data)))}
            else:
                logger.warning(f"⚠️ No comment data found for user {usernames[0]}.")
                return {"status": "no_data", "username": usernames[0]}
                
        except Exception as e:
            logger.error(f"❌ Error in comment scraping pipeline: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "username": usernames[0], "error": str(e)}

    async def scrape_instagram_reels(self, usernames, results_limit=10):
        """
        Extracts Instagram reels for specified users and stores results in JSON.

        :param usernames: List of Instagram usernames.
        :param results_limit: Maximum number of reels to extract per user.
        :return: Path to the final JSON file containing extracted reels.
        """

        try:
            if not usernames or not isinstance(usernames, list):
                raise ValueError("❌ 'usernames' must be a non-empty list of Instagram usernames.")
            if results_limit <= 0:
                raise ValueError("❌ 'results_limit' must be a positive integer.")

            logger.info(f"🚀 Starting extraction of reels for users: {usernames}")

            all_reels = {}

            for username in usernames:
                logger.info(f"📸 Extracting reels for user: {username}")
                run_input = {
                    "username": [username],
                    "resultsLimit": results_limit
                }

                run = self.client.actor("apify/instagram-reel-scraper").call(run_input=run_input)
                dataset_id = run.get("defaultDatasetId")

                if not dataset_id:
                    logger.warning(f"⚠️ No dataset generated for '{username}'. Skipping...")
                    continue

                dataset_items = list(self.client.dataset(dataset_id).iterate_items())
                if not dataset_items:
                    logger.warning(f"⚠️ No reels found for '{username}'.")
                    continue

                user_reels = []
                for reel in dataset_items:
                    reel_info = {
                        "reelId": reel.get("id"),
                        "shortCode": reel.get("shortCode"),
                        "videoUrl": reel.get("videoUrl"),
                        "caption": reel.get("caption"),
                        "hashtags": reel.get("hashtags", []),
                        "mentions": reel.get("mentions", []),
                        "likesCount": reel.get("likesCount", 0),
                        "commentsCount": reel.get("commentsCount", 0),
                        "viewsCount": reel.get("playCount", 0),
                        "timestamp": reel.get("timestamp"),
                        "ownerUsername": reel.get("ownerUsername"),
                        "isSponsored": reel.get("isSponsored", False)
                    }
                    user_reels.append(reel_info)

                all_reels[username] = user_reels
                logger.info(f"✅ {len(user_reels)} reels extracted for '{username}'.") 

                json_data = json.dumps(user_reels)
                bytes_data = json_data.encode('utf-8')
                #Store user reels
                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{username}/reels.json",
                    data=bytes_data,
                    content_type="application/json"
                )

                logger.info(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{username}/reels.json")

           
            return user_reels

        except ValueError as ve:
            logger.error(f"🔍 Validation error: {ve}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return None
        finally:
            logger.info("🔚 Reels extraction process completed.")



    async def scrape_instagram_igtv(self, usernames, results_limit=10):
        """
        Extracts IGTV videos for specified Instagram users and stores results in JSON.

        :param usernames: List of Instagram usernames.
        :param results_limit: Maximum number of IGTV videos to extract per user.
        :return: Path to the final JSON file containing extracted IGTV videos.
        """

        try:
            if not usernames or not isinstance(usernames, list):
                raise ValueError("❌ 'usernames' must be a non-empty list of Instagram usernames.")
            if results_limit <= 0:
                raise ValueError("❌ 'results_limit' must be a positive integer.")

            logger.info(f"🚀 Starting extraction of IGTV videos for users: {usernames}")

            all_igtv_videos = {}

            for username in usernames:
                logger.info(f"📸 Extracting IGTV videos for user: {username}")
                run_input = {
                    "usernames": [username],
                    "resultsType": "igtv",
                    "resultsLimit": results_limit
                }

                run = self.client.actor("apify/instagram-profile-scraper").call(run_input=run_input)
                dataset_id = run.get("defaultDatasetId")

                if not dataset_id:
                    logger.warning(f"⚠️ No dataset generated for '{username}'. Skipping...")
                    continue

                dataset_items = list(self.client.dataset(dataset_id).iterate_items())
                if not dataset_items:
                    logger.warning(f"⚠️ No IGTV videos found for '{username}'.")
                    continue

                user_igtv = []
                for video in dataset_items:
                    if video.get("type") == "igtv":
                        video_info = {
                            "igtvId": video.get("id"),
                            "shortCode": video.get("shortCode"),
                            "videoUrl": video.get("videoUrl"),
                            "title": video.get("title"),
                            "caption": video.get("caption"),
                            "hashtags": video.get("hashtags", []),
                            "mentions": video.get("mentions", []),
                            "likesCount": video.get("likesCount", 0),
                            "commentsCount": video.get("commentsCount", 0),
                            "viewsCount": video.get("playCount", 0),
                            "timestamp": video.get("timestamp"),
                            "ownerUsername": video.get("ownerUsername"),
                            "isSponsored": video.get("isSponsored", False)
                        }
                        user_igtv.append(video_info)

                all_igtv_videos[username] = user_igtv
                logger.info(f"✅ {len(user_igtv)} IGTV videos extracted for '{username}'.")
    
                json_data = json.dumps(user_igtv)
                bytes_data = json_data.encode('utf-8')

                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{username}/igtv.json",
                    data=bytes_data,
                    content_type="application/json"
                )
                logger.info(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{username}/igtv.json")


            return all_igtv_videos
        
        except ValueError as ve:
            logger.error(f"🔍 Validation error: {ve}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return None
        finally:
            logger.info("🔚 IGTV extraction process completed.")


    async def run_full_instagram_scraper(self, usernames, results_limit=5, max_comments=10, scraping_job=None, db_session=None):
        """
        Run a full Instagram scraper workflow: profile, posts, comments, images, and analysis.

        :param usernames: List of Instagram usernames to scrape.
        :param results_limit: Maximum number of posts to extract per user.
        :param max_comments: Maximum number of comments to extract per post.
        :param scraping_job: Optional scraping job model to update (if available).
        :param db_session: Optional database session to use.
        :return: Dictionary with the result of the analysis.
        """
        try:
            session = db_session or SessionLocal()
            total_steps = 5  # profile, posts, comments, images, analysis
            current_step = 0
            
            # Update scraping job if provided
            if scraping_job:
                scraping_job.status = "processing"
                scraping_job.started_at = datetime.now(UTC)
                scraping_job.progress = 0
                session.commit()
            
            username = usernames[0] if usernames else None
            if not username:
                raise ValueError("No username provided for scraping")
                
            logger.info(f"Starting full Instagram scraping for {username}")
            
            # Step 1: Scrape Instagram profile
            current_step += 1
            if scraping_job:
                scraping_job.current_step = "Scraping profile information"
                scraping_job.progress = int((current_step / total_steps) * 100)
                session.commit()
            
            profile_info = await self.scrape_instagram_profile(usernames)
            
            if not profile_info:
                error_msg = f"Failed to scrape profile for {username}"
                if scraping_job:
                    scraping_job.status = "failed"
                    scraping_job.error_message = error_msg
                    session.commit()
                raise ValueError(error_msg)
            
            # Store profile in database
            user_info = session.query(InstagramUserInfo).filter_by(username=username).first()
            if not user_info:
                user_info = InstagramUserInfo(
                    username=username,
                    full_name=profile_info.get('fullName', ''),
                    biography=profile_info.get('biography', ''),
                    profile_pic_url=profile_info.get('profilePicUrl', ''),
                    followers_count=profile_info.get('followersCount', 0),
                    follows_count=profile_info.get('followingCount', 0),
                    total_posts=profile_info.get('postsCount', 0),
                    verified=profile_info.get('verified', False),
                    business_category=profile_info.get('businessCategory', ''),
                    external_url=profile_info.get('externalUrl', '')
                )
                session.add(user_info)
                session.commit()
            
            # Step 2: Scrape Instagram posts
            current_step += 1
            if scraping_job:
                scraping_job.current_step = "Scraping posts data"
                scraping_job.progress = int((current_step / total_steps) * 100)
                session.commit()
            
            _, posts_data = await self.scrape_instagram_posts(usernames, results_limit)
            
            # Process and store posts data
            for post_data in posts_data:
                try:
                    post_info = session.query(InstagramPostInfo).filter_by(post_id=post_data.get('id')).first()
                    if not post_info:
                        post_info = InstagramPostInfo(
                            post_id=post_data.get('id', ''),
                            username=username,
                            caption=post_data.get('caption', ''),
                            likes_count=post_data.get('likesCount', 0),
                            comments_count=post_data.get('commentsCount', 0),
                            url=post_data.get('url', ''),
                            image_urls=json.dumps(post_data.get('images', [])),
                            timestamp=post_data.get('timestamp'),
                            location=json.dumps(post_data.get('location', {})),
                            hashtags=json.dumps(post_data.get('hashtags', [])),
                            mentions=json.dumps(post_data.get('mentions', [])),
                            extracted_at=datetime.now(UTC)
                        )
                        session.add(post_info)
                except Exception as post_error:
                    logger.error(f"Error processing post {post_data.get('id')}: {str(post_error)}")
            
            session.commit()
            
            # Step 3: Scrape Instagram comments
            current_step += 1
            if scraping_job:
                scraping_job.current_step = "Scraping comments"
                scraping_job.progress = int((current_step / total_steps) * 100)
                session.commit()
            
            await self.run_instagram_comments_scraper(usernames, results_limit, max_comments)
            
            # Step 4: Download and analyze images
            current_step += 1
            if scraping_job:
                scraping_job.current_step = "Analyzing images"
                scraping_job.progress = int((current_step / total_steps) * 100)
                session.commit()
            
            try:
                logger.info(f"Starting image analysis for {username}")
                
                # Check if images are already downloaded
                image_analyzer = InstagramImageAnalyzer(username=username, output_folder=f"{self.output_folder}/{username}")
                
                # Get list of image objects from MinIO
                image_objects = self.minio_service.list_objects(prefix=f"{self.output_folder}/{username}/images/")
                
                if not image_objects:
                    logger.warning(f"No images found for {username}. Downloading now...")
                    # Step 4a: Download images if they don't exist
                    dataset_ids, _ = await self.scrape_instagram_posts(usernames, results_limit)
                    dataset_id = dataset_ids.get(username)
                    if dataset_id:
                        await self.download_images_from_dataset(usernames, dataset_id)
                        image_objects = self.minio_service.list_objects(prefix=f"{self.output_folder}/{username}/images/")
                
                # Step 4b: Analyze images
                if image_objects:
                    await image_analyzer.analyze_images()
                else:
                    logger.warning(f"No images available for analysis for {username}")
            except Exception as image_error:
                logger.error(f"Error during image analysis: {str(image_error)}")
                # Continue with other steps even if image analysis fails
            
            # Step 5: Complete and finalize
            current_step += 1
            if scraping_job:
                scraping_job.current_step = "Completed"
                scraping_job.progress = 100
                scraping_job.status = "completed"
                scraping_job.completed_at = datetime.now(UTC)
                session.commit()
            
            return {
                "status": "completed",
                "username": username,
                "message": f"Instagram analysis completed for {username}"
            }
        
        except Exception as e:
            error_message = f"Error in full Instagram scraper: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            
            if scraping_job:
                scraping_job.status = "failed"
                scraping_job.error_message = error_message
                session.commit()
            
            return {
                "status": "failed",
                "username": usernames[0] if usernames else None,
                "error": error_message
            }
        finally:
            if db_session is None and session:
                session.close()