"""
LinkedIn Library Scraper Module

This module provides utility functions for LinkedIn scraping operations,
including building search URLs and other helper functions.
"""
import urllib.parse
from typing import Optional, Dict, Any


def build_search_url(company_id: str, search_type: str = "ads", **kwargs) -> str:
    """
    Build a LinkedIn search URL for various search types.
    
    Args:
        company_id: The LinkedIn company ID or slug
        search_type: The type of search ('ads', 'posts', etc.)
        **kwargs: Additional parameters for the search URL
    
    Returns:
        str: The constructed search URL
    """
    base_url = "https://www.linkedin.com"
    
    if search_type == "ads":
        # Default parameters for ads search
        params = {
            "date": kwargs.get("date_option", "last-30-days"),
            "country": kwargs.get("country", "ALL"),
        }
        
        # Build ads library URL
        url = f"{base_url}/ads/search?companyId={company_id}"
        
        # Add additional parameters
        for key, value in params.items():
            if value:
                url += f"&{key}={urllib.parse.quote(str(value))}"
                
        return url
    
    elif search_type == "posts":
        # Build posts URL
        url = f"{base_url}/company/{company_id}/posts/"
        return url
    
    elif search_type == "company":
        # If company_id is a full URL, return it
        if company_id.startswith(base_url):
            return company_id
        
        # Otherwise, build company URL
        url = f"{base_url}/company/{company_id}/"
        return url
    
    # Default to company URL
    return f"{base_url}/company/{company_id}/"


def extract_company_id_from_url(linkedin_url: str) -> Optional[str]:
    """
    Extract company ID or slug from a LinkedIn URL.
    
    Args:
        linkedin_url: The LinkedIn company URL
    
    Returns:
        Optional[str]: The extracted company ID or None if not found
    """
    if not linkedin_url:
        return None
    
    # Clean and parse URL
    url_parts = linkedin_url.strip().split('/')
    
    # Remove empty parts
    url_parts = [part for part in url_parts if part]
    
    # Look for the company part
    for i, part in enumerate(url_parts):
        if part == "company" and i < len(url_parts) - 1:
            # Return the part after "company"
            return url_parts[i+1].split("?")[0]
    
    # If URL ends with a company ID (like linkedin.com/company/123)
    if "company" in url_parts and len(url_parts) > url_parts.index("company") + 1:
        return url_parts[url_parts.index("company") + 1]
    
    # Could not extract company ID
    return None 