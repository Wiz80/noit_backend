import json
from transformers import pipeline
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer
from app.models.business.competitive_analysis.instagram import (
    InstagramUserInfo, 
    InstagramPostInfo, 
    InstagramComment,
    InstagramCommentSentiment, 
    InstagramCommentEmotion,
    InstagramPostSentimentSummary,
    InstagramUserSentimentOverview
)
from app.db.session import SessionLocal
from sqlalchemy import func

# Initialize database session
session = SessionLocal()

class InstagramSentimentEmotionAnalyzer(BaseInstagramAnalyzer):
    def __init__(self, username, output_folder):
        super().__init__(username, output_folder)
        self.sentiment_model = "pysentimiento/robertuito-sentiment-analysis"
        self.emotion_model = "pysentimiento/robertuito-emotion-analysis"
        self.sentiment_pipeline = pipeline(
            task="text-classification",
            model=self.sentiment_model,
            tokenizer=self.sentiment_model,
            return_all_scores=True,
            device=-1
        )
        self.emotion_pipeline = pipeline(
            task="text-classification",
            model=self.emotion_model,
            tokenizer=self.emotion_model,
            return_all_scores=True,
            device=-1
        )

    async def analyze_sentiment_and_emotions(self):
        """Analyzes sentiment and emotions of Instagram comments and stores results in MinIO and database."""
        try:
            comments = await self.load_comments()
            if not comments:
                print("❌ No comments found.")
                return

            # Get Instagram user
            instagram_user = session.query(InstagramUserInfo).filter_by(username=self.username).first()
            if not instagram_user:
                print(f"⚠️ Instagram user {self.username} not found in database")
                return
                
            # Get Instagram posts for this user
            posts = session.query(InstagramPostInfo).filter_by(instagram_user_id=instagram_user.id).all()
            if not posts:
                print(f"⚠️ No posts found for user {self.username}")
                return
                
            # Use the first post for simplicity
            default_post_id = posts[0].id
            
            sentiment_results = []
            emotion_results = []
            
            # Counters for user sentiment overview
            total_comments = len(comments)
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            
            # Dictionary to track post-level sentiment summaries
            post_sentiment_summaries = {post.id: {"total": 0, "positive": 0, "negative": 0, "neutral": 0} for post in posts}
            post_sentiment_summaries[default_post_id]["total"] = total_comments

            for comment in comments:
                cleaned_text = self.clean_text(comment)

                # Sentiment Analysis
                sentiment_response = self.sentiment_pipeline(cleaned_text)[0]
                top_sentiment = max(sentiment_response, key=lambda x: x["score"])
                sentiment_results.append({
                    "commentText": comment,
                    "scores": sentiment_response,
                    "top_label": top_sentiment["label"]
                })
                
                # Update counters based on sentiment
                if top_sentiment["label"] == "POS":
                    positive_count += 1
                    post_sentiment_summaries[default_post_id]["positive"] += 1
                elif top_sentiment["label"] == "NEG":
                    negative_count += 1
                    post_sentiment_summaries[default_post_id]["negative"] += 1
                else:
                    neutral_count += 1
                    post_sentiment_summaries[default_post_id]["neutral"] += 1

                # Emotion Analysis
                emotion_response = self.emotion_pipeline(cleaned_text)[0]
                top_emotion = max(emotion_response, key=lambda x: x["score"])
                emotion_results.append({
                    "commentText": comment,
                    "scores": emotion_response,
                    "top_label": top_emotion["label"]
                })
                
                # Save to database
                # Find or create comment record
                comment_record = session.query(InstagramComment).filter_by(
                    user_id=instagram_user.id,
                    post_id=default_post_id,
                    comment_text=comment
                ).first()
                
                if comment_record:
                    # Save sentiment
                    sentiment_record = InstagramCommentSentiment(
                        post_id=default_post_id,
                        comment_id=comment_record.id,
                        comment_text=comment,
                        sentiment_negative=next(s["score"] for s in sentiment_response if s["label"] == "NEG"),
                        sentiment_neutral=next(s["score"] for s in sentiment_response if s["label"] == "NEU"),
                        sentiment_positive=next(s["score"] for s in sentiment_response if s["label"] == "POS")
                    )
                    session.add(sentiment_record)
                    
                    # Save emotion
                    for emotion_item in emotion_response:
                        emotion_record = InstagramCommentEmotion(
                            comment_id=comment_record.id,
                            emotion_label=emotion_item["label"],
                            emotion_score=emotion_item["score"]
                        )
                        session.add(emotion_record)

            # Save post-level sentiment summaries
            for post_id, counts in post_sentiment_summaries.items():
                if counts["total"] > 0:  # Only save if there are comments
                    existing_summary = session.query(InstagramPostSentimentSummary).filter_by(post_id=post_id).first()
                    
                    if existing_summary:
                        existing_summary.total_comments = counts["total"]
                        existing_summary.positive_comments = counts["positive"]
                        existing_summary.negative_comments = counts["negative"]
                        existing_summary.neutral_comments = counts["neutral"]
                    else:
                        post_summary = InstagramPostSentimentSummary(
                            post_id=post_id,
                            total_comments=counts["total"],
                            positive_comments=counts["positive"],
                            negative_comments=counts["negative"],
                            neutral_comments=counts["neutral"]
                        )
                        session.add(post_summary)
            
            # Save user-level sentiment overview
            if total_comments > 0:
                existing_overview = session.query(InstagramUserSentimentOverview).filter_by(user_id=instagram_user.id).first()
                
                # Calculate ratios
                positive_ratio = positive_count / total_comments if total_comments > 0 else 0
                negative_ratio = negative_count / total_comments if total_comments > 0 else 0
                neutral_ratio = neutral_count / total_comments if total_comments > 0 else 0
                
                if existing_overview:
                    existing_overview.total_comments = total_comments
                    existing_overview.positive_comments = positive_count
                    existing_overview.negative_comments = negative_count
                    existing_overview.neutral_comments = neutral_count
                    existing_overview.positive_ratio = positive_ratio
                    existing_overview.negative_ratio = negative_ratio
                    existing_overview.neutral_ratio = neutral_ratio
                else:
                    user_overview = InstagramUserSentimentOverview(
                        user_id=instagram_user.id,
                        total_comments=total_comments,
                        positive_comments=positive_count,
                        negative_comments=negative_count,
                        neutral_comments=neutral_count,
                        positive_ratio=positive_ratio,
                        negative_ratio=negative_ratio,
                        neutral_ratio=neutral_ratio
                    )
                    session.add(user_overview)
            
            session.commit()
            print(f"✅ Sentiment and emotion analysis saved to database for user: {self.username}")

            # Save results to MinIO
            await self.save_results_to_minio(sentiment_results, emotion_results)

        except Exception as e:
            print(f"❌ Error analyzing sentiment and emotions: {e}")
            session.rollback()

    async def save_results_to_minio(self, sentiment_results, emotion_results):
        """Saves the analysis results to MinIO as JSON files."""
        try:
            sentiment_output = {
                "total_comments": len(sentiment_results),
                "results": sentiment_results
            }
            emotion_output = {
                "total_comments": len(emotion_results),
                "results": emotion_results
            }

            # Upload Sentiment Results
            sentiment_path = f"{self.output_folder}/sentiment_analysis.json"
            await self.minio_service.upload_content(
                object_name=sentiment_path,
                data=json.dumps(sentiment_output, indent=4, ensure_ascii=False),
                content_type="application/json"
            )
            print(f"✅ Sentiment analysis results saved to MinIO: {sentiment_path}")

            # Upload Emotion Results
            emotion_path = f"{self.output_folder}/emotion_analysis.json"
            await self.minio_service.upload_content(
                object_name=emotion_path,
                data=json.dumps(emotion_output, indent=4, ensure_ascii=False),
                content_type="application/json"
            )
            print(f"✅ Emotion analysis results saved to MinIO: {emotion_path}")

        except Exception as e:
            print(f"❌ Error saving results to MinIO: {e}")
