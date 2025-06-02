# Instagram Analysis Testing Module

This module contains tests for the Instagram analysis services, particularly focused on competitive analysis features.

## Available Tests

### Instagram Comments Analyzer

Tests the transformation of Instagram comments data collected for a competitor.

**File**: `test_instagram_comments_analyzer.py`

**How to run**:
```bash
python -m tests.services.test_instagram_comments_analyzer
```

### Instagram Sentiment and Emotion Analyzer

Tests the sentiment and emotion analysis of Instagram comments for a competitor.

**File**: `test_instagram_sentiment_emotion_analyzer.py`

**How to run**:
```bash
python -m tests.services.test_instagram_sentiment_emotion_analyzer
```

## Test Configuration

These tests require:

1. **Valid MinIO Credentials**: Configured via environment variables or `settings.py`
2. **APIFY_API_KEY**: Set as an environment variable
3. **Database Connection**: Configured in `app/db/session.py`

## Test Data

Tests use the following sample data for business ID `88025338-e86a-41ff-9b76-b8c1889ca4ac`:
- Competitor: `bulldogskincare`
- Data stored in MinIO under path: `{business_id}/competitor-analysis/instagram/{instagram_username}/`

## Test Flow

### Comments Analyzer Test
1. Fetches raw comments data from MinIO
2. Fetches posts data from MinIO
3. Transforms the comments using InstagramComments class
4. Saves transformed data back to MinIO
5. Reports summary of transformation

### Sentiment and Emotion Analyzer Test
1. Verifies processed comments data exists in MinIO
2. Sets up necessary database records if they don't exist
3. Runs sentiment and emotion analysis 
4. Verifies result files were created in MinIO
5. Reports summary of analysis results

## Debugging

Each test includes breakpoints for debugging:
- BREAKPOINT 1: After initializing parameters
- BREAKPOINT 2: After fetching/verifying data
- BREAKPOINT 3: After processing/analysis

Logging is configured at DEBUG level to provide detailed information during test execution. 