import json
from transformers import pipeline
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer
from app.models.business.competitive_analysis.instagram import (
    InstagramUserInfo, 
    InstagramPostInfo, 
    InstagramComment,
    InstagramCommentSentiment, 
    InstagramCommentEmotion,
    InstagramPostSentimentSummary,
    InstagramUserSentimentOverview
)
from app.db.session import SessionLocal
from sqlalchemy import func
from collections import defaultdict
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Initialize database session
session = SessionLocal()

class InstagramSentimentEmotionAnalyzer(BaseInstagramAnalyzer):
    def __init__(self, username, output_folder):
        super().__init__(username, output_folder)
        self.sentiment_model = "pysentimiento/robertuito-sentiment-analysis"
        self.emotion_model = "pysentimiento/robertuito-emotion-analysis"
        self.sentiment_pipeline = pipeline(
            task="text-classification",
            model=self.sentiment_model,
            tokenizer=self.sentiment_model,
            return_all_scores=True,
            device=-1
        )
        self.emotion_pipeline = pipeline(
            task="text-classification",
            model=self.emotion_model,
            tokenizer=self.emotion_model,
            return_all_scores=True,
            device=-1
        )

    async def load_processed_comments(self):
        """
        Carga los comentarios procesados desde MinIO y los convierte en una lista plana
        de comentarios para facilitar el análisis.
        
        A diferencia del método load_comments, este método:
        1. Busca específicamente el archivo processed_comments_data.json
        2. Procesa la estructura de datos anidada (dictionary con post_id como claves o lista de posts)
        3. Devuelve una lista plana de comentarios con información del post incluida
        
        Returns:
            list: Lista de comentarios formateados para el análisis
        """
        try:
            comments_list = []
            
            # Try the correct path first
            processed_comments_path = f"{self.output_folder}/{self.username}/processed_comments_data.json"
            logger.debug(f"Buscando comentarios procesados en: {processed_comments_path}")
            
            # Obtener los datos del archivo - sin usar await ya que get_object_data devuelve directamente bytes
            comments_data = self.minio_service.get_object_data(processed_comments_path)
            
            # If not found, try alternative legacy paths for backward compatibility
            if not comments_data:
                logger.warning(f"No se encontraron comentarios en la ruta principal: {processed_comments_path}")
                
                # Try legacy path 1: with 'businesses' prefix
                legacy_path_1 = f"businesses/{self.output_folder}/{self.username}/processed_comments_data.json"
                logger.debug(f"Intentando ruta legacy 1: {legacy_path_1}")
                comments_data = self.minio_service.get_object_data(legacy_path_1)
                
                if comments_data:
                    logger.info(f"✅ Datos encontrados en ruta legacy 1: {legacy_path_1}")
                else:
                    # Try legacy path 2: old instagram structure
                    business_id = self.output_folder.split('/')[0] if '/' in self.output_folder else self.output_folder
                    legacy_path_2 = f"businesses/{business_id}/instagram/{self.username}/processed_comments_data.json"
                    logger.debug(f"Intentando ruta legacy 2: {legacy_path_2}")
                    comments_data = self.minio_service.get_object_data(legacy_path_2)
                    
                    if comments_data:
                        logger.info(f"✅ Datos encontrados en ruta legacy 2: {legacy_path_2}")
                    else:
                        logger.warning(f"No se encontraron comentarios procesados en ninguna ruta")
                        return []
            
            # Parsear el JSON (puede ser un diccionario {post_id: {...}} o una lista de posts)
            posts_data = json.loads(comments_data.decode('utf-8'))
            
            # Determinar si es lista o diccionario y procesar adecuadamente
            if isinstance(posts_data, list):
                # Formato nuevo: lista de posts
                logger.info(f"Datos de comentarios en formato de lista con {len(posts_data)} posts")
                posts_list = posts_data
                
                # Procesar cada post en la lista
                post_count = len(posts_list)
                comment_count = 0
                
                for post in posts_list:
                    if not isinstance(post, dict):
                        continue
                    
                    post_id = post.get("postId", "")
                    
                    # Verificar que el post tenga comentarios
                    if not "comments" in post or not isinstance(post["comments"], list):
                        continue
                    
                    for comment in post.get("comments", []):
                        # Añadir información del post a cada comentario
                        comment["post_id"] = post_id
                        comment["shortCode"] = post.get("shortCode", post_id)
                        comment["postUrl"] = post.get("postUrl", f"https://www.instagram.com/p/{post_id}/")
                        
                        # Renombrar campos si es necesario para compatibilidad
                        if "id" in comment and not "id_comentario" in comment:
                            comment["id_comentario"] = comment["id"]
                        if "text" in comment and not "contenido" in comment:
                            comment["contenido"] = comment["text"]
                        if "ownerUsername" in comment and not "ownerusername" in comment:
                            comment["ownerusername"] = comment["ownerUsername"]
                        
                        comments_list.append(comment)
                        comment_count += 1
                        
                        # Procesar también las respuestas si existen
                        for reply in comment.get("replies", []):
                            if isinstance(reply, dict):
                                reply["post_id"] = post_id
                                reply["shortCode"] = post.get("shortCode", post_id)
                                reply["postUrl"] = post.get("postUrl", f"https://www.instagram.com/p/{post_id}/")
                                
                                # Renombrar campos para replies también
                                if "id" in reply and not "id_comentario" in reply:
                                    reply["id_comentario"] = reply["id"]
                                if "text" in reply and not "contenido" in reply:
                                    reply["contenido"] = reply["text"]
                                if "ownerUsername" in reply and not "ownerusername" in reply:
                                    reply["ownerusername"] = reply["ownerUsername"]
                                    
                                comments_list.append(reply)
                                comment_count += 1
                
            elif isinstance(posts_data, dict):
                # Formato anterior: diccionario con post_id como claves
                logger.info(f"Datos de comentarios en formato de diccionario con {len(posts_data)} posts")
                posts_dict = posts_data
                
                # Aplanar la estructura para tener una lista de comentarios
                post_count = 0
                comment_count = 0
                
                for post_id, post_data in posts_dict.items():
                    post_count += 1
                    
                    # Verificar que el post tenga comentarios
                    if not "comments" in post_data or not isinstance(post_data["comments"], list):
                        continue
                    
                    for comment in post_data.get("comments", []):
                        # Añadir información del post a cada comentario
                        comment["post_id"] = post_data.get("post_id", "")
                        comment["shortCode"] = post_id
                        comment["postUrl"] = f"https://www.instagram.com/p/{post_id}/"
                        
                        # Renombrar campos si es necesario para compatibilidad
                        if "id_comentario" in comment and not "id" in comment:
                            comment["id"] = comment["id_comentario"]
                        if "contenido" in comment and not "text" in comment:
                            comment["text"] = comment["contenido"]
                        if "ownerusername" in comment and not "ownerUsername" in comment:
                            comment["ownerUsername"] = comment["ownerusername"]
                        
                        comments_list.append(comment)
                        comment_count += 1
                        
                        # Procesar también las respuestas si existen
                        for reply in comment.get("replies", []):
                            if isinstance(reply, dict):
                                reply["post_id"] = post_data.get("post_id", "")
                                reply["shortCode"] = post_id
                                reply["postUrl"] = f"https://www.instagram.com/p/{post_id}/"
                                
                                # Renombrar campos para replies también
                                if "id_comentario" in reply and not "id" in reply:
                                    reply["id"] = reply["id_comentario"]
                                if "contenido" in reply and not "text" in reply:
                                    reply["text"] = reply["contenido"]
                                if "ownerusername" in reply and not "ownerUsername" in reply:
                                    reply["ownerUsername"] = reply["ownerusername"]
                                    
                                comments_list.append(reply)
                                comment_count += 1
            else:
                logger.error(f"Formato de datos de comentarios inválido. No es ni lista ni diccionario: {type(posts_data)}")
                return []
            
            logger.info(f"Se encontraron {comment_count} comentarios en {post_count} posts")
            print(f"📊 Procesados {comment_count} comentarios de {post_count} posts")
            return comments_list
            
        except Exception as e:
            logger.exception(f"Error cargando comentarios procesados: {e}")
            print(f"❌ Error cargando comentarios procesados: {e}")
            return []

    async def analyze_sentiment_and_emotions(self):
        """
        Analiza el sentimiento y las emociones de los comentarios de Instagram y almacena
        los resultados en MinIO y en la base de datos. Utiliza los nuevos campos del archivo
        de comentarios (clave "contenido" para el texto) y agrupa los resultados por el id del post.
        Se asume que el post_id aquí corresponde al shortcode extraído de postUrl (y asociado con el post_id real
        desde el archivo de posts).

        Para cada comentario (y sus replies anidados) se extraen los siguientes campos:
        - post_id: Extraído de postUrl mediante extract_post_id().
        - comment_id: El id del comentario.
        - comment_text: El texto del comentario (clave "contenido").
        - owner_username: El username del autor (clave "ownerUsername").
        - owner_profile_pic_url: La URL de la foto de perfil (clave "ownerProfilePicUrl").
        - timestamp: Fecha y hora de publicación (clave "timestamp").
        - likes_count: Cantidad de likes recibidos (clave "likesCount").

        Se ejecutan pipelines de análisis de sentimiento y emociones sobre el texto (después de limpiarlo)
        y se almacenan tanto a nivel individual (por comentario) como en resumen por post y a nivel global
        (usuario).

        Además, se consideran métricas adicionales (como repliesCount o detalles del owner) para enriquecer el análisis.
        Los resultados se guardan en MinIO (sentiment_analysis.json y emotion_analysis.json) y se actualizan los registros
        en la base de datos para:
        - Cada comentario (sentimiento y emociones).
        - Resumen a nivel de post (agrupados por post_id, que es el shortcode).
        - Resumen a nivel de usuario (overview general).
        """
        try:
            # Cargar los comentarios transformados usando el nuevo método para obtener estructura correcta
            raw_comments = await self.load_processed_comments()
            if not raw_comments:
                print("❌ No se encontraron comentarios procesados.")
                return

            # Obtener usuario de Instagram desde la base de datos
            instagram_user = session.query(InstagramUserInfo).filter_by(username=self.username).first()
            if not instagram_user:
                print(f"⚠️ Usuario Instagram {self.username} no encontrado en la base de datos.")
                return

            # Obtener todos los posts asociados al usuario
            posts_db = session.query(InstagramPostInfo).filter_by(instagram_user_id=instagram_user.id).all()
            if not posts_db:
                print(f"⚠️ No se encontraron posts para el usuario {self.username}.")
                return

            # Crear un mapeo de shortcode a post_id de la base de datos
            shortcode_to_db_post_id = {}
            for post in posts_db:
                if hasattr(post, 'shortcode') and post.shortcode:
                    shortcode_to_db_post_id[post.shortcode] = post.id
                    logger.debug(f"Mapeo shortcode {post.shortcode} -> post_id {post.id}")

            # Diccionario para agrupar el resumen de sentimiento por post (clave = post_id, en este caso el shortcode)
            post_sentiment_summaries = defaultdict(lambda: {"total": 0, "positive": 0, "negative": 0, "neutral": 0})
            
            # Contadores globales a nivel de usuario
            total_comments = 0
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            
            sentiment_results = []
            emotion_results = []
            
            # Iterar sobre cada comentario (incluyendo replies) del nuevo formato
            for entry in raw_comments:
                # Omitir entradas con error
                if entry.get("error"):
                    continue

                # Extraer el post_id (shortcode) y buscar en el mapeo para obtener el post_id real
                post_shortcode = entry.get("shortCode") or await self.extract_post_id(entry.get("postUrl", ""))
                if not post_shortcode:
                    logger.warning(f"No se pudo determinar el shortcode para un comentario, omitiendo.")
                    continue
                
                # Usar el mapeo para convertir shortcode a post_id de base de datos si es posible
                db_post_id = shortcode_to_db_post_id.get(post_shortcode, post_shortcode)
                
                total_comments += 1
                # Utilizar la clave "contenido" o "text" para el texto del comentario
                raw_text = entry.get("contenido") or entry.get("text", "")
                if not raw_text:
                    logger.warning(f"Comentario sin texto, omitiendo análisis.")
                    continue
                    
                cleaned_text = self.clean_text(raw_text)

                # Ejecutar pipeline de sentimiento
                sentiment_response = self.sentiment_pipeline(cleaned_text)[0]
                top_sentiment = max(sentiment_response, key=lambda x: x["score"])
                sentiment_results.append({
                    "post_id": post_shortcode,
                    "db_post_id": db_post_id,
                    "comment_id": entry.get("id") or entry.get("id_comentario"),
                    "comment_text": raw_text,
                    "owner_username": entry.get("ownerUsername") or entry.get("ownerusername"),
                    "owner_profile_pic_url": entry.get("ownerProfilePicUrl"),
                    "timestamp": entry.get("timestamp"),
                    "likes_count": entry.get("likesCount"),
                    "scores": sentiment_response,
                    "top_label": top_sentiment["label"]
                })

                # Actualizar contadores de resumen
                post_sentiment_summaries[post_shortcode]["total"] += 1
                if top_sentiment["label"] == "POS":
                    positive_count += 1
                    post_sentiment_summaries[post_shortcode]["positive"] += 1
                elif top_sentiment["label"] == "NEG":
                    negative_count += 1
                    post_sentiment_summaries[post_shortcode]["negative"] += 1
                else:
                    neutral_count += 1
                    post_sentiment_summaries[post_shortcode]["neutral"] += 1

                # Ejecutar pipeline de emociones
                emotion_response = self.emotion_pipeline(cleaned_text)[0]
                top_emotion = max(emotion_response, key=lambda x: x["score"])
                emotion_results.append({
                    "post_id": post_shortcode,
                    "db_post_id": db_post_id,
                    "comment_id": entry.get("id") or entry.get("id_comentario"),
                    "comment_text": raw_text,
                    "owner_username": entry.get("ownerUsername") or entry.get("ownerusername"),
                    "owner_profile_pic_url": entry.get("ownerProfilePicUrl"),
                    "timestamp": entry.get("timestamp"),
                    "likes_count": entry.get("likesCount"),
                    "scores": emotion_response,
                    "top_label": top_emotion["label"]
                })

                # Guardar en base de datos solo si se puede asociar al post_id correcto
                try:
                    # Solo buscamos comentarios en la DB si tenemos un post_id válido
                    if db_post_id in shortcode_to_db_post_id.values():
                        comment_record = session.query(InstagramComment).filter_by(
                            user_id=instagram_user.id,
                            post_id=db_post_id,
                            comment_text=raw_text
                        ).first()
                        
                        if comment_record:
                            try:
                                sentiment_record = InstagramCommentSentiment(
                                    post_id=db_post_id,
                                    comment_id=comment_record.id,
                                    comment_text=raw_text,
                                    sentiment_negative=next(s["score"] for s in sentiment_response if s["label"] == "NEG"),
                                    sentiment_neutral=next(s["score"] for s in sentiment_response if s["label"] == "NEU"),
                                    sentiment_positive=next(s["score"] for s in sentiment_response if s["label"] == "POS")
                                )
                                session.add(sentiment_record)
                            except Exception as s_err:
                                logger.error(f"Error al guardar el sentimiento para el comentario {raw_text}: {s_err}")

                            try:
                                for emotion_item in emotion_response:
                                    emotion_record = InstagramCommentEmotion(
                                        comment_id=comment_record.id,
                                        emotion_label=emotion_item["label"],
                                        emotion_score=emotion_item["score"]
                                    )
                                    session.add(emotion_record)
                            except Exception as e_err:
                                logger.error(f"Error al guardar la emoción para el comentario {raw_text}: {e_err}")
                except Exception as db_err:
                    logger.error(f"Error consultando el registro de comentario: {db_err}")

            # Guardar resúmenes de sentimiento a nivel de post - solo para posts que existen en la DB
            for pid, counts in post_sentiment_summaries.items():
                if counts["total"] > 0:
                    # Obtener el post_id de la base de datos si existe
                    db_post_id = shortcode_to_db_post_id.get(pid)
                    
                    # Solo guardar en la base de datos si existe el post
                    if db_post_id:
                        try:
                            existing_summary = session.query(InstagramPostSentimentSummary).filter_by(post_id=db_post_id).first()
                            if existing_summary:
                                existing_summary.total_comments = counts["total"]
                                existing_summary.positive_comments = counts["positive"]
                                existing_summary.negative_comments = counts["negative"]
                                existing_summary.neutral_comments = counts["neutral"]
                            else:
                                post_summary = InstagramPostSentimentSummary(
                                    post_id=db_post_id,
                                    total_comments=counts["total"],
                                    positive_comments=counts["positive"],
                                    negative_comments=counts["negative"],
                                    neutral_comments=counts["neutral"]
                                )
                                session.add(post_summary)
                        except Exception as ps_err:
                            logger.error(f"Error al guardar resumen de post {pid}: {ps_err}")

            # Guardar resumen global a nivel de usuario
            if total_comments > 0:
                try:
                    positive_ratio = positive_count / total_comments
                    negative_ratio = negative_count / total_comments
                    neutral_ratio = neutral_count / total_comments

                    existing_overview = session.query(InstagramUserSentimentOverview).filter_by(user_id=instagram_user.id).first()
                    if existing_overview:
                        existing_overview.total_comments = total_comments
                        existing_overview.positive_comments = positive_count
                        existing_overview.negative_comments = negative_count
                        existing_overview.neutral_comments = neutral_count
                        existing_overview.positive_ratio = positive_ratio
                        existing_overview.negative_ratio = negative_ratio
                        existing_overview.neutral_ratio = neutral_ratio
                    else:
                        user_overview = InstagramUserSentimentOverview(
                            user_id=instagram_user.id,
                            total_comments=total_comments,
                            positive_comments=positive_count,
                            negative_comments=negative_count,
                            neutral_comments=neutral_count,
                            positive_ratio=positive_ratio,
                            negative_ratio=negative_ratio,
                            neutral_ratio=neutral_ratio
                        )
                        session.add(user_overview)
                except Exception as ov_err:
                    logger.error(f"Error al guardar el resumen global de usuario: {ov_err}")

            session.commit()
            print(f"✅ Análisis de sentimiento y emociones guardado en la base de datos para el usuario: {self.username}")

            # Guardar resultados en MinIO
            await self.save_results_to_minio(sentiment_results, emotion_results)

        except Exception as e:
            logger.exception(f"Error analizando sentimiento y emociones: {e}")
            print(f"❌ Error analizando sentimiento y emociones: {e}")
            session.rollback()


    async def save_results_to_minio(self, sentiment_results, emotion_results):
        """
        Guarda los resultados del análisis de sentimiento y emociones en MinIO en formato JSON.
        """
        try:
            sentiment_output = {
                "total_comments": len(sentiment_results),
                "results": sentiment_results
            }
            emotion_output = {
                "total_comments": len(emotion_results),
                "results": emotion_results
            }

            # Subir resultados de sentimiento a MinIO
            sentiment_path = f"{self.output_folder}/{self.username}/sentiment_analysis.json"
            await self.minio_service.upload_content(
                object_name=sentiment_path,
                data=json.dumps(sentiment_output, indent=4, ensure_ascii=False),
                content_type="application/json"
            )
            print(f"✅ Resultados de sentimiento guardados en MinIO: {sentiment_path}")

            # Subir resultados de emociones a MinIO
            emotion_path = f"{self.output_folder}/{self.username}/emotion_analysis.json"
            await self.minio_service.upload_content(
                object_name=emotion_path,
                data=json.dumps(emotion_output, indent=4, ensure_ascii=False),
                content_type="application/json"
            )
            print(f"✅ Resultados de emociones guardados en MinIO: {emotion_path}")

        except Exception as e:
            logger.exception(f"Error guardando resultados en MinIO: {e}")
            print(f"❌ Error guardando resultados en MinIO: {e}")