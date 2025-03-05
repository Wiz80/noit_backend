from sqlalchemy import Column, String, Text, ForeignKey, Integer, Boolean, ARRAY, DateTime, Float, CheckConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid
from datetime import datetime, UTC

# create stutus of execution


class InstagramScrapingJob(Base):
    __tablename__ = "instagram_scraping_jobs"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    business_id = Column(String, nullable=False)
    competitor_id = Column(String, ForeignKey("competitors.id"))
    username = Column(String(50), nullable=False)
    
    # Dataset IDs for different types of data
    dataset_id_profile = Column(String)
    dataset_id_posts = Column(String)
    dataset_id_comments = Column(String)
    dataset_id_reels = Column(String)
    dataset_id_igtv = Column(String)
    
    # Status tracking
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # Progress tracking
    profile_status = Column(String, default="pending")  # pending, processing, completed, failed
    posts_status = Column(String, default="pending")
    comments_status = Column(String, default="pending")
    reels_status = Column(String, default="pending")
    igtv_status = Column(String, default="pending")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))
    
    # Metadata
    results_limit = Column(Integer)
    max_comments = Column(Integer)
    job_metadata = Column(JSON)

class InstagramUserInfo(Base):
    __tablename__ = "instagram_user_info"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    # competitor_id = Column(String, ForeignKey("competitors.id"))
    
    username = Column(String(50), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    biography = Column(Text)
    followers_count = Column(Integer, nullable=False)
    follows_count = Column(Integer, nullable=False)
    verified = Column(Boolean, default=False)
    business_category = Column(String(100))
    external_url = Column(String(2083))
    profile_pic_url = Column(Text)
    total_posts = Column(Integer, nullable=False)
    igtv_videos = Column(Integer)
    highlight_reels = Column(Integer)
    address_city_name = Column(String(255))
    address_lat = Column(Float)
    address_lng = Column(Float)
    

class InstagramPostInfo(Base):
    __tablename__ = "instagram_posts_info"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    id_post = Column(String, nullable=False, unique=True)
    instagram_user_id = Column(String, ForeignKey("instagram_user_info.id"))
    
    caption = Column(Text)
    hashtags = Column(ARRAY(String))
    mentions = Column(ARRAY(String))
    likes_count = Column(Integer, nullable=False)
    comments_count = Column(Integer, nullable=False)
    is_sponsored = Column(Boolean, default=False)
    post_timestamp = Column(DateTime(timezone=True))
    type_post = Column(String(50), nullable=True)
    url_post = Column(String(2083), nullable=True)
    

class InstagramPostImage(Base):
    __tablename__ = "instagram_post_images"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    post_id = Column(String, ForeignKey("instagram_posts_info.id", ondelete="CASCADE"))
    file_name = Column(String(255), nullable=False, unique=True)
    llm_analysis = Column(Text)
    

class InstagramImageColor(Base):
    __tablename__ = "instagram_image_colors"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    image_id = Column(String, ForeignKey("instagram_post_images.id", ondelete="CASCADE"))
    
    # Color components with constraints
    red = Column(Integer, nullable=False)
    green = Column(Integer, nullable=False)
    blue = Column(Integer, nullable=False)
    proportion = Column(Float, nullable=False)
    
    # Add check constraints for valid ranges
    __table_args__ = (
        CheckConstraint('red >= 0 AND red <= 255', name='valid_red'),
        CheckConstraint('green >= 0 AND green <= 255', name='valid_green'),
        CheckConstraint('blue >= 0 AND blue <= 255', name='valid_blue'),
        CheckConstraint('proportion >= 0 AND proportion <= 1', name='valid_proportion'),
    )
    

class InstagramUserInsight(Base):
    __tablename__ = "instagram_user_insights"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"))
    final_insight = Column(Text, nullable=False)


# New models for comment analysis

class InstagramCommentCategory(Base):
    __tablename__ = "instagram_comment_categories"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    category_type = Column(String(100), nullable=False)
    category_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.now(UTC))


class InstagramComment(Base):
    __tablename__ = "instagram_comments"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(String, ForeignKey("instagram_posts_info.id", ondelete="CASCADE"), nullable=False)
    username_commentator = Column(String(50), nullable=False)
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.now(UTC))


class InstagramLDATopic(Base):
    __tablename__ = "instagram_lda_topics"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    topic_name = Column(String(100), nullable=False)
    topic_details = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class InstagramCommentSentiment(Base):
    __tablename__ = "instagram_comment_sentiments"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    post_id = Column(String, ForeignKey("instagram_posts_info.id", ondelete="CASCADE"), nullable=False)
    comment_id = Column(String, ForeignKey("instagram_comments.id", ondelete="CASCADE"), nullable=False)
    comment_text = Column(Text, nullable=False)
    sentiment_negative = Column(Float, nullable=False)
    sentiment_neutral = Column(Float, nullable=False)
    sentiment_positive = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)



class InstagramPostSentimentSummary(Base):
    __tablename__ = "instagram_post_sentiment_summary"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    post_id = Column(String, ForeignKey("instagram_posts_info.id", ondelete="CASCADE"), nullable=False)
    total_comments = Column(Integer, nullable=False, default=0)
    positive_comments = Column(Integer, nullable=False, default=0)
    negative_comments = Column(Integer, nullable=False, default=0)
    neutral_comments = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class InstagramUserSentimentOverview(Base):
    __tablename__ = "instagram_user_sentiment_overview"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    total_comments = Column(Integer, nullable=False, default=0)
    positive_comments = Column(Integer, nullable=False, default=0)
    negative_comments = Column(Integer, nullable=False, default=0)
    neutral_comments = Column(Integer, nullable=False, default=0)
    positive_ratio = Column(Float, nullable=False)
    negative_ratio = Column(Float, nullable=False)
    neutral_ratio = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class InstagramCommentEmotion(Base):
    __tablename__ = "instagram_comment_emotions"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    comment_id = Column(String, ForeignKey("instagram_comments.id", ondelete="CASCADE"), nullable=False)
    emotion_label = Column(String(50), nullable=False)
    emotion_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)



# Multi-account analysis tables

class MultiAccountCommentCategory(Base):
    __tablename__ = "multi_account_comment_categories"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    category_type = Column(String(100), nullable=False)
    category_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class MultiAccountComment(Base):
    __tablename__ = "multi_account_comments"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(String, ForeignKey("instagram_posts_info.id", ondelete="CASCADE"), nullable=False)
    comment_text = Column(Text, nullable=False)
    category_id = Column(String, ForeignKey("multi_account_comment_categories.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class MultiAccountLDATopic(Base):
    __tablename__ = "multi_account_lda_topics"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    topic_name = Column(String(100), nullable=False)
    topic_details = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class MultiAccountSentimentOverview(Base):
    __tablename__ = "multi_account_sentiment_overview"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("instagram_user_info.id", ondelete="CASCADE"), nullable=False)
    total_comments = Column(Integer, nullable=False, default=0)
    positive_comments = Column(Integer, nullable=False, default=0)
    negative_comments = Column(Integer, nullable=False, default=0)
    neutral_comments = Column(Integer, nullable=False, default=0)
    positive_ratio = Column(Float, nullable=False)
    negative_ratio = Column(Float, nullable=False)
    neutral_ratio = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    