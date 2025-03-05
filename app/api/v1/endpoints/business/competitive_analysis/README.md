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