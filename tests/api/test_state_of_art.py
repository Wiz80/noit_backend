import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.state_of_art import MarketStateOfArt, StatusEnum

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    """Mock database session for testing"""
    mock_session = MagicMock()
    
    # Mock business idea
    mock_business_idea = MagicMock(spec=BusinessIdea)
    mock_business_idea.id = "test-business-id"
    mock_business_idea.title = "Test Business"
    mock_business_idea.description = "Test Description"
    mock_business_idea.mission = "Test Mission"
    mock_business_idea.vision = "Test Vision"
    
    # Mock query results
    mock_session.query.return_value.filter.return_value.first.return_value = mock_business_idea
    
    # Mock state of art record
    mock_state_of_art = MagicMock(spec=MarketStateOfArt)
    mock_state_of_art.id = "test-state-of-art-id"
    mock_state_of_art.business_idea_id = "test-business-id"
    mock_state_of_art.market_research_status = StatusEnum.PENDING
    mock_state_of_art.state_of_art_status = StatusEnum.PENDING
    
    # Set up the query to return the mock state of art record
    mock_session.query.return_value.filter.return_value.first.side_effect = [
        mock_business_idea,  # First call returns business idea
        mock_state_of_art    # Second call returns state of art record
    ]
    
    return mock_session

@pytest.fixture
def mock_minio_client():
    """Mock MinIO client for testing"""
    mock_client = MagicMock()
    
    # Mock get_object_data to return a JSON string
    mock_client.get_object_data.return_value = json.dumps({
        "category1": {
            "title": "Category 1",
            "description": "Description 1",
            "questions": ["Question 1", "Question 2"]
        },
        "category2": {
            "title": "Category 2",
            "description": "Description 2",
            "questions": ["Question 3", "Question 4"]
        }
    })
    
    # Mock upload_content to do nothing
    mock_client.upload_content = MagicMock()
    
    return mock_client

@pytest.fixture
def mock_research_module():
    """Mock ResearchModule for testing"""
    mock_module = MagicMock()
    mock_module.search_and_answer.return_value = {
        "answer": "Test answer",
        "sources": ["Source 1", "Source 2"]
    }
    return mock_module

@patch("app.api.deps.get_db")
@patch("app.api.deps.get_minio_client")
@patch("app.services.business.business_understanding.state_of_art.ResearchModule")
async def test_state_of_art_test_mode(
    mock_research_module_class,
    mock_get_minio_client,
    mock_get_db,
    mock_db_session,
    mock_minio_client,
    mock_research_module
):
    """Test that state of art endpoint works correctly in test mode"""
    # Set up mocks
    mock_get_db.return_value = mock_db_session
    mock_get_minio_client.return_value = mock_minio_client
    mock_research_module_class.return_value = mock_research_module
    
    # Mock the generate_market_research_questions method
    with patch(
        "app.services.business.business_understanding.state_of_art.MarketStateOfArtService.generate_market_research_questions"
    ) as mock_generate_market_research:
        # Mock the generate_state_of_art_questions method
        with patch(
            "app.services.business.business_understanding.state_of_art.MarketStateOfArtService.generate_state_of_art_questions"
        ) as mock_generate_state_of_art:
            # Set up mock return values
            mock_generate_market_research.return_value = {
                "category1": {
                    "title": "Market Category 1",
                    "subitems": [
                        {
                            "title": "Subcategory 1",
                            "questions": ["Market Q1", "Market Q2", "Market Q3", "Market Q4"]
                        }
                    ]
                },
                "category2": {
                    "title": "Market Category 2",
                    "subitems": [
                        {
                            "title": "Subcategory 2",
                            "questions": ["Market Q5", "Market Q6", "Market Q7", "Market Q8"]
                        }
                    ]
                }
            }
            
            mock_generate_state_of_art.return_value = {
                "category1": {
                    "title": "State of Art Category 1",
                    "subitems": [
                        {
                            "title": "Subcategory 1",
                            "questions": ["SoA Q1", "SoA Q2", "SoA Q3", "SoA Q4"]
                        }
                    ]
                },
                "category2": {
                    "title": "State of Art Category 2",
                    "subitems": [
                        {
                            "title": "Subcategory 2",
                            "questions": ["SoA Q5", "SoA Q6", "SoA Q7", "SoA Q8"]
                        }
                    ]
                }
            }
            
            # Make the request to the endpoint
            response = client.post(
                "/api/v1/business-understanding/business/test-business-id/state-of-art",
                params={"test_mode": True, "test_questions_limit": 2}
            )
            
            # Check that the response is successful
            assert response.status_code == 200
            
            # Check that the response contains the expected data
            data = response.json()
            assert data["success"] is True
            assert data["business_id"] == "test-business-id"
            assert "state_of_art_path" in data
            
            # Verify that the test_mode parameter was passed to the service
            # This is done by checking the call to ResearchModule.search_and_answer
            # We expect it to be called only for the first 2 questions in each category
            
            # Count the number of calls to search_and_answer
            assert mock_research_module.search_and_answer.call_count <= 4  # 2 categories x 2 questions
            
            # Verify that the results were saved to MinIO
            assert mock_minio_client.upload_content.call_count == 2  # One for market research, one for state of art 