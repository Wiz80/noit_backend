#TODO: BORRAR

from app.services.business.competitive_analysis.instagram.instagram_img_scraper import InstagramImageScraper
from app.services.business.competitive_analysis.instagram.instagram_user_scraper import InstagramUserScraper
from app.services.business.competitive_analysis.instagram.instragram_statistics import InstagramStatistics
import asyncio

async def main():


    # instagram_scraper = InstagramImageScraper(
    #     username="dindacosmetics",
    #     post_limit= 5,
    #     image_limit= 5,
    #     output_folder= "6b0220ab-2377-4e75-bf1e-8cc78e3984d9/competitor-analysis/instagram/dindacosmetics"
    # )
    # await instagram_scraper.lattice_scrap()

    # instagram_user_scraper = InstagramUserScraper(
    #     username="dindacosmetics",
    #     post_limit= 5,
    #     image_limit= 5,
    #     output_folder= "6b0220ab-2377-4e75-bf1e-8cc78e3984d9/competitor-analysis/instagram/dindacosmetics"
    # )

    instagram_user_scraper = InstagramStatistics(
        username="dindacosmetics",
        post_limit= 5,
        image_limit= 5,
        output_folder= "6b0220ab-2377-4e75-bf1e-8cc78e3984d9/competitor-analysis/instagram/dindacosmetics"
    )

    await instagram_user_scraper.generate_statistics()


if __name__ == "__main__":

    asyncio.run(main())