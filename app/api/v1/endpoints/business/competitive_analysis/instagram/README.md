# Competitor Analysis Module

This module provides functionality for analyzing competitors across different platforms, starting with Instagram.

## Instagram Competitor Analysis

The Instagram competitor analysis module allows you to extract and analyze data from competitors' Instagram profiles. This includes profile information, posts, comments, reels, and IGTV videos.

### Endpoints

#### Start Instagram Competitor Analysis

```
POST /api/v1/competitor-analysis/instagram/{business_id}
```

This endpoint initiates the Instagram competitor analysis process for all competitors associated with a specific business idea. The analysis runs in the background, and a task ID is returned for tracking progress.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Response:**
```json
{
  "task_id": "string",
  "message": "Instagram competitor analysis started successfully",
  "status": "processing"
}
```

#### Get Instagram Analysis Progress

```
GET /api/v1/competitor-analysis/instagram/{business_id}/task/{task_id}
```

This endpoint retrieves the progress of an ongoing Instagram competitor analysis task.

**Path Parameters:**
- `business_id`: UUID of the business idea
- `task_id`: Task identifier returned from the start endpoint

**Response:**
```json
{
  "task_id": "string",
  "progress": 0,
  "status": "string",
  "results": {
    "competitor_name": {
      "instagram_username": "string",
      "competitor_id": "string",
      "status": "string",
      "message": "string"
    }
  }
}
```

#### Cancel Instagram Analysis

```
DELETE /api/v1/competitor-analysis/instagram/task/{task_id}
```

This endpoint cancels an ongoing Instagram competitor analysis task.

**Path Parameters:**
- `task_id`: Task identifier

**Response:**
```json
{
  "message": "Instagram analysis cancelled successfully"
}
```

### Data Extraction

For each competitor, the following data is extracted:

1. **Profile Information**:
   - Username, full name, biography
   - Follower and following counts
   - Post count
   - Profile picture URL
   - Business category
   - Verification status

2. **Posts**:
   - Caption, hashtags, mentions
   - Like and comment counts
   - Post type (image, video, carousel)
   - Timestamp
   - Sponsorship status

3. **Comments**:
   - Comment text
   - Commenter username
   - Commenter profile picture

4. **Reels**:
   - Caption, hashtags, mentions
   - Like, comment, and view counts
   - Video URL
   - Timestamp

5. **IGTV Videos**:
   - Title, caption, hashtags, mentions
   - Like, comment, and view counts
   - Video URL
   - Timestamp

## Instagram Comments Analysis

The Instagram comments analysis module allows you to extract, analyze, and categorize comments from competitors' Instagram profiles.

### Endpoints

#### Scrape Comments from Posts

```
POST /api/v1/competitor-analysis/instagram-comments/{business_id}/scrape-comments
```

This endpoint scrapes comments from specific Instagram posts.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Request Body:**
```json
{
  "post_urls": ["https://www.instagram.com/p/ABCDEFG/", "https://www.instagram.com/p/HIJKLMN/"],
  "max_comments": 50
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully scraped comments from 2 posts",
  "post_count": 2,
  "comments_count": 87,
  "results": [...]
}
```

#### Categorize Comments

```
POST /api/v1/competitor-analysis/instagram-comments/{business_id}/categorize-comments
```

This endpoint categorizes Instagram comments for a specific username using an LLM.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Request Body:**
```json
{
  "username": "competitor_username",
  "provider": "openai",
  "model": "openai:gpt-4o-mini"
}
```

**Response:**
```json
{
  "status": "success",
  "username": "competitor_username",
  "total_categories": 12,
  "category_counts": {
    "Product Questions": 45,
    "Positive Feedback": 87,
    "Complaints": 23
  }
}
```

#### Analyze Sentiment and Emotions

```
POST /api/v1/competitor-analysis/instagram-comments/{business_id}/analyze-sentiment
```

This endpoint analyzes sentiment and emotions in Instagram comments for a specific username.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Request Body:**
```json
{
  "username": "competitor_username"
}
```

**Response:**
```json
{
  "status": "success",
  "username": "competitor_username",
  "total_comments_analyzed": 155,
  "sentiment_file_path": "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram/sentiment_analysis.json",
  "emotion_file_path": "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram/emotion_analysis.json"
}
```

#### Model Comment Topics

```
POST /api/v1/competitor-analysis/instagram-comments/{business_id}/model-topics
```

This endpoint performs topic modeling on Instagram comments for a specific username.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Request Body:**
```json
{
  "username": "competitor_username",
  "num_topics": 5,
  "lang": "en"
}
```

**Response:**
```json
{
  "status": "success",
  "username": "competitor_username",
  "total_topics": 5,
  "lda_topics_file_path": "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram/lda_topics.json",
  "wordcloud_file_path": "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram/wordcloud.png"
}
```

#### Complete Comments Analysis

```
POST /api/v1/competitor-analysis/instagram-comments/{business_id}/complete-comments-analysis
```

This endpoint runs a complete analysis on Instagram comments including categorization, sentiment analysis, and topic modeling.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Query Parameters:**
- `username`: Instagram username to analyze
- `num_topics`: Number of topics for topic modeling (default: 5)
- `max_comments`: Maximum number of comments to analyze per post (default: 50)
- `provider`: LLM provider name (default: "openai")
- `model`: LLM model name (default: "openai:gpt-4o-mini")
- `lang`: Language code (default: "en")

**Response:**
```json
{
  "status": "processing",
  "message": "Complete comments analysis for competitor_username started in background",
  "username": "competitor_username",
  "business_id": "88025338-e86a-41ff-9b76-b8c1889ca4ac"
}
```

## Instagram Image Analysis

The Instagram image analysis module allows you to analyze images from competitors' Instagram profiles, including individual posts and feed coherence.

### Endpoints

#### Analyze Posts Images

```
POST /api/v1/competitor-analysis/instagram-analyzer/{business_id}/analyze-posts-images
```

This endpoint analyzes images from Instagram posts for a specific username.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Request Body:**
```json
{
  "instagram_username": "competitor_username",
  "posts_limit": 20,
  "business_id": "88025338-e86a-41ff-9b76-b8c1889ca4ac"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully analyzed images from 20 posts",
  "username": "competitor_username",
  "analysis_type": "posts_images",
  "posts_analyzed": 20,
  "output_path": "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram/competitor_username/posts_image_analysis_report.json"
}
```

#### Analyze Instagram Feed

```
POST /api/v1/competitor-analysis/instagram-analyzer/{business_id}/analyze-feed
```

This endpoint analyzes Instagram feed coherence for a specific username.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Request Body:**
```json
{
  "instagram_username": "competitor_username",
  "posts_limit": 50,
  "business_id": "88025338-e86a-41ff-9b76-b8c1889ca4ac"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully analyzed feed with 50 posts in 10 batches",
  "username": "competitor_username",
  "analysis_type": "feed_coherence",
  "posts_analyzed": 50,
  "output_path": "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram/competitor_username/feed_analysis_report.json"
}
```

#### Complete Image Analysis

```
POST /api/v1/competitor-analysis/instagram-analyzer/{business_id}/complete-image-analysis
```

This endpoint runs a complete image analysis on Instagram posts and feed.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Query Parameters:**
- `instagram_username`: Instagram username to analyze
- `posts_limit`: Maximum number of posts to analyze (optional)

**Response:**
```json
{
  "status": "processing",
  "message": "Complete image analysis for competitor_username started in background",
  "username": "competitor_username",
  "business_id": "88025338-e86a-41ff-9b76-b8c1889ca4ac"
}
```

## Instagram Statistics Analysis

The Instagram statistics module allows you to generate and analyze statistics from competitors' Instagram profiles, including engagement metrics and post type distributions.

### Endpoints

#### Generate Statistics

```
POST /api/v1/competitor-analysis/instagram-statistics/{business_id}/generate-statistics
```

This endpoint generates statistics from Instagram posts for a specific username.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Request Body:**
```json
{
  "username": "competitor_username",
  "post_limit": 50,
  "image_limit": 10
}
```

**Response:**
```json
{
  "status": "success",
  "username": "competitor_username",
  "total_posts": 50,
  "total_followers": 10000,
  "avg_likes_per_post": 250.5,
  "avg_comments_per_post": 15.3,
  "avg_engagement_rate": 2.65,
  "output_path": "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram/statistics.json"
}
```

#### Complete Statistics Analysis

```
POST /api/v1/competitor-analysis/instagram-statistics/{business_id}/complete-statistics-analysis
```

This endpoint runs a complete statistics analysis on Instagram posts.

**Path Parameters:**
- `business_id`: UUID of the business idea

**Query Parameters:**
- `username`: Instagram username to analyze
- `post_limit`: Maximum number of posts to analyze (default: 50)
- `image_limit`: Maximum number of images to analyze per post (default: 10)

**Response:**
```json
{
  "status": "processing",
  "message": "Statistics analysis for competitor_username started in background",
  "username": "competitor_username",
  "business_id": "88025338-e86a-41ff-9b76-b8c1889ca4ac"
}
```

### Implementation Details

The Instagram competitor analysis is implemented using:

1. **InstagramScraper**: A service that uses the Apify API to extract data from Instagram
2. **CompetitorAnalysisController**: A controller that manages the analysis process
3. **MinioService**: A service for storing the extracted data

The analysis process runs asynchronously in the background, and progress is tracked using a simple in-memory cache. In a production environment, this should be replaced with a more robust solution like Redis.

### Dependencies

- Apify API key (set in environment variables)
- MinIO for object storage
- PostgreSQL for storing competitor information 