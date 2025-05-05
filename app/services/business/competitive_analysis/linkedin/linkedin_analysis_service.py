import logging
import json
import numpy as np
import re
import uuid
import os
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime

# NLP/ML imports
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.cluster import KMeans, DBSCAN
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import spacy
from collections import Counter
from textblob import TextBlob

# Download required NLTK packages
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If model not downloaded, inform user to download it
    logging.error("spaCy model 'en_core_web_sm' not found. Please run: python -m spacy download en_core_web_sm")
    # Use simple NLP as fallback
    nlp = None

from app.services.storage.minio_service import MinioService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInAnalysisService:
    """
    Service for analyzing LinkedIn data using NLP and ML techniques
    """
    
    def __init__(self):
        """Initialize the LinkedIn analysis service with necessary tools"""
        self.minio_service = MinioService(bucket_name="lattice-businesses")
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words('english'))
        
    async def analyze_competitor(self, 
                               business_id: str, 
                               competitor_id: str,
                               competitor_name: str,
                               analysis_types: List[str] = None,
                               force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analyze LinkedIn data for a specific competitor
        
        Args:
            business_id: The business ID
            competitor_id: The competitor ID
            competitor_name: The competitor name
            analysis_types: List of analysis types to perform 
                            ("sentiment", "keywords", "topics", "engagement", "content", "ads")
            force_refresh: Whether to force refresh the analysis
            
        Returns:
            Dict containing analysis results
        """
        if not analysis_types:
            analysis_types = ["sentiment", "keywords", "topics", "engagement", "content", "ads"]
            
        # Check if analysis already exists and not forcing refresh
        analysis_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name.lower()}/analysis.json"
        if not force_refresh and self.minio_service.object_exists(analysis_path):
            return self.minio_service.download_json(analysis_path)
            
        # Create analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Prepare result structure
        result = {
            "business_id": business_id,
            "competitor_id": competitor_id,
            "competitor_name": competitor_name,
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "insights": {}
        }
        
        # Load data from Minio
        company_data = await self._load_company_data(business_id, competitor_name)
        posts_data = await self._load_posts_data(business_id, competitor_name)
        ads_data = await self._load_ads_data(business_id, competitor_name)
        
        # Extract LinkedIn URL
        linkedin_url = None
        if company_data and isinstance(company_data, list) and len(company_data) > 0:
            linkedin_url = company_data[0].get("url", "")
        
        # Initialize insights
        insights = {
            "competitor_id": competitor_id,
            "competitor_name": competitor_name,
            "linkedin_url": linkedin_url,
            "company_profile": self._extract_company_profile(company_data)
        }
        
        # Perform requested analyses
        if "sentiment" in analysis_types and posts_data:
            insights["sentiment_analysis"] = await self._analyze_sentiment(posts_data)
            
        if "keywords" in analysis_types:
            insights["keyword_extraction"] = await self._extract_keywords_and_entities(company_data, posts_data, ads_data)
            
        if "topics" in analysis_types and posts_data:
            insights["topic_modeling"] = await self._perform_topic_modeling(posts_data)
            
        if "engagement" in analysis_types and posts_data:
            insights["engagement_stats"] = await self._analyze_engagement(posts_data, company_data)
            
        if "content" in analysis_types and posts_data:
            insights["content_distribution"] = await self._analyze_content_distribution(posts_data)
            
        if "ads" in analysis_types and ads_data:
            insights["ad_metrics"] = await self._analyze_ads(ads_data)
            
        # Generate recommendations
        insights["recommendations"] = await self._generate_recommendations(insights)
        
        # Update result with insights
        result["insights"] = insights
        
        # Save to Minio
        self.minio_service.upload_json(analysis_path, result)
        
        return result
        
    async def analyze_business_competitors(self,
                                         business_id: str,
                                         competitor_ids: List[str],
                                         competitor_names: List[str],
                                         analysis_types: List[str] = None,
                                         include_comparison: bool = True,
                                         force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analyze LinkedIn data for all competitors of a business
        
        Args:
            business_id: The business ID
            competitor_ids: List of competitor IDs
            competitor_names: List of competitor names
            analysis_types: List of analysis types to perform
            include_comparison: Whether to include comparison between competitors
            force_refresh: Whether to force refresh the analysis
            
        Returns:
            Dict containing analysis results for all competitors and comparison
        """
        if not analysis_types:
            analysis_types = ["sentiment", "keywords", "topics", "engagement", "content", "ads"]
            
        # Check if analysis already exists and not forcing refresh
        analysis_path = f"{business_id}/competitor-analysis/linkedin/business_analysis.json"
        if not force_refresh and self.minio_service.object_exists(analysis_path):
            return self.minio_service.download_json(analysis_path)
            
        # Create analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Prepare result structure
        result = {
            "business_id": business_id,
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "status": "in_progress",
            "competitors": [],
            "comparison": {},
            "recommendations": []
        }
        
        # Analyze each competitor
        for i, competitor_id in enumerate(competitor_ids):
            try:
                competitor_name = competitor_names[i]
                competitor_result = await self.analyze_competitor(
                    business_id=business_id,
                    competitor_id=competitor_id,
                    competitor_name=competitor_name,
                    analysis_types=analysis_types,
                    force_refresh=force_refresh
                )
                if "insights" in competitor_result:
                    result["competitors"].append(competitor_result["insights"])
            except Exception as e:
                logger.error(f"Error analyzing competitor {competitor_id}: {str(e)}")
                
        # Generate comparison if requested
        if include_comparison and result["competitors"]:
            result["comparison"] = await self._generate_comparison(result["competitors"])
            result["recommendations"] = await self._generate_business_recommendations(result["competitors"], result["comparison"])
        
        # Update status
        result["status"] = "completed"
        
        # Save to Minio
        self.minio_service.upload_json(analysis_path, result)
        
        return result
        
    # Helper methods for loading data
    
    async def _load_company_data(self, business_id: str, competitor_name: str) -> List[Dict[str, Any]]:
        """Load company data from Minio"""
        path = f"{business_id}/competitor-analysis/linkedin/{competitor_name.lower()}/company.json"
        if self.minio_service.object_exists(path):
            data = self.minio_service.download_json(path)
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data
        return []
        
    async def _load_posts_data(self, business_id: str, competitor_name: str) -> List[Dict[str, Any]]:
        """Load posts data from Minio"""
        path = f"{business_id}/competitor-analysis/linkedin/{competitor_name.lower()}/post.json"
        if self.minio_service.object_exists(path):
            data = self.minio_service.download_json(path)
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data
        return []
        
    async def _load_ads_data(self, business_id: str, competitor_name: str) -> List[Dict[str, Any]]:
        """Load ads data from Minio"""
        path = f"{business_id}/competitor-analysis/linkedin/{competitor_name.lower()}/ads.json"
        if self.minio_service.object_exists(path):
            data = self.minio_service.download_json(path)
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data
        return []
        
    # Analysis methods
    
    def _extract_company_profile(self, company_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key company profile information"""
        if not company_data or len(company_data) == 0:
            return {}
            
        company = company_data[0]  # Take the first result
        
        return {
            "name": company.get("name", ""),
            "tagline": company.get("tagline", ""),
            "description": company.get("description", ""),
            "industry": company.get("industry", []),
            "hashtag": company.get("hashtag", []),
            "websiteUrl": company.get("websiteUrl", ""),
            "headquarter": company.get("headquarter", {}),
            "foundedOn": company.get("foundedOn", {}),
            "employeeCount": company.get("employeeCount", 0),
            "followerCount": company.get("followerCount", 0),
            "crunchbaseFunding": company.get("crunchbaseFunding", {})
        }
        
    async def _analyze_sentiment(self, posts_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Analyze sentiment of posts and comments"""
        if not posts_data:
            return {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 0.0,
                "compound": 0.0
            }
            
        # Extract text from posts and comments
        texts = []
        
        for post in posts_data:
            if "text" in post and post["text"]:
                texts.append(post["text"])
            
            # Add comment texts
            if "comments" in post and post["comments"]:
                for comment in post["comments"]:
                    if "text" in comment and comment["text"]:
                        texts.append(comment["text"])
        
        if not texts:
            return {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 0.0,
                "compound": 0.0
            }
            
        # Analyze sentiment
        pos_scores = []
        neg_scores = []
        neu_scores = []
        compound_scores = []
        
        for text in texts:
            sentiment = self.sentiment_analyzer.polarity_scores(text)
            pos_scores.append(sentiment["pos"])
            neg_scores.append(sentiment["neg"])
            neu_scores.append(sentiment["neu"])
            compound_scores.append(sentiment["compound"])
            
        # Calculate average scores
        return {
            "positive": sum(pos_scores) / len(pos_scores),
            "negative": sum(neg_scores) / len(neg_scores),
            "neutral": sum(neu_scores) / len(neu_scores),
            "compound": sum(compound_scores) / len(compound_scores)
        }
        
    async def _extract_keywords_and_entities(self, 
                                           company_data: List[Dict[str, Any]], 
                                           posts_data: List[Dict[str, Any]], 
                                           ads_data: List[Dict[str, Any]]) -> Dict[str, List]:
        """Extract keywords and entities from text data"""
        # Combine all relevant text
        texts = []
        
        # Add company description
        if company_data and len(company_data) > 0:
            company = company_data[0]
            if "description" in company and company["description"]:
                texts.append(company["description"])
            if "tagline" in company and company["tagline"]:
                texts.append(company["tagline"])
        
        # Add post texts
        if posts_data:
            for post in posts_data:
                if "text" in post and post["text"]:
                    texts.append(post["text"])
        
        # Add ad texts
        if ads_data:
            for ad in ads_data:
                if "body" in ad:
                    # Ad body might be a list or a string
                    if isinstance(ad["body"], list):
                        texts.extend([body for body in ad["body"] if body])
                    elif ad["body"]:
                        texts.append(ad["body"])
                        
                if "headline" in ad and ad["headline"]:
                    texts.append(ad["headline"])
        
        if not texts:
            return {
                "keywords": [],
                "entities": []
            }
            
        # Extract keywords using TF-IDF
        tfidf_vectorizer = TfidfVectorizer(
            max_df=0.95, 
            min_df=2, 
            max_features=30,
            stop_words='english'
        )
        
        # Process the texts to handle potential errors
        cleaned_texts = []
        for text in texts:
            try:
                # Clean text (remove URLs, special chars, etc)
                cleaned_text = re.sub(r'http\S+', '', text)
                cleaned_text = re.sub(r'[^\w\s]', '', cleaned_text)
                cleaned_text = cleaned_text.lower()
                cleaned_texts.append(cleaned_text)
            except Exception as e:
                logger.warning(f"Error cleaning text: {str(e)}")
        
        if not cleaned_texts:
            return {
                "keywords": [],
                "entities": []
            }
            
        try:
            tfidf_matrix = tfidf_vectorizer.fit_transform(cleaned_texts)
            feature_names = tfidf_vectorizer.get_feature_names_out()
            
            # Get top keywords
            tfidf_sums = tfidf_matrix.sum(axis=0).A1
            top_indices = tfidf_sums.argsort()[-30:][::-1]
            keywords = [{"keyword": feature_names[i], "score": float(tfidf_sums[i])} for i in top_indices]
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            keywords = []
        
        # Extract entities using spaCy if available
        entities = []
        if nlp:
            try:
                # Combine texts to process them together
                combined_text = " ".join(cleaned_texts)
                doc = nlp(combined_text)
                
                # Count entities
                entity_counts = Counter()
                for ent in doc.ents:
                    entity_counts[(ent.text.lower(), ent.label_)] += 1
                
                # Convert to list of dicts
                for (text, label), count in entity_counts.most_common(30):
                    entities.append({
                        "text": text,
                        "label": label,
                        "count": count
                    })
            except Exception as e:
                logger.error(f"Error extracting entities: {str(e)}")
        
        return {
            "keywords": keywords,
            "entities": entities
        }
        
    async def _perform_topic_modeling(self, posts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform topic modeling on posts data"""
        if not posts_data:
            return {
                "topics": [],
                "dominant_topic": {}
            }
            
        # Extract post texts
        texts = []
        for post in posts_data:
            if "text" in post and post["text"]:
                texts.append(post["text"])
        
        if not texts:
            return {
                "topics": [],
                "dominant_topic": {}
            }
            
        # Clean texts
        cleaned_texts = []
        for text in texts:
            try:
                # Clean text
                cleaned_text = re.sub(r'http\S+', '', text)
                cleaned_text = re.sub(r'[^\w\s]', '', cleaned_text)
                cleaned_text = cleaned_text.lower()
                
                # Tokenize and remove stopwords
                tokens = word_tokenize(cleaned_text)
                filtered_tokens = [word for word in tokens if word not in self.stop_words]
                
                cleaned_texts.append(" ".join(filtered_tokens))
            except Exception as e:
                logger.warning(f"Error cleaning text for topic modeling: {str(e)}")
        
        if not cleaned_texts:
            return {
                "topics": [],
                "dominant_topic": {}
            }
            
        try:
            # Vectorize texts
            vectorizer = CountVectorizer(max_df=0.95, min_df=2, max_features=1000, stop_words='english')
            dtm = vectorizer.fit_transform(cleaned_texts)
            
            # Apply LDA
            lda_model = LatentDirichletAllocation(
                n_components=5,  # Number of topics
                random_state=42,
                max_iter=10
            )
            lda_output = lda_model.fit_transform(dtm)
            
            # Get feature names
            feature_names = vectorizer.get_feature_names_out()
            
            # Format topics
            topics = []
            for topic_idx, topic in enumerate(lda_model.components_):
                top_words_idx = topic.argsort()[:-11:-1]  # Get top 10 words
                top_words = [feature_names[i] for i in top_words_idx]
                topics.append({
                    "id": topic_idx,
                    "words": top_words,
                    "weight": float(topic.sum() / lda_model.components_.sum())
                })
            
            # Find dominant topic
            dominant_topic_index = np.argmax([t["weight"] for t in topics])
            dominant_topic = topics[dominant_topic_index]
            
            return {
                "topics": topics,
                "dominant_topic": dominant_topic
            }
        except Exception as e:
            logger.error(f"Error in topic modeling: {str(e)}")
            return {
                "topics": [],
                "dominant_topic": {},
                "error": str(e)
            }
        
    async def _analyze_engagement(self, posts_data: List[Dict[str, Any]], company_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze engagement metrics"""
        if not posts_data:
            return {
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0,
                "avg_likes_per_post": 0,
                "avg_comments_per_post": 0,
                "avg_shares_per_post": 0,
                "engagement_rate": 0
            }
            
        # Calculate engagement metrics
        total_likes = 0
        total_comments = 0
        total_shares = 0
        
        for post in posts_data:
            total_likes += post.get("numLikes", 0)
            total_comments += post.get("numComments", 0)
            total_shares += post.get("numShares", 0)
            
        post_count = len(posts_data)
        
        # Get follower count
        follower_count = 0
        if company_data and len(company_data) > 0:
            follower_count = company_data[0].get("followerCount", 0)
        
        # Calculate averages and rate
        avg_likes = total_likes / post_count if post_count > 0 else 0
        avg_comments = total_comments / post_count if post_count > 0 else 0
        avg_shares = total_shares / post_count if post_count > 0 else 0
        
        # Calculate engagement rate (as a percentage)
        engagement_rate = 0
        if follower_count > 0:
            engagement_rate = ((total_likes + total_comments + total_shares) / (post_count * follower_count)) * 100
        
        return {
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "avg_likes_per_post": avg_likes,
            "avg_comments_per_post": avg_comments,
            "avg_shares_per_post": avg_shares,
            "engagement_rate": engagement_rate
        }
        
    async def _analyze_content_distribution(self, posts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze content type distribution"""
        if not posts_data:
            return {
                "text_posts": 0,
                "image_posts": 0,
                "video_posts": 0,
                "total_posts": 0,
                "text_percentage": 0,
                "image_percentage": 0,
                "video_percentage": 0
            }
            
        # Count post types
        text_posts = 0
        image_posts = 0
        video_posts = 0
        
        for post in posts_data:
            post_type = post.get("type", "")
            
            if post_type == "linkedinVideo":
                video_posts += 1
            elif "image_urls" in post and post["image_urls"]:
                image_posts += 1
            else:
                text_posts += 1
        
        total_posts = len(posts_data)
        
        # Calculate percentages
        text_percentage = (text_posts / total_posts * 100) if total_posts > 0 else 0
        image_percentage = (image_posts / total_posts * 100) if total_posts > 0 else 0
        video_percentage = (video_posts / total_posts * 100) if total_posts > 0 else 0
        
        return {
            "text_posts": text_posts,
            "image_posts": image_posts,
            "video_posts": video_posts,
            "total_posts": total_posts,
            "text_percentage": text_percentage,
            "image_percentage": image_percentage,
            "video_percentage": video_percentage
        }
        
    async def _analyze_ads(self, ads_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze advertising metrics"""
        if not ads_data:
            return {
                "total_ads": 0,
                "ad_types": {},
                "cta_distribution": {},
                "countries_distribution": {},
                "target_languages": [],
                "target_locations": []
            }
            
        # Count ad types
        ad_types = {}
        cta_distribution = {}
        countries = {}
        target_languages = set()
        target_locations = set()
        
        for ad in ads_data:
            # Count ad types
            ad_type = ad.get("ad_type", "unknown")
            ad_types[ad_type] = ad_types.get(ad_type, 0) + 1
            
            # Count CTAs
            cta_name = ad.get("CTA_name", "unknown")
            cta_distribution[cta_name] = cta_distribution.get(cta_name, 0) + 1
            
            # Count countries from impressions
            for country_data in ad.get("impressions_per_country", []):
                country = country_data.get("country", "unknown")
                impression = country_data.get("impressions", "0%")
                
                # Convert impression string to float
                try:
                    if isinstance(impression, str):
                        if impression.endswith("%"):
                            impression = impression.rstrip("%")
                        if impression.startswith("<"):
                            impression = "0.5"  # Assume "<1%" is 0.5%
                        impression_float = float(impression)
                    else:
                        impression_float = float(impression)
                    
                    countries[country] = countries.get(country, 0) + impression_float
                except ValueError:
                    continue
            
            # Extract targeting settings
            targeting = ad.get("targeting_settings", {})
            
            # Languages
            if "Language" in targeting and targeting["Language"]:
                for language in targeting["Language"]:
                    target_languages.add(language)
            
            # Locations
            if "Location" in targeting and targeting["Location"]:
                for location in targeting["Location"]:
                    target_locations.add(location)
        
        return {
            "total_ads": len(ads_data),
            "ad_types": ad_types,
            "cta_distribution": cta_distribution,
            "countries_distribution": countries,
            "target_languages": list(target_languages),
            "target_locations": list(target_locations)
        }
        
    async def _generate_recommendations(self, insights: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on insights"""
        recommendations = []
        
        # Check company profile
        company_profile = insights.get("company_profile", {})
        if not company_profile.get("description") or len(company_profile.get("description", "")) < 50:
            recommendations.append("The competitor's LinkedIn company description is minimal or missing. This may be an opportunity to provide more comprehensive information in your profile.")
        
        # Check content distribution
        content_distribution = insights.get("content_distribution", {})
        if content_distribution:
            # Check for video content
            if content_distribution.get("video_percentage", 0) < 10:
                recommendations.append("The competitor posts little video content (<10%). Consider video content as a potential differentiator if appropriate for your industry.")
                
            # Check for balanced content
            text_pct = content_distribution.get("text_percentage", 0)
            image_pct = content_distribution.get("image_percentage", 0)
            video_pct = content_distribution.get("video_percentage", 0)
            
            if max(text_pct, image_pct, video_pct) > 70:
                recommendations.append("The competitor relies heavily on a single content type. A more balanced content strategy might engage a broader audience.")
        
        # Check engagement
        engagement_stats = insights.get("engagement_stats", {})
        if engagement_stats:
            if engagement_stats.get("engagement_rate", 0) < 1.0:
                recommendations.append("The competitor has a low engagement rate (<1%). This could indicate their content is not resonating with their audience, presenting an opportunity for better content strategy.")
        
        # Check sentiment
        sentiment = insights.get("sentiment_analysis", {})
        if sentiment:
            compound = sentiment.get("compound", 0)
            if compound > 0.5:
                recommendations.append("The competitor's content receives highly positive sentiment. Analyze their successful posts to understand what resonates with their audience.")
            elif compound < 0:
                recommendations.append("The competitor's content receives negative sentiment overall. This could present an opportunity to address audience pain points more effectively.")
        
        # Check keywords
        keywords = insights.get("keyword_extraction", {}).get("keywords", [])
        if keywords:
            keywords_str = ", ".join([k["keyword"] for k in keywords[:5]])
            recommendations.append(f"Top keywords for this competitor include: {keywords_str}. Consider incorporating relevant keywords in your content strategy if aligned with your brand.")
        
        # Check topic modeling
        topics = insights.get("topic_modeling", {}).get("dominant_topic", {})
        if topics and "words" in topics:
            topic_words = ", ".join(topics["words"][:5])
            recommendations.append(f"The competitor's content focuses on topics related to: {topic_words}. Analyze if these topics align with your target audience's interests.")
        
        # Check ad strategy
        ad_metrics = insights.get("ad_metrics", {})
        if ad_metrics:
            if ad_metrics.get("total_ads", 0) > 0:
                # Suggest CTA strategy
                cta_distribution = ad_metrics.get("cta_distribution", {})
                if cta_distribution:
                    top_cta = max(cta_distribution.items(), key=lambda x: x[1])[0]
                    recommendations.append(f"The competitor primarily uses '{top_cta}' as their call-to-action in ads. Consider testing this CTA if it aligns with your campaign objectives.")
                
                # Suggest geographic targeting
                countries = ad_metrics.get("countries_distribution", {})
                if countries:
                    top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:3]
                    top_countries_str = ", ".join([c[0] for c in top_countries])
                    recommendations.append(f"The competitor focuses their ad spend on these markets: {top_countries_str}. Evaluate if these are key markets for your business as well.")
            else:
                recommendations.append("The competitor doesn't appear to be running LinkedIn ads currently. This could represent an opportunity to capture audience attention through paid campaigns.")
        
        return recommendations
        
    async def _generate_comparison(self, competitors_insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comparison between competitors"""
        if not competitors_insights:
            return {}
            
        comparison = {
            "follower_counts": {},
            "sentiment_comparison": {},
            "engagement_rates": {},
            "content_strategy": {},
            "common_topics": {},
            "advertising_focus": {}
        }
        
        # Follower counts
        for competitor in competitors_insights:
            name = competitor.get("competitor_name", "Unknown")
            company_profile = competitor.get("company_profile", {})
            follower_count = company_profile.get("followerCount", 0)
            comparison["follower_counts"][name] = follower_count
        
        # Sentiment comparison
        for competitor in competitors_insights:
            name = competitor.get("competitor_name", "Unknown")
            sentiment = competitor.get("sentiment_analysis", {})
            if sentiment:
                comparison["sentiment_comparison"][name] = sentiment.get("compound", 0)
        
        # Engagement rates
        for competitor in competitors_insights:
            name = competitor.get("competitor_name", "Unknown")
            engagement = competitor.get("engagement_stats", {})
            if engagement:
                comparison["engagement_rates"][name] = engagement.get("engagement_rate", 0)
        
        # Content strategy
        for competitor in competitors_insights:
            name = competitor.get("competitor_name", "Unknown")
            content = competitor.get("content_distribution", {})
            if content:
                comparison["content_strategy"][name] = {
                    "text": content.get("text_percentage", 0),
                    "image": content.get("image_percentage", 0),
                    "video": content.get("video_percentage", 0)
                }
        
        # Identify common topics across competitors
        all_topics = []
        for competitor in competitors_insights:
            name = competitor.get("competitor_name", "Unknown")
            topic_modeling = competitor.get("topic_modeling", {})
            dominant_topic = topic_modeling.get("dominant_topic", {})
            if dominant_topic and "words" in dominant_topic:
                all_topics.extend(dominant_topic["words"][:5])  # Take top 5 words from dominant topic
        
        # Count topic frequency
        topic_counts = Counter(all_topics)
        common_topics = [{"word": word, "count": count} for word, count in topic_counts.most_common(10)]
        comparison["common_topics"] = common_topics
        
        # Advertising focus
        ad_country_counts = Counter()
        ad_cta_counts = Counter()
        
        for competitor in competitors_insights:
            name = competitor.get("competitor_name", "Unknown")
            ad_metrics = competitor.get("ad_metrics", {})
            
            if ad_metrics:
                # Track countries
                countries = ad_metrics.get("countries_distribution", {})
                for country, weight in countries.items():
                    ad_country_counts[country] += weight
                
                # Track CTAs
                ctas = ad_metrics.get("cta_distribution", {})
                for cta, count in ctas.items():
                    ad_cta_counts[cta] += count
        
        comparison["advertising_focus"] = {
            "top_countries": [{"country": country, "weight": weight} for country, weight in ad_country_counts.most_common(5)],
            "top_ctas": [{"cta": cta, "count": count} for cta, count in ad_cta_counts.most_common(5)]
        }
        
        return comparison
        
    async def _generate_business_recommendations(self, competitors_insights: List[Dict[str, Any]], comparison: Dict[str, Any]) -> List[str]:
        """Generate business-level recommendations based on comparison"""
        if not competitors_insights or not comparison:
            return []
            
        recommendations = []
        
        # Follower gap analysis
        if "follower_counts" in comparison:
            follower_counts = comparison["follower_counts"]
            if follower_counts:
                max_followers = max(follower_counts.items(), key=lambda x: x[1])
                min_followers = min(follower_counts.items(), key=lambda x: x[1])
                
                if max_followers[1] > 0 and min_followers[1] > 0 and max_followers[1] / min_followers[1] > 5:
                    recommendations.append(f"{max_followers[0]} has significantly more followers ({max_followers[1]}) than {min_followers[0]} ({min_followers[1]}). Analyze their content strategy to understand what's driving this difference in audience size.")
        
        # Engagement optimization
        if "engagement_rates" in comparison:
            engagement_rates = comparison["engagement_rates"]
            if engagement_rates:
                max_engagement = max(engagement_rates.items(), key=lambda x: x[1])
                if max_engagement[1] > 0:
                    recommendations.append(f"{max_engagement[0]} achieves the highest engagement rate at {max_engagement[1]:.2f}%. Study their most engaging posts to identify patterns you can adapt to your strategy.")
        
        # Content type opportunities
        if "content_strategy" in comparison:
            content_strategies = comparison["content_strategy"]
            
            # Find gaps in video content
            video_percentages = {comp: stats["video"] for comp, stats in content_strategies.items()}
            if video_percentages:
                avg_video = sum(video_percentages.values()) / len(video_percentages)
                if avg_video < 15:
                    recommendations.append(f"Video content is underutilized among competitors (average {avg_video:.1f}%). This presents an opportunity to differentiate with more video content.")
        
        # Topic focus
        if "common_topics" in comparison:
            common_topics = comparison["common_topics"]
            if common_topics:
                top_topics = [topic["word"] for topic in common_topics[:5]]
                topics_str = ", ".join(top_topics)
                recommendations.append(f"The most common topics across all competitors are: {topics_str}. Consider how your content strategy addresses these key industry themes.")
        
        # Ad strategy recommendations
        if "advertising_focus" in comparison:
            ad_focus = comparison["advertising_focus"]
            
            # Geographic focus
            top_countries = ad_focus.get("top_countries", [])
            if top_countries:
                countries_str = ", ".join([c["country"] for c in top_countries[:3]])
                recommendations.append(f"Competitors focus their ad spend on these markets: {countries_str}. Consider if your geographic targeting aligns with industry trends.")
            
            # CTA strategy
            top_ctas = ad_focus.get("top_ctas", [])
            if top_ctas:
                ctas_str = ", ".join([c["cta"] for c in top_ctas[:3]])
                recommendations.append(f"The most common CTAs used by competitors are: {ctas_str}. Test these against your current CTAs to optimize conversion.")
        
        # Add differentiation recommendation
        if competitors_insights:
            recommendations.append("Look for content gaps or underserved topics among competitors by comparing the dominant themes in your industry. The analysis shows that most competitors focus on similar topics, which may present an opportunity to address niche areas.")
        
        return recommendations 