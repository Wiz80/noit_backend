import os
import json
import tiktoken
from collections import defaultdict
from openai import OpenAI
from app.services.storage.minio_service import MinioService
from apify_client import ApifyClient
from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramPostInfo, InstagramComment, InstagramCommentCategory
from app.db.session import SessionLocal
import aisuite as ai
from dotenv import load_dotenv
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer

load_dotenv()

# Initialize database session
session = SessionLocal()

class InstagramCommentCategorizer(BaseInstagramAnalyzer):
    def __init__(self, username, output_folder, provider, model):
        super().__init__(username, output_folder)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.provider = provider
        self.model = model
        self._init_clients()
            
    def _init_clients(self):
        """Initialize LLM clients"""
        if self.provider in ["openai", "claude"]:
            self.client = ai.Client()
        elif self.provider == "deepseek":
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
        else:
            raise ValueError("Invalid validator model specified")


    def count_tokens(self, text):
        """Counts the number of tokens in a given text using OpenAI's tokenizer."""
        return len(self.tokenizer.encode(text))

    def clean_llm_response(self, response_text):
        """Cleans LLM response, ensuring valid JSON output."""
        try:
            # Eliminar delimitadores de código markdown y espacios en blanco
            response_text = response_text.strip().replace("```json", "").replace("```", "").strip()
            parsed_response = json.loads(response_text)
            
            print(f"🔍 DEBUG: Parsed LLM Response - Type: {type(parsed_response)}")
            
            # Caso 1: Respuesta ya es un diccionario de categorías
            if isinstance(parsed_response, dict) and all(isinstance(v, list) for v in parsed_response.values()):
                print(f"🔍 DEBUG: Response is already a categories dictionary")
                return parsed_response
            
            # Caso 2: Respuesta tiene una clave "temas" o "categories"
            for key in ["temas", "categories", "categorias"]:
                if key in parsed_response:
                    categories = parsed_response.get(key)
                    print(f"🔍 DEBUG: Found '{key}' key in response")
                    
                    # Si categories es un diccionario de listas, retornarlo directamente
                    if isinstance(categories, dict) and all(isinstance(v, list) for v in categories.values()):
                        return categories
                    
                    # Si categories es una lista, intentamos agrupar por temas
                    if isinstance(categories, list):
                        print(f"🔍 DEBUG: Converting list of {len(categories)} items to categories")
                        categorized = defaultdict(list)
                        
                        # Agrupación simplificada: todos los comentarios en "General Category"
                        categorized["General Category"] = categories
                        return dict(categorized)
            
            # Caso 3: La respuesta es una lista de comentarios
            if isinstance(parsed_response, list):
                print(f"🔍 DEBUG: Response is a list of {len(parsed_response)} items")
                return {"General Category": parsed_response}
            
            # Caso 4: No entendemos la estructura de la respuesta
            print(f"⚠️ Unknown response structure. Creating empty categories.")
            return {}
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON decoding error: {e}\nRaw response: {response_text}")
            return {}

    def determine_batch_size(self, comments, max_tokens_per_batch=4000):
        """
        Determina dinámicamente el tamaño óptimo de los batches basado en el límite de tokens.
        
        Se asume que 'comments' es una lista de diccionarios de comentarios (nuevo formato),
        donde el texto de cada comentario se encuentra en la clave "contenido" y el owner en "ownerUsername".
        Cada comentario se formatea de la siguiente manera:
        "Owner: {ownerUsername} | Content: {contenido}"
        
        Se utiliza self.count_tokens para calcular el número de tokens de ese string.
        
        :param comments: Lista de diccionarios de comentarios (nuevo formato).
        :param max_tokens_per_batch: Límite máximo de tokens por batch.
        :return: Lista de batches, donde cada batch es una lista de strings formateados.
        """
        batches = []
        current_batch = []
        current_token_count = 0

        for comment in comments:
            # Asegurémonos de que comment es un diccionario
            if isinstance(comment, dict):
                # Extraer owner y contenido del diccionario
                owner = comment.get('ownerUsername', '')
                content = comment.get('contenido', '')
                formatted_comment = f"Owner: {owner} | Content: {content}"
                
                # Preservar la información original para el procesamiento posterior
                formatted_dict = {
                    "formatted_text": formatted_comment,
                    "original_data": comment
                }
            else:
                # Si no es un diccionario, convertirlo a string
                formatted_comment = f"Content: {str(comment)}"
                formatted_dict = {
                    "formatted_text": formatted_comment,
                    "original_data": {"contenido": str(comment)}
                }
                
            comment_tokens = self.count_tokens(formatted_comment)
            
            if current_token_count + comment_tokens > max_tokens_per_batch:
                batches.append(current_batch)
                current_batch = []
                current_token_count = 0

            current_batch.append(formatted_dict)
            current_token_count += comment_tokens

        if current_batch:
            batches.append(current_batch)

        return batches


    async def generate_dynamic_categories_in_batches(self, comments):
        """
        Procesa los comentarios (nuevo formato) en batches y genera categorías temáticas usando LLM.
        
        Cada comentario se formatea a una línea con el siguiente formato:
        "Owner: [ownerUsername] | Content: [contenido]"
        
        Además, si ya existen categorías acumuladas de batches anteriores, se las envía como contexto para que la LLM
        asigne los nuevos comentarios a categorías existentes cuando corresponda. 
        
        :param comments: Lista de diccionarios de comentarios.
        :return: Diccionario final de categorías con la lista de comentarios asociados.
        """
        # Si no hay comentarios, retornar categoría vacía
        if not comments or len(comments) == 0:
            print("⚠️ No hay comentarios para analizar")
            return {"General Category": []}
            
        # Mostrar los comentarios que vamos a procesar para debug
        print("📝 Comentarios a procesar:")
        for i, comment in enumerate(comments[:3]):  # Mostrar los 3 primeros para debug
            if isinstance(comment, dict):
                print(f"  {i+1}. Owner: {comment.get('ownerUsername', 'N/A')} | Content: {comment.get('contenido', 'N/A')}")
            else:
                print(f"  {i+1}. {comment}")
        if len(comments) > 3:
            print(f"  ... y {len(comments) - 3} comentarios más")
        
        from collections import defaultdict
        
        # Diccionario para almacenar las categorías acumuladas
        cumulative_categories = {}
        
        # Crear batches para procesamiento
        batches = self.determine_batch_size(comments)
        print(f"📌 Total de comentarios: {len(comments)}")
        print(f"📌 Total de batches: {len(batches)}")

        for batch_num, batch in enumerate(batches, start=1):
            print(f"🔄 Procesando batch {batch_num}/{len(batches)} con {len(batch)} comentarios...")
            
            # Verificar que el batch no esté vacío
            if not batch:
                print("⚠️ Batch vacío, saltando...")
                continue
                
            # Extraer los textos formateados para el prompt
            formatted_texts = [item["formatted_text"] for item in batch]
            
            # Mostrar algunos ejemplos del batch actual para debug
            print("📝 Ejemplos de comentarios en este batch:")
            for i, formatted_text in enumerate(formatted_texts[:3]):
                print(f"  {i+1}. {formatted_text}")
            if len(formatted_texts) > 3:
                print(f"  ... y {len(formatted_texts) - 3} comentarios más")
            
            # Construir el prompt:
            prompt_messages = []
            prompt_messages.append({
                "role": "system",
                "content": """Eres un experto en análisis de comentarios de Instagram. Tu tarea es:
                
1. Analizar cuidadosamente cada comentario de Instagram proporcionado
2. Identificar temas recurrentes y agrupar comentarios por categorías específicas
3. Crear categorías temáticas descriptivas en español (mínimo 3-5 categorías)
4. Devolver un JSON con las categorías identificadas y sus comentarios

Es muy importante ser específico en las categorías. Ejemplos de buenas categorías:
- "reacciones positivas" (para emojis de fuego, comentarios de admiración, etc.)
- "preguntas sobre productos" (consultas sobre formulación, usos, etc.)
- "solicitudes de distribución" (comentarios sobre disponibilidad en ciertos países)
- "menciones a resultados" (comentarios sobre efectos del producto)

El JSON debe tener formato de diccionario con claves para las categorías y valores como listas de textos de comentarios."""
            })
            
            # Unir los textos formateados en un string
            comments_text = "\n".join(formatted_texts)
            
            user_message = (
                "A continuación hay una lista de comentarios de Instagram que necesito categorizar por temas específicos:\n\n"
                f"{comments_text}\n\n"
                "Analiza estos comentarios y agrúpalos en categorías temáticas específicas. Devuelve un JSON donde cada clave "
                "es una categoría descriptiva en español, y el valor es una lista con los textos de los comentarios que pertenecen a esa categoría.\n\n"
                "IMPORTANTE:\n"
                "1. Crea MÚLTIPLES categorías específicas (mínimo 3-5)\n"
                "2. No uses categorías genéricas como 'General' a menos que sea absolutamente necesario\n"
                "3. Incluye el comentario completo en la lista de cada categoría\n\n"
                "Formato de respuesta esperado (solo JSON):\n"
                "{\n"
                '  "reacciones positivas": ["🔥🔥🔥", "The skin tho flawless 🔥🔥"],\n'
                '  "preguntas sobre productos": ["What the science based on....old formulation or new?"],\n'
                '  "disponibilidad": ["I hope this product will come back in Europe\'s Rossmann"]\n'
                "}"
            )
            prompt_messages.append({"role": "user", "content": user_message})
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=prompt_messages,
                    temperature=0.7,  # Aumentar para fomentar categorías más creativas
                    max_tokens=2000
                )
                if not response or not response.choices:
                    print("⚠️ Respuesta vacía de LLM.")
                    continue

                response_content = response.choices[0].message.content.strip()
                if not response_content:
                    print("⚠️ LLM retornó una respuesta vacía.")
                    continue

                print(f"📝 Respuesta del LLM (primeros 100 caracteres): {response_content[:100]}...")
                
                # Para debug, mostrar la respuesta completa
                if len(response_content) < 500:
                    print(f"Respuesta completa:\n{response_content}")
                
                # Intentar forzar el formato JSON si no lo tiene
                if not response_content.strip().startswith("{"):
                    # Buscar donde comienza el JSON (después de una explicación)
                    json_start = response_content.find("{")
                    if json_start >= 0:
                        response_content = response_content[json_start:]
                        print(f"⚠️ Detectado JSON parcial, extrayendo desde posición {json_start}")
                    else:
                        print("⚠️ No se detectó formato JSON en la respuesta")
                
                # Limpiar y procesar la respuesta JSON
                batch_categories = self.clean_llm_response(response_content)
                
                if not batch_categories:
                    print("⚠️ No se pudieron extraer categorías de la respuesta")
                    # Crear categorías manualmente basadas en el contenido
                    manual_categories = self.create_manual_categories(batch)
                    if manual_categories:
                        batch_categories = manual_categories
                        print(f"✅ Se crearon {len(manual_categories)} categorías manualmente")
                
                # Mostrar las categorías identificadas
                print(f"📊 Categorías identificadas: {list(batch_categories.keys())}")
                
                # Mapear los comentarios originales para cada categoría
                processed_categories = {}
                for category, comment_snippets in batch_categories.items():
                    processed_categories[category] = []
                    
                    for snippet in comment_snippets:
                        # Buscar el comentario original que contiene este snippet
                        for item in batch:
                            original_comment = item["original_data"]
                            comment_content = original_comment.get("contenido", "")
                            
                            # Si el snippet está en el contenido del comentario original o viceversa
                            if (isinstance(snippet, str) and 
                                (snippet in comment_content or comment_content in snippet)):
                                processed_categories[category].append(original_comment)
                                break
                        else:
                            # Si no se encuentra una coincidencia exacta, usar el snippet como texto
                            if isinstance(snippet, str):
                                processed_categories[category].append({"contenido": snippet})
                            elif isinstance(snippet, dict):
                                processed_categories[category].append(snippet)
                            else:
                                processed_categories[category].append({"contenido": str(snippet)})
                
                # Fusionar las categorías del batch con las acumuladas
                for category, comments_list in processed_categories.items():
                    if category in cumulative_categories:
                        # Si la categoría ya existe, extendemos la lista existente con los nuevos comentarios
                        cumulative_categories[category].extend(comments_list)
                    else:
                        # Si es una nueva categoría, simplemente asignamos la lista de comentarios
                        cumulative_categories[category] = comments_list

            except Exception as e:
                print(f"⚠️ Error procesando batch {batch_num}: {str(e)}")
                import traceback
                traceback.print_exc()

        # Verificar que tenemos al menos una categoría
        if not cumulative_categories:
            print("⚠️ No se pudieron generar categorías. Creando categoría por defecto.")
            # Agrupar todos los comentarios en una categoría general
            cumulative_categories = {"General Category": comments}
        else:
            print(f"✅ Se generaron {len(cumulative_categories)} categorías: {list(cumulative_categories.keys())}")
        
        return cumulative_categories
        
    def create_manual_categories(self, batch):
        """Crea categorías manualmente basadas en palabras clave y emojis"""
        categories = {
            "reacciones positivas": [],
            "preguntas sobre productos": [],
            "mensajes directos": []
        }
        
        for item in batch:
            comment = item["original_data"]
            content = comment.get("contenido", "").lower()
            
            # Clasificar basado en contenido
            if "🔥" in content or "amazing" in content or "flawless" in content or "yasss" in content:
                categories["reacciones positivas"].append(comment)
            elif "?" in content or "what" in content or "how" in content or "when" in content or "formulation" in content:
                categories["preguntas sobre productos"].append(comment)
            elif "dm" in content or "message" in content:
                categories["mensajes directos"].append(comment)
            else:
                # Si no encaja en ninguna categoría existente, añadirla a la que tenga menos comentarios
                min_category = min(categories.keys(), key=lambda k: len(categories[k]))
                categories[min_category].append(comment)
        
        # Eliminar categorías vacías
        return {k: v for k, v in categories.items() if v}

    async def save_results(self, categories):
        """Saves categorized comments in MinIO and the database."""
        try:
            category_counts = {category: len(comments) for category, comments in categories.items()}
            results = {
                "category_counts": category_counts,
                "categorized_comments": categories
            }

            # Upload results to MinIO
            output_path = f"{self.output_folder}/{self.username}/dynamic_categorized_comments.json"
            await self.minio_service.upload_content(
                object_name=output_path,
                data=json.dumps(results, indent=4, ensure_ascii=False),
                content_type="application/json"
            )

            print(f"✅ Categorized comments saved in MinIO: {output_path}")
            
            # Save results to database
            # Get the Instagram user from the database
            instagram_user = session.query(InstagramUserInfo).filter_by(username=self.username).first()
            if not instagram_user:
                print(f"⚠️ Instagram user {self.username} not found in database")
                return len(categories)
                
            # Get the Instagram post info for this user
            posts = session.query(InstagramPostInfo).filter_by(instagram_user_id=instagram_user.id).all()
            if not posts:
                print(f"⚠️ No posts found for user {self.username}")
                return len(categories)
                
            post_dict = {post.id: post for post in posts}
            
            # Dictionary to store categories by their IDs for later use with comments
            category_id_map = {}
            
            # Save categories to database
            for category_name, comment_list in categories.items():
                # Create or update category
                category = session.query(InstagramCommentCategory).filter_by(
                    user_id=instagram_user.id,
                    category_type=category_name
                ).first()
                
                if not category:
                    category = InstagramCommentCategory(
                        user_id=instagram_user.id,
                        category_type=category_name,
                        category_count=len(comment_list)
                    )
                    session.add(category)
                    session.flush()  # Generate ID without committing
                else:
                    category.category_count = len(comment_list)
                
                # Store category ID for later use
                category_id_map[category_name] = category.id
                
                # Save comments
                for comment in comment_list:
                    # Para simplicity, assign to the first post if we can't match the comment to a specific post
                    # In a real implementation, you'd want to match comments to their specific posts
                    post_id = posts[0].id if posts else None
                    
                    if post_id:
                        # Manejar diferentes formatos de comentario
                        if isinstance(comment, dict):
                            # Extraer el texto del comentario del diccionario
                            comment_text = comment.get('contenido', comment.get('content', ''))
                            owner_username = comment.get('ownerUsername', comment.get('owner', 'unknown_user'))
                        elif isinstance(comment, str):
                            # Si el comentario es un string, usarlo directamente
                            comment_text = comment
                            owner_username = 'unknown_user'
                        else:
                            # Si no es dict ni string, convertirlo a string
                            comment_text = str(comment)
                            owner_username = 'unknown_user'
                        
                        # Check if comment already exists
                        existing_comment = session.query(InstagramComment).filter_by(
                            user_id=instagram_user.id,
                            post_id=post_id,
                            comment_text=comment_text
                        ).first()
                        
                        if existing_comment:
                            # Si el comentario ya existe, actualizamos su categoría
                            existing_comment.category_id = category.id
                            session.flush()
                        else:
                            # Si no existe, creamos un nuevo comentario
                            comment_obj = InstagramComment(
                                user_id=instagram_user.id,
                                post_id=post_id,
                                comment_text=comment_text,
                                username_commentator=owner_username,
                                category_id=category.id  # Aseguramos que category_id esté asignado
                            )
                            session.add(comment_obj)
            
            # Commit the changes
            session.commit()
            
            # Verificar que los comentarios tienen categoría asignada
            comments_without_category = session.query(InstagramComment).filter_by(
                user_id=instagram_user.id,
                category_id=None
            ).count()
            
            if comments_without_category > 0:
                print(f"⚠️ After saving, there are still {comments_without_category} comments without category")
            
            print(f"✅ Categorized comments saved in database for user: {self.username}")
            
            return len(categories)
        except Exception as e:
            print(f"❌ Error saving results: {e}")
            session.rollback()
            return 0

    async def run_analysis(self):
        """Main function to run the entire categorization process."""
        try:
            comments = await self.load_comments()
            if not comments:
                print("❌ No comments found.")
                return

            categorized_comments = await self.generate_dynamic_categories_in_batches(comments)
            total_categories = await self.save_results(categorized_comments)

            print(f"📊 Total categories generated: {total_categories}")
            return total_categories
        except Exception as e:
            print(f"❌ Error during analysis: {e}")

    async def load_comments(self):
        """Loads Instagram comments from MinIO."""
        try:
            # Correct path with username included
            object_path = f"{self.output_folder}/{self.username}/processed_comments_data.json"
            comments_json = self.minio_service.get_object_data(object_path)
            
            if not comments_json:
                print(f"❌ No comment data found at {object_path}")
                return []
                
            # Parse the JSON into a list (not dictionary)
            posts_list = json.loads(comments_json)
            
            # Debug log para ver la estructura exacta
            print(f"🔍 Estructura de posts_list: {type(posts_list)}")
            if isinstance(posts_list, list) and len(posts_list) > 0:
                print(f"🔍 Ejemplo del primer post:")
                first_post = posts_list[0]  # Acceder al primer elemento de la lista
                
                # Ver las claves del primer post
                if isinstance(first_post, dict):
                    print(f"🔍 Claves del post: {list(first_post.keys())}")
                    
                    # Ver un comentario de ejemplo si existe
                    if "comments" in first_post and len(first_post["comments"]) > 0:
                        sample_comment = first_post["comments"][0]
                        print(f"🔍 Claves del comentario: {list(sample_comment.keys())}")
                        print(f"🔍 Muestra de comentario: {sample_comment}")
            
            # Create a list of formatted comments
            comments_list = []
            
            # Flatten the comments structure to a list
            for post in posts_list:
                if not isinstance(post, dict):
                    continue
                    
                post_id = post.get("postId", "")
                for comment in post.get("comments", []):
                    # Extraer los campos correctos basados en la estructura observada
                    comment_id = comment.get("id", "")
                    content = comment.get("text", "")
                    owner = comment.get("ownerUsername", "")
                    
                    # Solo incluir comentarios con contenido
                    if content:
                        formatted_comment = {
                            "post_id": post_id,
                            "id_comentario": comment_id,
                            "ownerUsername": owner,
                            "contenido": content
                        }
                        comments_list.append(formatted_comment)
            
            print(f"📊 Loaded {len(comments_list)} comments from {len(posts_list)} posts")
            
            # Mostrar ejemplos
            if comments_list:
                print("📝 Ejemplos de comentarios cargados:")
                for i, comment in enumerate(comments_list[:3]):
                    print(f"  {i+1}. Owner: {comment.get('ownerUsername')} | Content: {comment.get('contenido')}")
            
            return comments_list
            
        except Exception as e:
            print(f"❌ Error loading comments: {e}")
            import traceback
            traceback.print_exc()
            return []
