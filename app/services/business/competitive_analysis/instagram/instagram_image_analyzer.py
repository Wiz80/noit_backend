import os
import json
import base64
import colorgram
import asyncio
from PIL import Image
from openai import OpenAI
from app.services.storage.minio_service import MinioService
from sqlalchemy.orm import Session
from app.models.business.competitive_analysis.instagram import InstagramPostInfo, InstagramPostImage, InstagramImageColor, InstagramUserInfo
from datetime import datetime

class InstagramImageAnalyzer:
    """
    Clase para analizar imágenes de cuentas de Instagram utilizando OpenAI GPT-4o.
    
    Esta clase proporciona métodos para:
    - Analizar imágenes individuales con GPT-4o
    - Analizar slidecards (múltiples imágenes en un post)
    - Analizar la coherencia visual del feed completo
    - Extraer paletas de colores de las imágenes
    
    Los métodos principales implementan procesamiento asincrónico y paralelo
    para mejorar significativamente la velocidad y eficiencia, especialmente
    cuando se procesan grandes cantidades de imágenes.
    """
    def __init__(self, api_key, output_folder="/content/Instagram_Scraper"):
        """
        Initialize InstagramImageAnalyzer class.

        :param api_key: OpenAI API key.
        :param output_folder: Folder to store the output JSON files.
        """
        if not api_key:
            raise ValueError("❌ The OpenAI API key cannot be empty.")

        self.api_key = api_key
        self.output_folder = output_folder
        self.client = OpenAI(api_key=api_key)
        self.minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)

    async def encode_image_from_minio(self, object_name):
        """Encodes an image from MinIO storage to Base64 format."""
        try:
            image_data = self.minio_service.get_object_data(object_name)
            return base64.b64encode(image_data).decode("utf-8")
        except Exception as e:
            print(f"❌ Error encoding image from MinIO: {str(e)}")
            return None

    def extract_color_palette_from_bytes(self, image_bytes, num_colors=5):
        """Extracts the dominant color palette from image bytes."""
        try:
            from io import BytesIO
            image = Image.open(BytesIO(image_bytes))
            colors = colorgram.extract(image, num_colors)
            return [
                {"rgb": (c.rgb.r, c.rgb.g, c.rgb.b), "proportion": c.proportion}
                for c in colors
            ]
        except Exception as e:
            print(f"❌ Error extracting color palette: {str(e)}")
            return []

    def generate_prompt_expert(self, base64_image):
        """Generates an expert-level prompt for image analysis using GPT-4o."""
        return [
            {
                "role": "system",
                "content": "You are an expert in digital marketing, branding, color psychology, and visual analysis. Analyze the image deeply, identifying visual patterns, styles, and branding elements."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image in depth for marketing, branding, and color theory."},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }}
                ]
            }
        ]

    async def analyze_image_with_openai(self, base64_image):
        """
        Envía la imagen al modelo GPT-4o para análisis.
        
        Esta función es asincrónica para permitir paralelización, lo que reduce
        significativamente el tiempo total de procesamiento cuando se analizan
        múltiples imágenes.
        
        :param base64_image: Imagen codificada en base64.
        :return: Análisis generado por OpenAI.
        """
        try:
            # Usar GPT-4o para todas las imágenes individuales
            vision_prompt = self.generate_prompt_expert(base64_image)
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Actualizado de gpt-4-vision-preview a gpt-4o
                messages=vision_prompt,
                temperature=0.7,
                max_tokens=1200
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error analyzing the image with GPT-4o: {error_msg}")
            return f"❌ Error analyzing the image with OpenAI: {error_msg}"

    async def save_analysis_to_database(self, db: Session, business_id: str, instagram_username: str, analysis_data: dict):
        """
        Save image analysis data to database tables.
        
        :param db: Database session
        :param business_id: Business ID
        :param instagram_username: Instagram username
        :param analysis_data: Image analysis data (puede ser del formato antiguo images_analyzed o del nuevo posts_analyzed)
        """
        try:
            print(f"💾 Saving image analysis to database for {instagram_username}...")
            
            # Find a post from this account to associate the images with
            # First get the user info record
            user_info = db.query(InstagramUserInfo).filter(
                InstagramUserInfo.username == instagram_username
            ).first()
            
            if not user_info:
                print(f"⚠️ No user found for {instagram_username}. Cannot save image analysis.")
                return
            
            print(f"📋 Found user info for {instagram_username} with ID: {user_info.id}")
            
            
            # Determine data format and process accordingly
            images_processed = 0
            colors_processed = 0
            
            # Check if we have the old format (from process_images_from_minio)
            if "images_analyzed" in analysis_data:
                print("📊 Processing analysis data in the old format (images_analyzed)")
                for image_data in analysis_data.get("images_analyzed", []):
                    # Create entry in instagram_post_images
                    file_name = image_data.get("file_name")
                    llm_analysis = image_data.get("gpt4o_analysis")
                    
                    print(f"📷 Processing image: {file_name}")

                    # Then find a post from this user
                    post = db.query(InstagramPostInfo).filter(
                        InstagramPostInfo.instagram_user_id == user_info.id,
                        # if the file name has _ in name is a carousel
                        InstagramPostInfo.id_post == file_name.split("_")[0] if "_" in file_name else file_name.split(".")[0]
                    ).first()
                    
                    if not post:
                        print(f"⚠️ No posts found for {instagram_username}. Cannot save image analysis.")
                        return
                        
                    print(f"🔗 Found post with ID {post.id} to associate with images")
                    
                    # Create the post image record
                    post_image = InstagramPostImage(
                        post_id=post.id,
                        file_name=file_name,
                        llm_analysis=llm_analysis
                    )
                    
                    db.add(post_image)
                    db.flush()  # Get the post_image.id
                    images_processed += 1
                    
                    # Save the color palette
                    for color in image_data.get("color_palette", []):
                        rgb = color.get("rgb")
                        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
                            # Create a color record for each color in the palette
                            image_color = InstagramImageColor(
                                image_id=post_image.id,
                                red=rgb[0],
                                green=rgb[1],
                                blue=rgb[2],
                                proportion=color.get("proportion", 0)
                            )
                            db.add(image_color)
                            colors_processed += 1
            
            # Check if we have the new format (from process_posts_images)
            elif "posts_analyzed" in analysis_data:
                print("📊 Processing analysis data in the new format (posts_analyzed)")
                for post_data in analysis_data.get("posts_analyzed", []):
                    post_id = post_data.get("post_id")
                    post_type = post_data.get("post_type")
                    
                    # Find the post in the database
                    post = db.query(InstagramPostInfo).filter(
                        InstagramPostInfo.instagram_user_id == user_info.id,
                        InstagramPostInfo.id_post == post_id
                    ).first()
                    
                    if not post:
                        print(f"⚠️ No post found for post_id {post_id}. Skipping.")
                        continue
                    
                    print(f"📝 Processing {post_type} post: {post_id}")
                    
                    # Process each image in the post
                    for image_data in post_data.get("images", []):
                        # For single posts or individual images in slidecards
                        if "file_name" in image_data:
                            file_name = image_data.get("file_name")
                            llm_analysis = image_data.get("gpt4o_analysis")
                            
                            # Create the post image record
                            post_image = InstagramPostImage(
                                post_id=post.id,
                                file_name=file_name,
                                llm_analysis=llm_analysis
                            )
                            
                            db.add(post_image)
                            db.flush()  # Get the post_image.id
                            images_processed += 1
                            
                            # Save the color palette
                            for color in image_data.get("color_palette", []):
                                rgb = color.get("rgb")
                                if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
                                    # Create a color record for each color in the palette
                                    image_color = InstagramImageColor(
                                        image_id=post_image.id,
                                        red=rgb[0],
                                        green=rgb[1],
                                        blue=rgb[2],
                                        proportion=color.get("proportion", 0)
                                    )
                                    db.add(image_color)
                                    colors_processed += 1
                        
                        # For slidecards (which have multiple files in one analysis)
                        elif "file_names" in image_data:
                            file_names = image_data.get("file_names", [])
                            llm_analysis = image_data.get("gpt4o_analysis")
                            color_palettes = image_data.get("color_palettes", [])
                            
                            # Create an entry for each file in the slidecard
                            for idx, file_name in enumerate(file_names):
                                post_image = InstagramPostImage(
                                    post_id=post.id,
                                    file_name=file_name,
                                    llm_analysis=llm_analysis  # Same analysis for all images in slidecard
                                )
                                
                                db.add(post_image)
                                db.flush()  # Get the post_image.id
                                images_processed += 1
                                
                                # Save the color palette if available
                                if idx < len(color_palettes):
                                    palette = color_palettes[idx]
                                    for color in palette:
                                        rgb = color.get("rgb")
                                        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
                                            image_color = InstagramImageColor(
                                                image_id=post_image.id,
                                                red=rgb[0],
                                                green=rgb[1],
                                                blue=rgb[2],
                                                proportion=color.get("proportion", 0)
                                            )
                                            db.add(image_color)
                                            colors_processed += 1
            
            else:
                print("⚠️ Unknown analysis data format. Cannot save to database.")
                return
            
            # Commit all changes
            db.commit()
            print(f"✅ Successfully saved {images_processed} images and {colors_processed} colors to database for {instagram_username}")
        
        except Exception as e:
            db.rollback()
            print(f"❌ Error saving image analysis to database: {str(e)}")
            # Reraise for debugging
            raise

    
    async def process_posts_images(self, instagram_username, posts):
        """
        Procesa las imágenes de cada post (o slidecard) de un usuario de Instagram.
        
        Para cada post (con al menos 'id' y 'caption'):
        - Se listan todas las imágenes de MinIO en el directorio: {output_folder}/{instagram_username}/images/
        - Se filtran las imágenes cuyo nombre comienza con el id del post, soportando
            tanto imágenes únicas ("{id}.jpeg") como slidecards ("{id}_1.jpeg", "{id}_2.jpeg", etc.).
        - Se determina el tipo de post ("single" si es una imagen; "slidecard" si son varias).
        - Se limita el número de imágenes a enviar al análisis (según el límite definido por OpenAI).
        - En caso de post normal, se analiza cada imagen individualmente; en slidecards, se envían
            todas (hasta el máximo) en un único llamado a OpenAI, junto con el caption del post.
        - Se genera un reporte en formato JSON que incluye, para cada post, su id, caption, el tipo
            de post y el detalle del análisis.
        - Se sube el reporte a MinIO.
        
        Maneja errores en cada paso con mensajes detallados.
        
        :param instagram_username: Usuario de Instagram para construir la ruta en MinIO.
        :param posts: Lista de posts, cada uno con al menos los campos 'id' y 'caption'.
        :return: Reporte final (diccionario) con el análisis de cada post.
        """
        MAX_IMAGES_FOR_ANALYSIS = 4  # Reducido de 5 a 4 para evitar límite de tokens
        MAX_CONCURRENT_TASKS = 5  # Limitar el número de tareas concurrentes para no sobrecargar la API
        prefix = f"{self.output_folder}/{instagram_username}/images/"
        print(f"🔍 Buscando imágenes en MinIO con el prefijo: {prefix}")
        
        try:
            image_objects = self.minio_service.list_objects(prefix=prefix)
        except Exception as e:
            print(f"❌ Error al listar objetos en MinIO: {str(e)}")
            return None

        if not image_objects:
            print(f"⚠️ No se encontraron imágenes en MinIO con el prefijo {prefix}.")
            return None

        # Construir la lista de nombres de objetos (rutas) de las imágenes
        image_names = []
        for image_object in image_objects:
            try:
                object_name = image_object if isinstance(image_object, str) else image_object.object_name
                image_names.append(object_name)
            except Exception as e:
                print(f"❌ Error procesando un objeto de imagen: {str(e)}")
                continue

        # Esta función comprueba y reduce el tamaño de una imagen si es necesario
        def maybe_resize_image(image_data, max_width=800):
            try:
                from io import BytesIO
                from PIL import Image
                
                img = Image.open(BytesIO(image_data))
                width, height = img.size
                
                # Si la imagen es demasiado grande, redimensionarla
                if width > max_width:
                    ratio = max_width / width
                    new_height = int(height * ratio)
                    img = img.resize((max_width, new_height), Image.LANCZOS)
                    
                    # Guardar la imagen redimensionada
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=85)
                    return buffer.getvalue()
                
                return image_data
            except Exception as e:
                print(f"⚠️ Error al redimensionar imagen: {str(e)}")
                return image_data  # Devuelve la imagen original si hay error
        
        # Función asincrónica para procesar un post individual
        async def process_single_post(post):
            post_id = post.get("id")
            caption = post.get("caption", "")
            if not post_id:
                print("⚠️ Se encontró un post sin id; se omite.")
                return None
            
            # Filtrar imágenes cuyo nombre comienza con el post id.
            matched_images = [
                name for name in image_names
                if os.path.basename(name).startswith(post_id)
            ]
            if not matched_images:
                print(f"⚠️ No se encontraron imágenes para el post id: {post_id}")
                return None
            
            # Determinar tipo de post: "single" si hay 1 imagen, "slidecard" si hay más.
            post_type = "single" if len(matched_images) == 1 else "slidecard"
            
            # Limitar la cantidad de imágenes a procesar según el límite definido.
            if len(matched_images) > MAX_IMAGES_FOR_ANALYSIS:
                print(f"ℹ️ Para el post id {post_id} se limitarán a {MAX_IMAGES_FOR_ANALYSIS} imágenes de {len(matched_images)} encontradas.")
                matched_images = matched_images[:MAX_IMAGES_FOR_ANALYSIS]
            
            image_results = []
            base64_images = []  # Se usarán para slidecards
            
            # Procesar cada imagen encontrada
            for object_name in matched_images:
                try:
                    print(f"🖼️ Procesando imagen: {object_name} para el post id: {post_id}")
                    image_data = self.minio_service.get_object_data(object_name)
                    if not image_data:
                        print(f"⚠️ No se pudo obtener la data de la imagen {object_name}")
                        continue
                    
                    # Redimensionar imágenes grandes para reducir el tamaño del payload
                    image_data = maybe_resize_image(image_data)
                except Exception as e:
                    print(f"❌ Error al obtener datos de la imagen {object_name}: {str(e)}")
                    continue
                
                try:
                    file_name = os.path.basename(object_name)
                except Exception as e:
                    print(f"❌ Error extrayendo el nombre de archivo de {object_name}: {str(e)}")
                    file_name = object_name
                
                try:
                    palette = self.extract_color_palette_from_bytes(image_data, num_colors=5)
                except Exception as e:
                    print(f"❌ Error extrayendo la paleta de colores para {object_name}: {str(e)}")
                    palette = []
                
                try:
                    b64_image = base64.b64encode(image_data).decode("utf-8")
                    base64_images.append(b64_image)
                except Exception as e:
                    print(f"❌ Error al codificar la imagen {object_name} a base64: {str(e)}")
                    continue
                
                # Si el post es "single", analizamos la imagen individualmente.
                if post_type == "single":
                    try:
                        gpt_analysis = await self.analyze_image_with_openai(b64_image)
                        gpt_analysis += f"\n\nCaption: {caption}"
                    except Exception as e:
                        gpt_analysis = f"❌ Error analizando la imagen con OpenAI: {str(e)}"
                    image_results.append({
                        "file_name": file_name,
                        "object_path": object_name,
                        "color_palette": palette,
                        "gpt4o_analysis": gpt_analysis
                    })
            
            # Para slidecards, si hay más de una imagen, se realiza un análisis conjunto.
            if post_type == "slidecard" and base64_images:
                try:
                    # Se analiza el slidecard en conjunto y se le pasa también el caption para mayor contexto.
                    gpt_analysis = await self.analyze_slidecard_with_openai(base64_images, caption)
                except Exception as e:
                    gpt_analysis = f"❌ Error analizando el slidecard con OpenAI: {str(e)}"
                
                # Recopilar todas las paletas de colores de las imágenes del slidecard
                color_palettes = []
                file_names = []
                for idx, object_name in enumerate(matched_images):
                    try:
                        file_name = os.path.basename(object_name)
                        file_names.append(file_name)
                        if idx < len(image_results):
                            color_palettes.append(image_results[idx].get("color_palette", []))
                    except Exception as e:
                        print(f"❌ Error procesando resultado para {object_name}: {str(e)}")
                
                # Usamos un único resultado para todo el slidecard
                image_results = [{
                    "file_names": file_names,
                    "object_paths": matched_images,
                    "color_palettes": color_palettes,
                    "gpt4o_analysis": gpt_analysis
                }]
            
            return {
                "post_id": post_id,
                "caption": caption,
                "post_type": post_type,
                "images": image_results
            }
        
        # Procesar posts en paralelo con límite de concurrencia
        posts_analysis = []
        
        # Procesar los posts en lotes para controlar la concurrencia
        for i in range(0, len(posts), MAX_CONCURRENT_TASKS):
            batch = posts[i:i+MAX_CONCURRENT_TASKS]
            print(f"🔄 Procesando lote de {len(batch)} posts (total: {i+1}-{min(i+len(batch), len(posts))} de {len(posts)})")
            
            # Ejecutar las tareas en paralelo
            batch_results = await asyncio.gather(
                *[process_single_post(post) for post in batch], 
                return_exceptions=True
            )
            
            # Filtrar resultados válidos
            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"❌ Error procesando un post: {str(result)}")
                elif result is not None:
                    posts_analysis.append(result)
        
        if not posts_analysis:
            print("⚠️ No se generaron análisis para ningún post.")
            return None
        
        final_report = {
            "username": instagram_username,
            "total_posts_analyzed": len(posts_analysis),
            "posts_analyzed": posts_analysis
        }
        
        # Guardar el reporte en MinIO
        report_object_name = f"{self.output_folder}/{instagram_username}/image_analysis_report.json"
        try:
            json_data = json.dumps(final_report, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error convirtiendo el reporte a JSON: {str(e)}")
            json_data = str(final_report)
        
        try:
            await self.minio_service.upload_content(
                object_name=report_object_name,
                data=json_data,
                content_type="application/json",
                metadata={"username": instagram_username}
            )
        except Exception as e:
            print(f"❌ Error subiendo el reporte a MinIO: {str(e)}")
        
        print(f"☁️ Reporte de análisis de imágenes de posts subido a MinIO: {report_object_name}")
        return final_report

    def generate_prompt_slidecard(self, base64_images, caption):
        """
        Genera el prompt para el análisis de un slidecard usando GPT-4o.
        
        :param base64_images: Lista de imágenes codificadas en base64.
        :param caption: Texto del caption del post.
        :return: Lista de mensajes para el prompt de OpenAI.
        """
        # GPT-4o puede manejar múltiples imágenes eficientemente
        MAX_IMAGES = 8
        if len(base64_images) > MAX_IMAGES:
            print(f"⚠️ Limiting slidecard analysis to {MAX_IMAGES} images out of {len(base64_images)}")
            base64_images = base64_images[:MAX_IMAGES]
            
        system_message = {
            "role": "system",
            "content": (
                "Eres un experto en marketing digital, branding, análisis visual y colorimetría. "
                "Analiza en conjunto las siguientes imágenes, identificando patrones visuales, estilos y elementos de branding. "
                "Considera además el contexto proporcionado por el caption."
            )
        }
        
        # Create a message with multiple content parts
        content = [
            {
                "type": "text", 
                "text": f"Analiza las siguientes imágenes de un slidecard para determinar insights en marketing y branding.\nCaption: {caption}"
            }
        ]
        
        # Add each image as a content item
        for idx, b64 in enumerate(base64_images, start=1):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}"
                }
            })
        
        user_message = {
            "role": "user",
            "content": content
        }
            
        return [system_message, user_message]

    async def analyze_slidecard_with_openai(self, base64_images, caption):
        """
        Envía al modelo GPT-4o un prompt con múltiples imágenes para analizar un slidecard.
        
        Esta función es asincrónica para permitir paralelización, lo que reduce
        significativamente el tiempo total de procesamiento cuando se analizan
        múltiples slidecards simultáneamente.
        
        :param base64_images: Lista de imágenes codificadas en base64.
        :param caption: El caption asociado al post.
        :return: El análisis generado por OpenAI.
        """
        try:
            print(f"🔍 Analizando slidecard con {len(base64_images)} imágenes usando GPT-4o")
            
            # Generar prompt para GPT-4o
            vision_prompt = self.generate_prompt_slidecard(base64_images, caption)
            
            # Usar GPT-4o para todos los análisis
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=vision_prompt,
                temperature=0.7,
                max_tokens=1200
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error analizando el slidecard con GPT-4o: {error_msg}")
            
            # Si hay error y hay múltiples imágenes, intentar con menos imágenes
            if len(base64_images) > 1:
                try:
                    print("🔄 Retrying with only the first image from the slidecard")
                    # Usar solo la primera imagen
                    single_image = [base64_images[0]]
                    vision_prompt = self.generate_prompt_slidecard(single_image, caption)
                    
                    response = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=vision_prompt,
                        temperature=0.7,
                        max_tokens=1200
                    )
                    return response.choices[0].message.content + "\n\n(Nota: Este análisis se basa solo en la primera imagen del slidecard debido a limitaciones técnicas)"
                except Exception as retry_e:
                    return f"❌ Error analizando el slidecard incluso con una sola imagen: {str(retry_e)}"
            
            return f"❌ Error analizando el slidecard con GPT-4o: {error_msg}"

    def generate_prompt_feed_batch(self, batch_images):
        """
        Genera el prompt para analizar un lote de imágenes representativas del feed
        usando el modelo GPT-4o.
        
        Este método se utiliza en el análisis paralelo de lotes de imágenes del feed.
        
        :param batch_images: Lista de diccionarios con claves 'post_id', 'caption' y 'base64_image'.
        :return: Lista de mensajes para el prompt de OpenAI.
        """
        # Con GPT-4o podemos incluir hasta 9 imágenes por lote
        MAX_BATCH_IMAGES = 9
        if len(batch_images) > MAX_BATCH_IMAGES:
            print(f"⚠️ Limiting feed analysis batch to {MAX_BATCH_IMAGES} images out of {len(batch_images)}")
            batch_images = batch_images[:MAX_BATCH_IMAGES]
        
        # Create system message
        system_message = {
            "role": "system", 
            "content": "Eres un experto en marketing digital, branding y análisis visual."
        }
        
        # Create a message with multiple content parts
        context_text = (
            "Eres un experto en análisis visual de feeds de Instagram, especializado en coherencia estética, "
            "branding, composición, y estrategia visual. A continuación se presentan imágenes representativas "
            "del feed de un usuario de Instagram. Considera que cada imagen corresponde a la primera imagen de un post "
            "o slidecard y puede incluir elementos de branding, paleta de colores, estilo fotográfico y composición. "
            "Analiza la coherencia visual global del feed, identificando patrones comunes, fortalezas en la identidad "
            "de la marca, y ofreciendo recomendaciones para mejorar la consistencia y el impacto visual."
        )
        
        # Create the content array for the user message
        content = [{"type": "text", "text": context_text}]
        
        # Add details for each image and its caption
        for idx, item in enumerate(batch_images, start=1):
            # Add a text description for each image
            image_description = f"\nImagen {idx} (Post ID: {item['post_id']})"
            if item.get("caption"):
                image_description += f"\nCaption: {item['caption']}"
                
            content.append({"type": "text", "text": image_description})
            
            # Add the image
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{item['base64_image']}"
                }
            })
        
        user_message = {
            "role": "user",
            "content": content
        }
            
        return [system_message, user_message]

    async def analyze_instagram_feed(self, instagram_username, posts):
        """
        Analiza la coherencia visual y branding del feed de Instagram a partir de los posts.
        
        Para cada post (con al menos 'id' y 'caption'):
        - Se obtiene la imagen representativa desde MinIO. Si el post es slidecard, se usa solo la primera imagen.
        - Se agrupan estas imágenes en lotes.
        - Para cada lote se envía un prompt a GPT-4o que analiza la coherencia visual del feed.
        - Se agregan los resultados en un reporte final que se sube a MinIO.
        
        Esta versión paraliza el análisis de los lotes para mayor velocidad.
        
        :param instagram_username: Nombre de usuario de Instagram (para construir la ruta en MinIO).
        :param posts: Lista de posts, cada uno con al menos 'id' y 'caption'.
        :return: Diccionario con el reporte final del análisis del feed.
        """
        # Definir constantes y el prefijo de MinIO.
        MAX_BATCH_SIZE = 9  # Con GPT-4o podemos manejar hasta 9 imágenes por lote
        MAX_CONCURRENT_BATCHES = 3  # Limita el número de lotes que se analizan simultáneamente
        prefix = f"{self.output_folder}/{instagram_username}/images/"
        print(f"🔍 Buscando imágenes en MinIO con el prefijo: {prefix}")
        
        try:
            image_objects = self.minio_service.list_objects(prefix=prefix)
        except Exception as e:
            print(f"❌ Error al listar objetos en MinIO: {str(e)}")
            return None

        if not image_objects:
            print(f"⚠️ No se encontraron imágenes en MinIO con el prefijo {prefix}.")
            return None

        # Extraer las rutas/nombres de archivo de las imágenes.
        image_names = []
        for image_object in image_objects:
            try:
                object_name = image_object if isinstance(image_object, str) else image_object.object_name
                image_names.append(object_name)
            except Exception as e:
                print(f"❌ Error procesando un objeto de imagen: {str(e)}")
                continue

        # Función interna para elegir la imagen representativa de un post.
        def select_representative_image(post_id, image_list):
            rep = None
            # Buscar si existe una imagen que coincida exactamente con "{id}.jpeg" (o .jpg).
            for name in image_list:
                base = os.path.basename(name).lower()
                if base == f"{post_id}.jpeg" or base == f"{post_id}.jpg":
                    return name
            # Si no, buscar la que tenga sufijo _1 (ordenado alfabéticamente).
            candidates = [name for name in image_list if os.path.basename(name).startswith(f"{post_id}_")]
            if candidates:
                return sorted(candidates)[0]
            return rep

        # Función para redimensionar imágenes grandes
        def maybe_resize_image(image_data, max_width=800):
            try:
                from io import BytesIO
                from PIL import Image
                
                img = Image.open(BytesIO(image_data))
                width, height = img.size
                
                # Si la imagen es demasiado grande, redimensionarla
                if width > max_width:
                    ratio = max_width / width
                    new_height = int(height * ratio)
                    img = img.resize((max_width, new_height), Image.LANCZOS)
                    
                    # Guardar la imagen redimensionada
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=85)
                    return buffer.getvalue()
                
                return image_data
            except Exception as e:
                print(f"⚠️ Error al redimensionar imagen: {str(e)}")
                return image_data  # Devuelve la imagen original si hay error

        # Recopilar las imágenes representativas del feed.
        feed_images = []
        for post in posts:
            post_id = post.get("id")
            caption = post.get("caption", "")
            if not post_id:
                print("⚠️ Se encontró un post sin id; se omite.")
                continue

            # Filtrar imágenes que comiencen con el post_id.
            matched_images = [name for name in image_names if os.path.basename(name).startswith(post_id)]
            if not matched_images:
                print(f"⚠️ No se encontró imagen representativa para el post id: {post_id}")
                continue

            rep_image_path = select_representative_image(post_id, matched_images)
            if not rep_image_path:
                print(f"⚠️ No se pudo seleccionar imagen representativa para el post id: {post_id}")
                continue

            try:
                image_data = self.minio_service.get_object_data(rep_image_path)
                if not image_data:
                    print(f"⚠️ No se pudo obtener data de la imagen {rep_image_path} para el post id: {post_id}")
                    continue
                    
                # Redimensionar imágenes grandes para reducir el tamaño del payload
                image_data = maybe_resize_image(image_data)
            except Exception as e:
                print(f"❌ Error al obtener data de la imagen {rep_image_path}: {str(e)}")
                continue

            try:
                b64_image = base64.b64encode(image_data).decode("utf-8")
            except Exception as e:
                print(f"❌ Error al codificar la imagen {rep_image_path} a base64: {str(e)}")
                continue

            feed_images.append({
                "post_id": post_id,
                "caption": caption,
                "object_path": rep_image_path,
                "base64_image": b64_image
            })

        if not feed_images:
            print("⚠️ No se obtuvieron imágenes representativas para el análisis del feed.")
            return None

        # Agrupar las imágenes en lotes de MAX_BATCH_SIZE.
        batches = [feed_images[i:i+MAX_BATCH_SIZE] for i in range(0, len(feed_images), MAX_BATCH_SIZE)]
        
        # Función asincrónica para analizar un lote de imágenes
        async def analyze_batch(batch_idx, batch):
            print(f"🔎 Analizando lote {batch_idx+1} de {len(batches)} (con {len(batch)} imágenes)...")
            
            try:
                print(f"🔍 Analizando feed con GPT-4o")
                prompt = self.generate_prompt_feed_batch(batch)
                
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=prompt,
                    temperature=0.7,
                    max_tokens=1200
                )
                analysis = response.choices[0].message.content
                model_used = "gpt-4o"
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Error analizando el lote con GPT-4o: {error_msg}")
                
                # Si hay error, intentar con un subset más pequeño
                if len(batch) > 3:
                    try:
                        # Intentar con la mitad de las imágenes
                        reduced_batch = batch[:len(batch)//2]
                        print(f"🔄 Retrying with a smaller batch of {len(reduced_batch)} images")
                        
                        prompt = self.generate_prompt_feed_batch(reduced_batch)
                        response = self.client.chat.completions.create(
                            model="gpt-4o",
                            messages=prompt,
                            temperature=0.7,
                            max_tokens=1200
                        )
                        analysis = response.choices[0].message.content + "\n\n(Nota: Este análisis se basa en un subconjunto de imágenes del lote debido a limitaciones técnicas)"
                        model_used = "gpt-4o (reduced batch)"
                    except Exception as retry_e:
                        analysis = f"❌ Error analizando el lote {batch_idx+1}: {str(retry_e)}"
                        model_used = "error"
                else:
                    analysis = f"❌ Error analizando el lote {batch_idx+1}: {error_msg}"
                    model_used = "error"
            
            return {
                "batch_number": batch_idx+1,
                "post_ids": [item["post_id"] for item in batch],
                "analysis": analysis,
                "model_used": model_used
            }
        
        # Procesar los lotes en paralelo con límite de concurrencia
        batch_results = []
        
        # Procesar en grupos para controlar la concurrencia
        for i in range(0, len(batches), MAX_CONCURRENT_BATCHES):
            current_batches = batches[i:i+MAX_CONCURRENT_BATCHES]
            print(f"⏳ Procesando grupo de {len(current_batches)} lotes (total: {i+1}-{min(i+len(current_batches), len(batches))} de {len(batches)})")
            
            # Ejecutar el análisis de lotes en paralelo
            results = await asyncio.gather(
                *[analyze_batch(i+j, batch) for j, batch in enumerate(current_batches)],
                return_exceptions=True
            )
            
            # Filtrar resultados válidos
            for result in results:
                if isinstance(result, Exception):
                    print(f"❌ Error procesando un lote: {str(result)}")
                else:
                    batch_results.append(result)
        
        # Ordenar los resultados por número de lote para mantener el orden original
        batch_results.sort(key=lambda x: x["batch_number"])
        
        # Construir el reporte final.
        report_summary = {
            "summary": (
                "Análisis del feed de Instagram basado en coherencia visual, branding y estética global. "
                "Cada lote representa hasta 9 imágenes representativas (la primera de cada post o slidecard). "
                "Análisis realizado exclusivamente con GPT-4o."
            ),
            "total_posts_analyzed": len(feed_images),
            "total_batches": len(batches),
            "model_used": "gpt-4o"
        }
        final_report = {
            "global_analysis": report_summary,
            "batch_analyses": batch_results,
            "detailed_posts": [{
                "post_id": item["post_id"], 
                "caption": item["caption"],
                "object_path": item["object_path"]
            } for item in feed_images]  # Versión reducida sin las imágenes base64 para ahorrar espacio
        }

        try:
            json_data = json.dumps(final_report, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error convirtiendo el reporte final a JSON: {str(e)}")
            json_data = str(final_report)

        report_object_name = f"{self.output_folder}/{instagram_username}/feed_analysis_report.json"
        try:
            await self.minio_service.upload_content(
                object_name=report_object_name,
                data=json_data,
                content_type="application/json",
                metadata={"username": instagram_username}
            )
        except Exception as e:
            print(f"❌ Error subiendo el reporte a MinIO: {str(e)}")
        
        print(f"☁️ Reporte de análisis del feed subido a MinIO: {report_object_name}")
        return final_report

    async def analyze_images(self):
        """
        Analyze all images available in MinIO for the given output folder.
        
        This method scans the output folder for images, processes them,
        and saves the analysis results.
        
        :return: Dictionary with analysis results
        """
        try:
            print(f"🔎 Analyzing images in output folder: {self.output_folder}")
            
            # Get list of image objects from MinIO
            image_prefix = f"{self.output_folder}/images/"
            image_objects = self.minio_service.list_objects(prefix=image_prefix)
            
            if not image_objects:
                print(f"⚠️ No images found in {image_prefix}")
                return {"status": "error", "message": "No images found"}
            
            # Process images and get their analysis
            results = []
            
            for image_object in image_objects:
                try:
                    object_name = image_object if isinstance(image_object, str) else image_object.object_name
                    file_name = os.path.basename(object_name)
                    
                    # Encode image to base64
                    base64_image = await self.encode_image_from_minio(object_name)
                    if not base64_image:
                        continue
                    
                    # Get image data for color extraction
                    image_data = self.minio_service.get_object_data(object_name)
                    if not image_data:
                        continue
                    
                    # Extract color palette
                    color_palette = self.extract_color_palette_from_bytes(image_data)
                    
                    # Analyze image with OpenAI
                    gpt4o_analysis = await self.analyze_image_with_openai(base64_image)
                    
                    # Add to results
                    results.append({
                        "file_name": file_name,
                        "gpt4o_analysis": gpt4o_analysis,
                        "color_palette": color_palette
                    })
                    
                    print(f"✓ Analyzed image: {file_name}")
                    
                except Exception as e:
                    print(f"❌ Error processing image: {str(e)}")
            
            # Save results to MinIO
            analysis_data = {
                "images_analyzed": results,
                "total_images": len(results),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            analysis_json = json.dumps(analysis_data, ensure_ascii=False, indent=2)
            output_path = f"{self.output_folder}/image_analysis.json"
            
            await self.minio_service.upload_content(
                object_name=output_path,
                data=analysis_json,
                content_type="application/json"
            )
            
            print(f"💾 Saved image analysis to {output_path}")
            return {"status": "success", "analysis": analysis_data}
            
        except Exception as e:
            error_message = f"Error analyzing images: {str(e)}"
            print(f"❌ {error_message}")
            return {"status": "error", "message": error_message}