import os
import json
import base64
import colorgram
from PIL import Image
from openai import OpenAI
from app.services.storage.minio_service import MinioService
from sqlalchemy.orm import Session
from app.models.business.competitive_analysis.instagram import InstagramPostInfo, InstagramPostImage, InstagramImageColor, InstagramUserInfo

class InstagramImageAnalyzer:
    def __init__(self, api_key, output_folder="/content/Instagram_Scraper"):
        """
        Initialize InstagramImageAnalyzer class.

        :param api_key: OpenAI API key.
        :param output_folder: Folder to store the output JSON files.
        """
        if not api_key:
            raise ValueError("❌ The OpenAI API key cannot be empty.")

        self.api_key = api_key
        self.output_folder = output_folder
        self.client = OpenAI(api_key=api_key)
        self.minio_service = MinioService(bucket_name="lattice-businesses")

    async def encode_image_from_minio(self, object_name):
        """Encodes an image from MinIO storage to Base64 format."""
        try:
            image_data = self.minio_service.get_object_data(object_name)
            return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            print(f"❌ Error encoding image from MinIO: {str(e)}")
            return None

    def extract_color_palette_from_bytes(self, image_bytes, num_colors=5):
        """Extracts the dominant color palette from image bytes."""
        try:
            from io import BytesIO
            image = Image.open(BytesIO(image_bytes))
            colors = colorgram.extract(image, num_colors)
            return [
                {"rgb": (c.rgb.r, c.rgb.g, c.rgb.b), "proportion": c.proportion}
                for c in colors
            ]
        except Exception as e:
            print(f"❌ Error extracting color palette: {str(e)}")
            return []

    def generate_prompt_expert(self, base64_image):
        """Generates an expert-level prompt for image analysis."""
        return [
            {
                "role": "system",
                "content": "You are an expert in digital marketing, branding, color psychology, and visual analysis. Analyze the image deeply, identifying visual patterns, styles, and branding elements."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image in depth for marketing, branding, and color theory."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ]

    def analyze_image_with_openai(self, base64_image):
        """Sends the image to OpenAI GPT-4o for analysis."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.generate_prompt_expert(base64_image),
                temperature=0.7,
                max_tokens=1200
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Error analyzing the image with OpenAI: {str(e)}"

    async def save_analysis_to_database(self, db: Session, business_id: str, instagram_username: str, analysis_data: dict):
        """
        Save image analysis data to database tables.
        
        :param db: Database session
        :param business_id: Business ID
        :param instagram_username: Instagram username
        :param analysis_data: Image analysis data
        """
        try:
            print(f"💾 Saving image analysis to database for {instagram_username}...")
            
            # Find a post from this account to associate the images with
            # First get the user info record
            user_info = db.query(InstagramUserInfo).filter(
                InstagramUserInfo.username == instagram_username
            ).first()
            
            if not user_info:
                print(f"⚠️ No user found for {instagram_username}. Cannot save image analysis.")
                return
            
            print(f"📋 Found user info for {instagram_username} with ID: {user_info.id}")
            
            
            # Iterate through each analyzed image
            images_processed = 0
            colors_processed = 0
            
            for image_data in analysis_data.get("images_analyzed", []):
                # Create entry in instagram_post_images
                file_name = image_data.get("file_name")
                llm_analysis = image_data.get("gpt4o_analysis")
                
                print(f"📷 Processing image: {file_name}")

                # Then find a post from this user
                post = db.query(InstagramPostInfo).filter(
                    InstagramPostInfo.instagram_user_id == user_info.id,
                    # if the file name has _ in name is a carousel
                    InstagramPostInfo.post_id == file_name.split("_")[0] if "_" in file_name else file_name.split(".")[0]
                ).first()
                
                if not post:
                    print(f"⚠️ No posts found for {instagram_username}. Cannot save image analysis.")
                    return
                    
                print(f"🔗 Found post with ID {post.id} to associate with images")
                
                # Create the post image record
                post_image = InstagramPostImage(
                    post_id=post.id,
                    file_name=file_name,
                    llm_analysis=llm_analysis
                )
                
                db.add(post_image)
                db.flush()  # Get the post_image.id
                images_processed += 1
                
                # Save the color palette
                for color in image_data.get("color_palette", []):
                    rgb = color.get("rgb")
                    if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
                        # Create a color record for each color in the palette
                        image_color = InstagramImageColor(
                            image_id=post_image.id,
                            red=rgb[0],
                            green=rgb[1],
                            blue=rgb[2],
                            proportion=color.get("proportion", 0)
                        )
                        db.add(image_color)
                        colors_processed += 1
            
            # Commit all changes
            db.commit()
            print(f"✅ Successfully saved {images_processed} images and {colors_processed} colors to database for {instagram_username}")
        
        except Exception as e:
            db.rollback()
            print(f"❌ Error saving image analysis to database: {str(e)}")
            # Reraise for debugging
            raise

    async def process_images_from_minio(self, instagram_username):
        """Processes all images in MinIO storage and generates an analysis report."""
        prefix = f"{self.output_folder}/{instagram_username}/images/"
        
        print(f"🔍 Looking for images in MinIO with prefix: {prefix}")
        
        # List objects in MinIO storage with the specified prefix
        image_objects = self.minio_service.list_objects(prefix=prefix)
        
        if not image_objects:
            print(f"⚠️ No images found in MinIO with prefix {prefix}.")
            return None
            
        print(f"📸 Found {len(image_objects)} images to analyze.")
        
        analysis_results = []

        for image_object in image_objects:
            # Handle both string object names and objects with object_name attribute
            object_name = image_object if isinstance(image_object, str) else image_object.object_name
            print(f"🖼️ Processing image: {object_name}")
            
            # Get image data from MinIO
            image_data = self.minio_service.get_object_data(object_name)
            if not image_data:
                print(f"⚠️ Could not retrieve image data for {object_name}")
                continue
                
            # Extract filename from object path
            file_name = os.path.basename(object_name)
            
            # Extract color palette
            palette = self.extract_color_palette_from_bytes(image_data, num_colors=5)
            
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode("utf-8")
            
            # Get AI analysis
            gpt_analysis = self.analyze_image_with_openai(base64_image)

            analysis_results.append({
                "file_name": file_name,
                "object_path": object_name,
                "color_palette": palette,
                "gpt4o_analysis": gpt_analysis
            })

        # Prepare the final report
        report_summary = {
            "summary": "Branding and marketing analysis generated with AI. See each image for details.",
            "images_analyzed": len(analysis_results)
        }

        final_report = {
            "global_analysis": report_summary,
            "images_analyzed": analysis_results
        }

        # Convert report to JSON
        json_data = json.dumps(final_report, indent=4, ensure_ascii=False)
        
        # Upload analysis report to MinIO
        report_object_name = f"{self.output_folder}/{instagram_username}/image_analysis_report.json"
        await self.minio_service.upload_content(
            object_name=report_object_name,
            data=json_data,
            content_type="application/json",
            metadata={"username": instagram_username}
        )

        # Save to database
        #await self.save_analysis_to_database(db, business_id, instagram_username, final_report)

        print(f"☁️ Image analysis report uploaded to MinIO: {report_object_name}")
        return final_report