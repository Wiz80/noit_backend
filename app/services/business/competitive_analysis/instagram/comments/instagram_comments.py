import json
import os
from collections import defaultdict
from apify_client import ApifyClient
from app.services.storage.minio_service import MinioService
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer
import re

class InstagramComments(BaseInstagramAnalyzer):

    def __init__(self, username, post_limit, image_limit, output_folder):
        super().__init__(username, output_folder, post_limit, image_limit)

    async def scrape_instagram_comments(self, max_posts: int = 15, max_comments: int = 50):
        """
        Scrapes Instagram posts and their comments using Apify.
        Saves the raw data to a local JSON file and also returns the data as a dictionary.

        :param username: Instagram username to scrape.
        :param api_key: Apify API key.
        :param max_posts: Maximum number of posts to extract.
        :param max_comments: Maximum number of comments per post to extract.
        :return: Tuple containing the path of the saved JSON file and the raw data dictionary.
        """
        # Define local storage directory

        try:
            # Initialize Apify Client
            client = ApifyClient(self.api_key)

            # Define input parameters for the Apify scraper
            run_input = {
                "username": [self.username],  # Correct field for the Apify actor
                "resultsLimit": max_posts,
                "maxComments": max_comments,
            }

            # Execute Apify actor
            run = client.actor("apify/export-instagram-comments-posts").call(run_input=run_input)

            # Fetch results
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
            if dataset_items:
                # Save raw data to local JSON
                await self.minio_service.upload_content(
                    object_name=f"{self.output_folder}/comments_data.json",
                    data=json.dumps(dataset_items, indent=4),
                    content_type="application/json",
                    metadata={
                        "username": self.username
                    }
                )

                print(f"✅ Raw comments data saved locally: {self.output_folder}/comments_data.json")
                return dataset_items  # Return path and data for further processing
            else:
                print("⚠️ No data found for this user.")
                return None, None

        except Exception as e:
            print(f"❌ Error scraping comments: {e}")
            return None, None

    # async def transform_instagram_comments(self, raw_data: list):
    #     """
    #     Transforms raw Instagram comments data into a structured format grouped by post.
    #     Instead of reading from a file, it receives the raw data as a parameter.

    #     :param raw_data: List containing raw Instagram comment data.
    #     :param output_file: Path to save the transformed JSON file.
    #     """
    #     try:
    #         if not raw_data:
    #             print("⚠️ No data provided for processing.")
    #             return

    #         # Dictionary to store posts grouped by postId
    #         posts_dict = defaultdict(lambda: {
    #             "postId": None,
    #             "postType": None,
    #             "shortCode": None,
    #             "caption": None,
    #             "hashtags": [],
    #             "mentions": [],
    #             "url": None,
    #             "images": [],
    #             "videoUrl": None,
    #             "likesCount": 0,
    #             "timestamp": None,
    #             "ownerFullName": None,
    #             "ownerUsername": None,
    #             "ownerId": None,
    #             "isSponsored": None,
    #             "comments": []
    #         })

    #         # Iterate through comments and organize by post
    #         for comment in raw_data:
    #             post_info = comment.get("postInfo", {})

    #             post_id = post_info.get("id")
    #             if not post_id:
    #                 continue  # Skip invalid data

    #             # Populate post information
    #             posts_dict[post_id]["postId"] = post_id
    #             posts_dict[post_id]["postType"] = post_info.get("type")
    #             posts_dict[post_id]["shortCode"] = post_info.get("shortCode")
    #             posts_dict[post_id]["caption"] = post_info.get("caption")
    #             posts_dict[post_id]["hashtags"] = post_info.get("hashtags", [])
    #             posts_dict[post_id]["mentions"] = post_info.get("mentions", [])
    #             posts_dict[post_id]["url"] = post_info.get("url")
    #             posts_dict[post_id]["images"] = post_info.get("images", [])
    #             posts_dict[post_id]["videoUrl"] = post_info.get("videoUrl")
    #             posts_dict[post_id]["likesCount"] = post_info.get("likesCount", 0)
    #             posts_dict[post_id]["timestamp"] = post_info.get("timestamp")
    #             posts_dict[post_id]["ownerFullName"] = post_info.get("ownerFullName")
    #             posts_dict[post_id]["ownerUsername"] = post_info.get("ownerUsername")
    #             posts_dict[post_id]["ownerId"] = post_info.get("ownerId")
    #             posts_dict[post_id]["isSponsored"] = post_info.get("isSponsored")

    #             # Append comment
    #             posts_dict[post_id]["comments"].append({
    #                 "commentText": comment.get("commentText"),
    #                 "commentatorUserName": comment.get("commentatorUserName"),
    #                 "commentatorProfilePicUrl": comment.get("commentatorProfilePicUrl")
    #             })

    #         # Convert dictionary to list
    #         structured_data = list(posts_dict.values())


    #         await self.minio_service.upload_content(
    #             object_name=f"{self.output_folder}/processed_comments_data.json",
    #             data=json.dumps(structured_data, indent=4),
    #             content_type="application/json",
    #             metadata={
    #                 "username": self.username
    #             }
    #         )

    #         print(f"✅ Transformed data saved locally: {self.output_folder}/processed_comments_data.json")

    #     except Exception as e:
    #         print(f"❌ Error processing data: {e}")

    async def run_instagram_comments_scraper(self):
        """
        Main function to scrape Instagram comments and process the data.

        :param username: Instagram username to scrape.
        :param api_key: Apify API key.
        """
        # Step 1: Scrape Instagram Comments
        raw_data = await self.scrape_instagram_comments()

        if raw_data:
            await self.transform_instagram_comments(raw_data)


    async def extract_post_id(self, post_url: str) -> str:
        """
        Extrae el shortcode (identificador corto) del post a partir de la URL de Instagram.
        Ejemplo: de "https://www.instagram.com/p/DGSd6RcMPak" retorna "DGSd6RcMPak".
        
        :param post_url: URL del post de Instagram.
        :return: El shortcode del post o, en su defecto, la URL original.
        """
        match = re.search(r'/p/([^/]+)', post_url)
        return match.group(1) if match else post_url


    async def transform_instagram_comments(self, raw_data: list, posts_data: list) -> dict:
        """
        Transforma los datos crudos de comentarios de Instagram en un formato estructurado,
        agrupándolos por post (usando el shortcode extraído de postUrl) y asociando la información
        del post proveniente de posts_data.
        
        Para cada post se creará un objeto con:
        - post_id: El identificador principal del post (extraído del posts_data).
        - shortCode: El shortcode del post (que coincide con el extraído de la URL).
        - comments: Lista de comentarios asociados al post, donde cada comentario incluye:
            • id_comentario: El identificador único del comentario.
            • contenido: El texto del comentario.
            • ownerusername: El username del autor.
            • timestamp: La fecha y hora en que se publicó el comentario.
            • likesCount: La cantidad de "likes" recibidos.
            • ownerProfilePicUrl: La URL de la foto de perfil del autor.
        
        Se procesan también las respuestas anidadas (replies) aplicando la misma estructura.
        
        :param raw_data: Lista de diccionarios con datos crudos de comentarios de Instagram.
        :param posts_data: Lista de diccionarios con datos de posts (por ejemplo, proveniente de infinitekparis_col_posts.json).
        :return: Diccionario en el que cada clave es el shortcode y el valor es un objeto con la información del post y sus comentarios.
        """
        # Crear un diccionario de posts a partir de posts_data, indexado por shortCode.
        posts_lookup = {}
        for post in posts_data:
            shortcode = post.get("shortCode")
            if shortcode:
                posts_lookup[shortcode] = post

        # Diccionario final: clave = shortcode, valor = { "post_id": ..., "shortCode": ..., "comments": [...] }
        result = {}

        for entry in raw_data:
            # Omitir entradas con error o sin URL válida.
            if entry.get("error") or not entry.get("postUrl"):
                continue

            # Extraer el shortcode a partir de la URL del comentario.
            shortcode = await self.extract_post_id(entry["postUrl"])
            # Buscar en posts_lookup la información del post.
            post_info = posts_lookup.get(shortcode, {})
            main_post_id = post_info.get("id", None)

            # Si aún no se ha creado la entrada para este shortcode, inicializarla.
            if shortcode not in result:
                result[shortcode] = {
                    "post_id": main_post_id,
                    "shortCode": shortcode,
                    "comments": []
                }

            # Función interna para procesar un comentario (o reply)
            def process_comment(item):
                return {
                    "id_comentario": item.get("id"),
                    "contenido": item.get("text"),
                    "ownerusername": item.get("ownerUsername"),
                    "timestamp": item.get("timestamp"),
                    "likesCount": item.get("likesCount"),
                    "ownerProfilePicUrl": item.get("ownerProfilePicUrl")
                }

            # Procesar el comentario principal.
            result[shortcode]["comments"].append(process_comment(entry))

            # Procesar replies (si existen)
            replies = entry.get("replies", [])
            if isinstance(replies, list):
                for reply in replies:
                    if isinstance(reply, dict):
                        result[shortcode]["comments"].append(process_comment(reply))

        return result
