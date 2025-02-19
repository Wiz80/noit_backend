from sqlalchemy import Column, String, Text, ForeignKey, Integer, Boolean, ARRAY, DateTime, Float, CheckConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid

# create stutus of execution


class InstagramScrapingJob(Base):
    __tablename__ = "instagram_scraping_jobs"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    competitor_id = Column(String, ForeignKey("competitors.id"))
    username = Column(String(50), nullable=False)
    dataset_id_post = Column(String)
    dataset_id_image = Column(String)
    status = Column(String, nullable=False)

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
    

class InstagramPostInfo(Base):
    __tablename__ = "instagram_posts_info"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    instagram_user_id = Column(String, ForeignKey("instagram_user_info.id"))
    
    caption = Column(Text)
    hashtags = Column(ARRAY(String))
    mentions = Column(ARRAY(String))
    likes_count = Column(Integer, nullable=False)
    comments_count = Column(Integer, nullable=False)
    is_sponsored = Column(Boolean, default=False)
    post_timestamp = Column(DateTime(timezone=True))
    

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
    