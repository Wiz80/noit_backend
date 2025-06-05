# Taskiq tasks module

# Import the broker first
from .broker import broker

# Import all tasks to register them with the broker
from . import competitor_analysis_tasks
from . import social_media_extraction_tasks
from . import instagram_analysis_tasks

from .competitor_analysis_tasks import research_competitors_task
from .social_media_extraction_tasks import extract_social_media_from_websites_task
from .instagram_analysis_tasks import run_instagram_full_analysis_task, complete_instagram_comments_analysis_task, complete_instagram_image_analysis_task, complete_instagram_statistics_analysis_task

__all__ = [
    'broker',
    'research_competitors_task',
    'extract_social_media_from_websites_task',
    'run_instagram_full_analysis_task',
    'complete_instagram_comments_analysis_task',
    'complete_instagram_image_analysis_task',
    'complete_instagram_statistics_analysis_task'
] 