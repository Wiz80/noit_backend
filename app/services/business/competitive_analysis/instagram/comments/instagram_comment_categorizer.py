import os
import json
import tiktoken
from collections import defaultdict
from openai import OpenAI
from app.services.storage.minio_service import MinioService
from apify_client import ApifyClient
from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramPostInfo, InstagramComment, InstagramCommentCategory
from app.db.session import SessionLocal
import aisuite as ai
from dotenv import load_dotenv
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer

load_dotenv()

# Initialize database session
session = SessionLocal()

class InstagramCommentCategorizer(BaseInstagramAnalyzer):
    def __init__(self, username, output_folder, provider, model):
        super().__init__(username, output_folder)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.provider = provider
        self.model = model
        self._init_clients()
            
    def _init_clients(self):
        """Initialize LLM clients"""
        if self.provider in ["openai", "claude"]:
            self.client = ai.Client()
        elif self.provider == "deepseek":
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
        else:
            raise ValueError("Invalid validator model specified")


    def count_tokens(self, text):
        """Counts the number of tokens in a given text using OpenAI's tokenizer."""
        return len(self.tokenizer.encode(text))

    def clean_llm_response(self, response_text):
        """Cleans LLM response, ensuring valid JSON output."""
        try:
            response_text = response_text.strip().replace("```json", "").replace("```", "").strip()
            parsed_response = json.loads(response_text)
            return parsed_response.get("temas", {})
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON decoding error: {e}\nRaw response: {response_text}")
            return {}

    def determine_batch_size(self, comments, max_tokens_per_batch=1000):
        """Dynamically determines optimal batch sizes based on token limits."""
        batches = []
        current_batch = []
        current_token_count = 0

        for comment in comments:
            comment_tokens = self.count_tokens(comment)
            if current_token_count + comment_tokens > max_tokens_per_batch:
                batches.append(current_batch)
                current_batch = []
                current_token_count = 0

            current_batch.append(comment)
            current_token_count += comment_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    async def generate_dynamic_categories_in_batches(self, comments):
        """Processes comments in batches and generates thematic categories using LLM."""
        categories = defaultdict(list)
        batches = self.determine_batch_size(comments)

        print(f"📌 Total comments: {len(comments)}")
        print(f"📌 Total batches: {len(batches)}")

        for batch_num, batch in enumerate(batches, start=1):
            print(f"🔄 Processing batch {batch_num}/{len(batches)} with {len(batch)} comments...")
            comments_text = "\n".join(batch)

            try:
                response = self.client.chat.completions.create(
                    model= self.model,
                    messages=[
                        {"role": "system", "content": "Eres un experto en análisis de texto."},
                        {"role": "user", "content": f"Analiza los siguientes comentarios de Instagram y agrúpalos en temas de discusión. Devuelve el resultado en formato JSON con 'temas': {{'nombre_tema': ['comentario1', 'comentario2']}}.\n\n{comments_text}"}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )

                if not response or not response.choices:
                    print("⚠️ Empty response from OpenAI.")
                    continue

                response_content = response.choices[0].message.content.strip()
                if not response_content:
                    print("⚠️ OpenAI returned an empty response.")
                    continue

                batch_categories = self.clean_llm_response(response_content)
                for category, comments_list in batch_categories.items():
                    categories[category].extend(comments_list)

            except Exception as e:
                print(f"⚠️ Error processing batch {batch_num}: {e}")

        return categories

    async def save_results(self, categories):
        """Saves categorized comments in MinIO and the database."""
        try:
            category_counts = {category: len(comments) for category, comments in categories.items()}
            results = {
                "category_counts": category_counts,
                "categorized_comments": categories
            }

            # Upload results to MinIO
            output_path = f"{self.output_folder}/dynamic_categorized_comments.json"
            await self.minio_service.upload_content(
                object_name=output_path,
                data=json.dumps(results, indent=4, ensure_ascii=False),
                content_type="application/json"
            )

            print(f"✅ Categorized comments saved in MinIO: {output_path}")
            
            # Save results to database
            # Get the Instagram user from the database
            instagram_user = session.query(InstagramUserInfo).filter_by(username=self.username).first()
            if not instagram_user:
                print(f"⚠️ Instagram user {self.username} not found in database")
                return len(categories)
                
            # Get the Instagram post info for this user
            posts = session.query(InstagramPostInfo).filter_by(instagram_user_id=instagram_user.id).all()
            post_dict = {post.id: post for post in posts}
            
            # Save categories to database
            for category_name, comment_list in categories.items():
                # Create or update category
                category = session.query(InstagramCommentCategory).filter_by(
                    user_id=instagram_user.id,
                    category_type=category_name
                ).first()
                
                if not category:
                    category = InstagramCommentCategory(
                        user_id=instagram_user.id,
                        category_type=category_name,
                        category_count=len(comment_list)
                    )
                    session.add(category)
                    session.flush()  # Generate ID without committing
                else:
                    category.category_count = len(comment_list)
                
                # Save comments
                for comment_text in comment_list:
                    # For simplicity, assign to the first post if we can't match the comment to a specific post
                    # In a real implementation, you'd want to match comments to their specific posts
                    post_id = posts[0].id if posts else None
                    
                    if post_id:
                        # Check if comment already exists
                        existing_comment = session.query(InstagramComment).filter_by(
                            user_id=instagram_user.id,
                            post_id=post_id,
                            comment_text=comment_text
                        ).first()
                        
                        if not existing_comment:
                            comment = InstagramComment(
                                user_id=instagram_user.id,
                                post_id=post_id,
                                comment_text=comment_text,
                                category_id=category.id
                            )
                            session.add(comment)
            
            session.commit()
            print(f"✅ Categorized comments saved in database for user: {self.username}")
            
            return len(categories)
        except Exception as e:
            print(f"❌ Error saving results: {e}")
            session.rollback()
            return 0

    async def run_analysis(self):
        """Main function to run the entire categorization process."""
        try:
            comments = await self.load_comments()
            if not comments:
                print("❌ No comments found.")
                return

            categorized_comments = await self.generate_dynamic_categories_in_batches(comments)
            total_categories = await self.save_results(categorized_comments)

            print(f"📊 Total categories generated: {total_categories}")
            return total_categories
        except Exception as e:
            print(f"❌ Error during analysis: {e}")
