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

from datetime import datetime
import os
import json
from collections import defaultdict
from apify_client import ApifyClient
from app.services.storage.minio_service import MinioService

from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramPostInfo
from app.db.session import SessionLocal
from sqlalchemy import select
from app.services.business.competitive_analysis.instagram.instagram_image_analyzer import InstagramImageAnalyzer

session = SessionLocal()


class InstagramScraper:
    def __init__(self, api_key, output_folder="/content/Instagram_Scraper"):
        """
        Initialize InstagramScraper class.

        :param api_key: Apify API key.
        :param output_folder: Folder to store the output JSON files.
        """
        if not api_key:
            raise ValueError("❌ The Apify API key cannot be empty.")

        self.api_key = api_key
        self.output_folder = output_folder
        self.client = ApifyClient(api_key)
        self.minio_service = MinioService(bucket_name="lattice-businesses")

        # Ensure the output folder exists
        os.makedirs(self.output_folder, exist_ok=True)
        print(f"📂 Output folder set to: {self.output_folder}")

    async def scrape_instagram_profile(self, usernames):
        """
        Scrapes Instagram profile information and saves the data as a JSON file.

        :param usernames: List of Instagram usernames to scrape.
        :return: Path to the saved JSON file.
        """
        actor_id = "apify/instagram-profile-scraper"
        filename = "instagram_profile.json"

        try:
            # Validate input parameters
            if not usernames or not isinstance(usernames, list):
                raise ValueError("❌ 'usernames' must be a non-empty list of Instagram usernames.")

            print("🚀 Starting Apify client...")

            # Prepare input for the Apify actor
            run_input = {"usernames": usernames}
            print(f"📸 Running actor '{actor_id}' for users: {usernames}")

            # Execute Apify actor
            run = self.client.actor(actor_id).call(run_input=run_input)
            if not run:
                raise RuntimeError("❌ Actor execution failed or returned no results.")

            # Retrieve dataset ID
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                raise ValueError("❌ No dataset generated. Check actor input parameters.")
            print(f"✅ Dataset ID obtained: {dataset_id}")

            # Fetch dataset items
            dataset_items = list(self.client.dataset(dataset_id).iterate_items())
            if not dataset_items:
                raise ValueError("❌ Dataset is empty. No profiles found for the provided usernames.")
            print(f"📄 Found {len(dataset_items)} profiles to save.")


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

                print(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{usernames[0]}/{filename}")

            return profile_info

        except ValueError as ve:
            print(f"🔍 Validation error: {ve}")
        except RuntimeError as re:
            print(f"🚨 Actor execution error: {re}")
        except FileNotFoundError as fe:
            print(f"⚠️ File not found error: {fe}")
        except IOError as ioe:
            print(f"📂 Input/output error: {ioe}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        finally:
            print("🔚 Process completed.")

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

            print("🚀 Starting Apify client for Instagram posts...")

            # Execute the scraper for each username
            for username in usernames:
                run_input = {
                    "username": [username],
                    "resultsLimit": results_limit
                }
                print(f"📸 Running actor '{actor_id}' for user: {username} with limit: {results_limit} posts.")

                # Execute Apify actor
                run = self.client.actor(actor_id).call(run_input=run_input)
                if not run:
                    raise RuntimeError(f"❌ Actor execution failed for user '{username}'.")

                # Retrieve dataset ID
                dataset_id = run.get("defaultDatasetId")
                if not dataset_id:
                    raise ValueError(f"❌ No dataset generated for user '{username}'.")

                print(f"✅ Dataset ID obtained for '{username}': {dataset_id}")
                dataset_ids[username] = dataset_id

                # Fetch dataset items
                dataset_items = list(self.client.dataset(dataset_id).iterate_items())
                if not dataset_items:
                    print(f"⚠️ No posts found for user '{username}'.")
                    continue

                print(f"📄 Found {len(dataset_items)} posts for '{username}'.")

                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{usernames[0]}/instagram_posts.json",
                    data=json.dumps(dataset_items, indent=4),
                    content_type="application/json",
                    metadata={
                        "business_id": self.output_folder,
                        "username": usernames
                    }
                )

                print(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{usernames[0]}/instagram_posts.json")

            # Return dataset IDs per user
            return dataset_ids, dataset_items

        except ValueError as ve:
            print(f"🔍 Validation error: {ve}")
        except RuntimeError as re:
            print(f"🚨 Actor execution error: {re}")
        except FileNotFoundError as fe:
            print(f"⚠️ File not found error: {fe}")
        except IOError as ioe:
            print(f"📂 Input/output error: {ioe}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        finally:
            print("🔚 Process completed.")



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
            print(f"📥 Downloading images from dataset ID: {dataset_id}...")
            for item in self.client.dataset(dataset_id).iterate_items():
                post_id = item.get('id')  # ID of the post
                images = item.get('images', [])  # List of image URLs in the post

                if not post_id:
                    print(f"⚠️ Post without ID : {item['inputUrl']}")
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
                            print(f"☁️ Image uploaded to MinIO: {self.output_folder}/{usernames[0]}/images/{image_name}")

                        except requests.exceptions.RequestException as re:
                            print(f"❌ Error downloading '{image_url}': {re}")
                            failed_images += 1
                        except Exception as e:
                            print(f"❌ Unexpected error processing '{image_url}': {e}")
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
                        print(f"☁️ Image uploaded to MinIO: {self.output_folder}/{usernames[0]}/images/{image_name}")

                    except requests.exceptions.RequestException as re:
                        print(f"❌ Error downloading '{image_url}': {re}")
                        failed_images += 1
                    except Exception as e:
                        print(f"❌ Unexpected error processing '{image_url}': {e}")
                        failed_images += 1

            print(f"🎉 Download completed: {total_images} images downloaded successfully.")
            if failed_images > 0:
                print(f"⚠️ {failed_images} images could not be downloaded.")

        except ValueError as ve:
            print(f"🔍 Validation error: {ve}")
        except RuntimeError as re:
            print(f"🚨 Execution error: {re}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        finally:
            print("🔚 Image download process completed.")

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
                print("⚠️ No usernames provided for comment extraction.")
                return None

            print(f"🔍 Starting Instagram comments extraction for users: {usernames}")
            print(f"📊 Parameters: posts limit={results_limit}, maximum comments per post={max_comments}")

            # First, get the posts from the usernames
            print(f"📥 Getting posts for users: {usernames}")
            _, posts_data = await self.scrape_instagram_posts(usernames, results_limit)
            
            if not posts_data or len(posts_data) == 0:
                print(f"⚠️ No posts found for the provided usernames.")
                return None
                
            # Extract post URLs from the posts data
            post_urls = [post.get("url") for post in posts_data if post.get("url")]
            
            if not post_urls:
                print(f"⚠️ No valid post URLs found in the retrieved posts.")
                return None
                
            print(f"✅ Found {len(post_urls)} posts to extract comments from.")

            # Initialize Apify client
            client = ApifyClient(self.api_key)

            # Define input parameters for the actor
            run_input = {
                "directUrls": post_urls,
                "resultsLimit": max_comments,  # Use max_comments for the comments limit per post
            }

            print(f"🚀 Executing Apify actor for {len(post_urls)} posts.")
            # Execute the actor and wait for completion
            run = client.actor("SbK00X0JYCPblD2wp").call(run_input=run_input)

            if not run:
                print(f"⚠️ Apify actor execution failed.")
                return None

            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                print(f"⚠️ No dataset ID received from Apify.")
                return None

            print(f"✅ Apify actor execution completed. Dataset ID: {dataset_id}")

            # Get dataset items
            print(f"📥 Getting dataset items.")
            dataset_items = client.dataset(dataset_id).list_items().items

            if not dataset_items:
                print(f"⚠️ No data found in the dataset.")
                return None

            print(f"✅ {len(dataset_items)} dataset items retrieved")
            
            # Log comments found per post for debugging
            post_comment_counts = {}
            for item in dataset_items:
                post_url = item.get("postInfo", {}).get("url", "Unknown URL")
                if post_url in post_comment_counts:
                    post_comment_counts[post_url] += 1
                else:
                    post_comment_counts[post_url] = 1
                    
            for idx, (post, count) in enumerate(post_comment_counts.items(), 1):
                print(f"Post {idx}: {post}")
                print(f"Comments retrieved: {count}")
                
            # If no comments were found, try to log more detailed information
            if len(dataset_items) == 0:
                print("⚠️ No comments found. Potential issues:")
                print("1. Posts may be too recent or have no comments")
                print("2. Instagram's API restrictions")
                print("3. Apify actor configuration needs adjustment")
                print("4. Post URLs format may be incorrect")
                print(f"Post URLs being used: {post_urls[:5]}..." if len(post_urls) > 5 else post_urls)

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
                print(f"✅ Comments data saved to MinIO: {self.output_folder}/{username}/comments_data.json")
            else:
                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/comments_data.json",
                    data=json.dumps(dataset_items, indent=4),
                    content_type="application/json",
                    metadata={
                        "source": "Instagram"
                    }
                )
                print(f"✅ Comments data saved to MinIO: {self.output_folder}/comments_data.json")

            return dataset_items

        except Exception as e:
            print(f"❌ Error extracting comments: {e}")
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
                print("⚠️ No data provided for processing.")
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
                    print("⚠️ Skipping invalid or error entry:", comment)
                    continue
                
                # Extract post info
                post_url = comment.get("postUrl")
                post_id = comment.get("id")
                if not post_url or not post_id:
                    print("⚠️ Skipping comment with missing post URL or ID")
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

                print(f"✅ Transformed data saved: {object_name}")
            else:
                print("⚠️ No structured data to save after processing.")

        except Exception as e:
            print(f"❌ Error processing data: {e}")
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
                print("⚠️ No valid username provided for comment scraping.")
                return None
                
            print(f"🚀 Starting comment scraping for user: {usernames[0]}")
            
            # Step 1: Scrape Instagram Comments - now passes usernames directly
            raw_data = await self.scrape_instagram_comments(
                usernames=usernames, 
                results_limit=result_limit, 
                max_comments=max_comments
            )

            if raw_data:
                print(f"✅ Successfully scraped comments data for {usernames[0]}. Processing...")
                # Step 2: Transform the raw data
                await self.transform_instagram_comments(usernames=usernames, raw_data=raw_data)
                return {"status": "success", "username": usernames[0], "dataset_id": str(hash(str(raw_data)))}
            else:
                print(f"⚠️ No comment data found for user {usernames[0]}.")
                return {"status": "no_data", "username": usernames[0]}
                
        except Exception as e:
            print(f"❌ Error in comment scraping pipeline: {e}")
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

            print(f"🚀 Starting extraction of reels for users: {usernames}")

            all_reels = {}

            for username in usernames:
                print(f"📸 Extracting reels for user: {username}")
                run_input = {
                    "username": [username],
                    "resultsLimit": results_limit
                }

                run = self.client.actor("apify/instagram-reel-scraper").call(run_input=run_input)
                dataset_id = run.get("defaultDatasetId")

                if not dataset_id:
                    print(f"⚠️ No dataset generated for '{username}'. Skipping...")
                    continue

                dataset_items = list(self.client.dataset(dataset_id).iterate_items())
                if not dataset_items:
                    print(f"⚠️ No reels found for '{username}'.")
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
                print(f"✅ {len(user_reels)} reels extracted for '{username}'.") 

                json_data = json.dumps(user_reels)
                bytes_data = json_data.encode('utf-8')
                #Store user reels
                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{username}/reels.json",
                    data=bytes_data,
                    content_type="application/json"
                )

                print(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{username}/reels.json")

           
            return user_reels

        except ValueError as ve:
            print(f"🔍 Validation error: {ve}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return None
        finally:
            print("🔚 Reels extraction process completed.")



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

            print(f"🚀 Starting extraction of IGTV videos for users: {usernames}")

            all_igtv_videos = {}

            for username in usernames:
                print(f"📸 Extracting IGTV videos for user: {username}")
                run_input = {
                    "usernames": [username],
                    "resultsType": "igtv",
                    "resultsLimit": results_limit
                }

                run = self.client.actor("apify/instagram-profile-scraper").call(run_input=run_input)
                dataset_id = run.get("defaultDatasetId")

                if not dataset_id:
                    print(f"⚠️ No dataset generated for '{username}'. Skipping...")
                    continue

                dataset_items = list(self.client.dataset(dataset_id).iterate_items())
                if not dataset_items:
                    print(f"⚠️ No IGTV videos found for '{username}'.")
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
                print(f"✅ {len(user_igtv)} IGTV videos extracted for '{username}'.")
    
                json_data = json.dumps(user_igtv)
                bytes_data = json_data.encode('utf-8')

                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/{username}/igtv.json",
                    data=bytes_data,
                    content_type="application/json"
                )
                print(f"☁️ JSON file uploaded to MinIO: {self.output_folder}/{username}/igtv.json")


            return all_igtv_videos
        
        except ValueError as ve:
            print(f"🔍 Validation error: {ve}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return None
        finally:
            print("🔚 IGTV extraction process completed.")


    async def run_full_instagram_scraper(self, usernames, results_limit=5, max_comments=10, scraping_job=None, db_session=None):
        """
        Runs the complete Instagram scraping pipeline for profiles, posts, images, comments, reels, and IGTV.

        :param usernames: List of Instagram usernames.
        :param results_limit: Maximum number of posts, reels, and IGTV videos to extract per user.
        :param max_comments: Maximum number of comments to extract per post.
        :param scraping_job: Optional InstagramScrapingJob record to update during the process
        :param db_session: Optional database session for updating the scraping job
        """
        try:
            print("🚀 Starting full Instagram scraping pipeline...")

            # Update scraping job if provided
            if scraping_job and db_session:
                scraping_job.status = "processing"
                scraping_job.results_limit = results_limit
                scraping_job.max_comments = max_comments
                db_session.commit()

            # 1. Scrape Instagram Profiles
            for username in usernames:
                print(f"📸 Scraping profile for user: {username}")

                # Update scraping job if provided
                if scraping_job and db_session:
                    scraping_job.profile_status = "processing"
                    db_session.commit()

                # Check if the profile already exists in the database
                instagram_user = session.query(InstagramUserInfo).filter_by(username=username).first()

                profile_data = await self.scrape_instagram_profile([username])

                # Update scraping job with profile dataset ID if provided
                if scraping_job and db_session and profile_data:
                    scraping_job.dataset_id_profile = profile_data.get("id", "")
                    scraping_job.profile_status = "completed"
                    db_session.commit()

                if instagram_user:
                    instagram_user.full_name = profile_data["fullName"]
                    instagram_user.biography = profile_data.get("biography", "")
                    instagram_user.followers_count = profile_data["followersCount"]
                    instagram_user.follows_count = profile_data["followsCount"]
                    instagram_user.verified = profile_data["verified"]
                    instagram_user.business_category = profile_data.get("businessCategoryName", "")
                    instagram_user.external_url = profile_data.get("externalUrl", "")
                    instagram_user.profile_pic_url = profile_data.get("profilePicUrl", "")
                    instagram_user.total_posts = profile_data["postsCount"]
                    instagram_user.igtv_videos = profile_data.get("igtvVideoCount", 0)
                    instagram_user.highlight_reels = profile_data.get("highlightReelCount", 0)
                
                    session.commit()
                    print(f"✅ Perfil de Instagram actualizado para: {profile_data['username']}")
                else:
                    # Store instance in database
                    instagram_user = InstagramUserInfo(
                    username=profile_data["username"],
                    full_name=profile_data["fullName"],
                    biography=profile_data.get("biography", ""),
                    followers_count=profile_data["followersCount"],
                    follows_count=profile_data["followsCount"],
                    verified=profile_data["verified"],
                    business_category=profile_data.get("businessCategoryName", ""),
                    external_url=profile_data.get("externalUrl", ""),
                    profile_pic_url=profile_data.get("profilePicUrl", ""),
                    total_posts=profile_data["postsCount"],
                    igtv_videos=profile_data.get("igtvVideoCount", 0),
                    highlight_reels=profile_data.get("highlightReelCount", 0),
                    address_city_name = profile_data.get("businessAddress", {}).get("city_name"),
                    address_lat = profile_data.get("businessAddress", {}).get("latitude"),
                    address_lng = profile_data.get("businessAddress", {}).get("longitude")
                    )
                    
                    session.add(instagram_user)
                    session.commit()
                    print(f"✅ Nuevo perfil de Instagram guardado para: {profile_data['username']}")


            # 2. Scrape Instagram Posts and Images
            # Update scraping job if provided
            if scraping_job and db_session:
                scraping_job.posts_status = "processing"
                db_session.commit()

            dataset_ids, post_data = await self.scrape_instagram_posts(usernames, results_limit)

            # Update scraping job with posts dataset ID if provided
            if scraping_job and db_session and dataset_ids:
                scraping_job.dataset_id_posts = dataset_ids.get(usernames[0], "")
                scraping_job.posts_status = "completed"
                db_session.commit()

            for post in post_data:
                existing_post = session.execute(
                    select(InstagramPostInfo).where(InstagramPostInfo.id_post == post["id"])
                )
                existing_post = existing_post.scalars().first()

                post_timestamp = datetime.fromisoformat(post["timestamp"].replace('Z', '+00:00'))
        
                # Procesar menciones (si las hay)
                mentions = []
                if post.get("mentions"):
                    mentions = post["mentions"]
                
                if existing_post:
                    # Actualizar post existente
                    existing_post.caption = post.get("caption", "")
                    existing_post.hashtags = post.get("hashtags", [])
                    existing_post.mentions = mentions
                    existing_post.likes_count = post.get("likesCount", 0)
                    existing_post.comments_count = post.get("commentsCount", 0)
                    existing_post.is_sponsored = post.get("isSponsored", False)
                    existing_post.post_timestamp = post_timestamp
                    existing_post.type_post = post.get("type", "")
                    existing_post.url_post = post.get("url", "")
                    
                    session.commit()
                    print(f"✅ Post de Instagram actualizado: {post['shortCode']}")

                else:
                    # Crear nuevo post
                    new_instagram_post = InstagramPostInfo(
                        id_post=post["id"],
                        instagram_user_id=instagram_user.id,
                        caption=post.get("caption", ""),
                        hashtags=post.get("hashtags", []),
                        mentions=mentions,
                        likes_count=post.get("likesCount", 0),
                        comments_count=post.get("commentsCount", 0),
                        is_sponsored=post.get("isSponsored", False),
                        post_timestamp=post_timestamp,
                        type_post=post.get("type", ""),
                        url_post=post.get("url", "")
                    )
                    
                    session.add(new_instagram_post)
                    session.commit()
                    session.refresh(new_instagram_post)
                    print(f"✅ Nuevo post de Instagram guardado: {post['shortCode']}")

            print(f"📊 Dataset IDs generated: {dataset_ids}")

            # 3. Download Images for Each Dataset ID
            for username, dataset_id in dataset_ids.items():
                print(f"📥 Downloading images for user: {username} with dataset ID: {dataset_id}")
                await self.download_images_from_dataset(usernames=[username], dataset_id=dataset_id)

            # 3.5 NEW STEP: Analyze images with InstagramImageAnalyzer
            # Update scraping job if provided
            if scraping_job and db_session:
                scraping_job.image_analysis_status = "processing"
                db_session.commit()
            
            print("🧠 Starting image analysis...")
            for username in usernames:
                try:
                    # Initialize the image analyzer
                    image_analyzer = InstagramImageAnalyzer(api_key=os.getenv("OPENAI_API_KEY"), output_folder=self.output_folder)
                    
                    # Process images from MinIO
                    analysis_results = await image_analyzer.process_images_from_minio(username)
                    
                    if analysis_results:
                        print(f"✅ Image analysis completed for {username}. Analyzed {len(analysis_results['images_analyzed'])} images.")
                    else:
                        print(f"⚠️ No images were analyzed for {username}.")
                        
                    # Update scraping job with image analysis status if provided
                    if scraping_job and db_session:
                        scraping_job.image_analysis_status = "completed"
                        db_session.commit()
                except Exception as e:
                    print(f"❌ Error during image analysis for {username}: {e}")
                    # Update scraping job with error status if provided
                    if scraping_job and db_session:
                        scraping_job.image_analysis_status = "failed"
                        scraping_job.error_message = f"Image analysis error: {str(e)}"
                        db_session.commit()

            # 4. Scrape and Process Instagram Comments
            # Update scraping job if provided
            if scraping_job and db_session:
                scraping_job.comments_status = "processing"
                db_session.commit()

            for username in usernames:
                print(f"💬 Scraping comments for user: {username}")
                # Call the comments scraper with the correct parameters
                comments_data = await self.run_instagram_comments_scraper(
                    usernames=[username], 
                    result_limit=results_limit, 
                    max_comments=max_comments
                )
                
                # Update scraping job with comments dataset ID if provided
                if scraping_job and db_session:
                    scraping_job.dataset_id_comments = str(comments_data)
                    scraping_job.comments_status = "completed"
                    db_session.commit()

            # 5. Scrape Instagram Reels
            # Update scraping job if provided
            if scraping_job and db_session:
                scraping_job.reels_status = "processing"
                db_session.commit()

            print("🎬 Scraping Instagram reels...")
            reels_data = await self.scrape_instagram_reels(usernames, results_limit)
            
            # Update scraping job with reels dataset ID if provided
            if scraping_job and db_session:
                scraping_job.dataset_id_reels = str(reels_data)
                scraping_job.reels_status = "completed"
                db_session.commit()

            if reels_data:
                print(f"🎉 Reels extraction completed.")
            else:
                print("⚠️ No reels extracted.")

            # 6. Scrape Instagram IGTV
            # Update scraping job if provided
            if scraping_job and db_session:
                scraping_job.igtv_status = "processing"
                db_session.commit()

            print("📹 Scraping Instagram IGTV videos...")
            igtv_data = await self.scrape_instagram_igtv(usernames, results_limit)
            
            # Update scraping job with IGTV dataset ID if provided
            if scraping_job and db_session:
                scraping_job.dataset_id_igtv = str(igtv_data)
                scraping_job.igtv_status = "completed"
                db_session.commit()

            if igtv_data:
                print(f"🎉 IGTV extraction completed.")
            else:
                print("⚠️ No IGTV videos extracted.")

            # Mark the entire job as completed if provided
            if scraping_job and db_session:
                scraping_job.status = "completed"
                scraping_job.completed_at = datetime.utcnow()
                db_session.commit()

            print("✅ Full Instagram scraping pipeline completed successfully.")
            return {"status": "completed", "message": "Instagram scraping completed successfully"}

        except Exception as e:
            print(f"❌ Unexpected error during full pipeline execution: {e}")
            
            # Mark the job as failed if provided
            if scraping_job and db_session:
                scraping_job.status = "failed"
                scraping_job.error_message = str(e)
                db_session.commit()
                
            return {"status": "failed", "error": str(e)}
        finally:
            print("🔚 Full Instagram scraping process completed.")