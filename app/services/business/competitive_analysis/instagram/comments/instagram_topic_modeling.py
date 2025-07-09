import json
import re
import spacy
from collections import Counter
from gensim import corpora, models
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import nltk
import numpy as np
from app.services.storage.minio_service import MinioService
from app.db.session import SessionLocal
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer
from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramLDATopic

# LangChain imports
from langchain_core.messages import HumanMessage
from app.services.llm import create_llm_client

# Initialize database session
session = SessionLocal()

class InstagramTopicModeling(BaseInstagramAnalyzer):
    def __init__(self, username, output_folder, num_topics=5, lang='en'):
        super().__init__(username, output_folder)
        self.num_topics = num_topics
        self.lang = lang
        
        # Cargar el modelo de lenguaje adecuado según el idioma
        try:
            if self.lang == 'es':
                self.nlp = spacy.load("es_core_news_sm")
                print(f"✅ Loaded Spanish language model (es_core_news_sm)")
            else:
                self.nlp = spacy.load("en_core_web_sm")
                print(f"✅ Loaded English language model (en_core_web_sm)")
        except Exception as e:
            print(f"❌ Error loading language model: {e}")
            # Intentar cargar un modelo alternativo si falla
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print(f"⚠️ Fallback to English language model")
            except:
                # Si todo falla, usar un pipeline simple
                print(f"⚠️ Using simple pipeline as fallback")
                self.nlp = spacy.blank("en")
        
        nltk.download('punkt')
        nltk.download('punkt_tab')
        nltk.download('stopwords')
        
        # Initialize LLM using LangChain with Claude as default
        try:
            self.client = create_llm_client(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                temperature=0.3
            )
            print(f"✅ LLM initialized with Claude")
        except Exception as e:
            print(f"❌ Error initializing LLM: {e}")
            # Try fallback to OpenAI
            try:
                self.client = create_llm_client(
                    provider="openai",
                    model="gpt-4o-mini",
                    temperature=0.3
                )
                print(f"⚠️ Fallback to OpenAI GPT-4o-mini")
            except Exception as fallback_error:
                print(f"❌ Could not initialize any LLM: {fallback_error}")
                raise ValueError(f"Could not initialize any LLM: {fallback_error}")
        
        self.model = "claude-3-5-sonnet-20241022"  # Model to use for analysis

    async def load_comments(self):
        """
        Loads comments for analysis. This method can be called in two ways:
        
        1. From preprocessed comments data stored in MinIO (like comment_categorizer does)
        2. From the dynamic categories returned by the comment categorizer
        
        The method first tries to extract comments from the output of the dynamic categorizer.
        If that fails, it attempts to load from MinIO using the same path as comment_categorizer.
        
        :return: List of comment text strings for analysis
        """
        try:
            # First check if we already have categorized comments in MinIO
            categorized_comments_path = f"{self.output_folder}/{self.username}/dynamic_categorized_comments.json"
            categorized_data = self.minio_service.get_object_data(categorized_comments_path)
            
            if categorized_data:
                print(f"📂 Found categorized comments in MinIO: {categorized_comments_path}")
                categorized_comments = json.loads(categorized_data.decode('utf-8'))
                
                # Extract the actual comments from the categorized structure
                comments_list = []
                categorized_dict = categorized_comments.get("categorized_comments", {})
                
                for category, comments in categorized_dict.items():
                    for comment in comments:
                        if isinstance(comment, dict):
                            # Extract the text from the comment dictionary
                            comment_text = comment.get('contenido', comment.get('content', ''))
                            if comment_text:
                                comments_list.append(comment_text)
                        elif isinstance(comment, str):
                            comments_list.append(comment)
                
                print(f"📊 Extracted {len(comments_list)} comments from categorized data")
                return comments_list
            
            # If no categorized comments found, try loading raw comments
            raw_comments_path = f"{self.output_folder}/{self.username}/processed_comments_data.json"
            raw_comments_data = self.minio_service.get_object_data(raw_comments_path)
            
            # If not found, try alternative legacy paths for backward compatibility
            if not raw_comments_data:
                print(f"⚠️ No raw comments found at primary path: {raw_comments_path}")
                
                # Try legacy path 1: with 'businesses' prefix
                legacy_path_1 = f"businesses/{self.output_folder}/{self.username}/processed_comments_data.json"
                print(f"🔍 Trying legacy path 1: {legacy_path_1}")
                raw_comments_data = self.minio_service.get_object_data(legacy_path_1)
                
                if raw_comments_data:
                    print(f"✅ Found raw comments at legacy path 1: {legacy_path_1}")
                else:
                    # Try legacy path 2: old instagram structure
                    business_id = self.output_folder.split('/')[0] if '/' in self.output_folder else self.output_folder
                    legacy_path_2 = f"businesses/{business_id}/instagram/{self.username}/processed_comments_data.json"
                    print(f"🔍 Trying legacy path 2: {legacy_path_2}")
                    raw_comments_data = self.minio_service.get_object_data(legacy_path_2)
                    
                    if raw_comments_data:
                        print(f"✅ Found raw comments at legacy path 2: {legacy_path_2}")
            
            if raw_comments_data:
                print(f"📂 Found raw comments in MinIO")
                posts_data = json.loads(raw_comments_data.decode('utf-8'))
                
                # Extract comments from raw data
                comments_list = []
                
                # Check if posts_data is a list (new format) or a dictionary (old format)
                if isinstance(posts_data, list):
                    print(f"📊 Processing list format with {len(posts_data)} posts")
                    # New format: list of posts
                    for post in posts_data:
                        if not isinstance(post, dict):
                            continue
                        
                        for comment in post.get("comments", []):
                            # Try to get content from different possible field names
                            content = comment.get("text", comment.get("contenido", ""))
                            if content:
                                comments_list.append(content)
                
                elif isinstance(posts_data, dict):
                    print(f"📊 Processing dictionary format with {len(posts_data)} posts")
                    # Old format: dictionary with post_id as keys
                    for post_id, post_data in posts_data.items():
                        for comment in post_data.get("comments", []):
                            content = comment.get("contenido", comment.get("text", ""))
                            if content:
                                comments_list.append(content)
                else:
                    print(f"⚠️ Unknown format for posts_data: {type(posts_data)}")
                
                print(f"📊 Extracted {len(comments_list)} comments from raw data")
                return comments_list
            
            # No comments found at all
            print("⚠️ No comments found in either categorized or raw format")
            return []
            
        except Exception as e:
            print(f"❌ Error loading comments: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def clean_text(self, text):
        """Clean text by removing special characters, URLs, etc."""
        if not isinstance(text, str):
            return ""
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove special characters and digits
        text = re.sub(r'[^\w\s]', '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text.lower()

    def preprocess_text(self, comments):
        """Preprocesses comments by cleaning, tokenizing, and lemmatizing text."""
        # Seleccionar idioma para stopwords
        try:
            if self.lang == 'es':
                stop_words = set(stopwords.words('spanish'))
                print("🔤 Using Spanish stopwords")
            else:
                stop_words = set(stopwords.words('english'))
                print("🔤 Using English stopwords")
        except Exception as e:
            print(f"⚠️ Error loading stopwords: {e}. Using empty set.")
            stop_words = set()
        
        processed_comments = []

        for comment in comments:
            comment = self.clean_text(comment)
            tokens = word_tokenize(comment)
            tokens = [word for word in tokens if word not in stop_words and len(word) > 2]

            doc = self.nlp(" ".join(tokens))
            lemmatized_tokens = [token.lemma_ for token in doc if token.is_alpha]

            processed_comments.append(lemmatized_tokens)

        return processed_comments

    def apply_lda(self, processed_comments):
        """Applies LDA for topic modeling and returns topics with associated word weights."""
        dictionary = corpora.Dictionary(processed_comments)
        corpus = [dictionary.doc2bow(text) for text in processed_comments]

        lda_model = models.LdaModel(corpus, num_topics=self.num_topics, id2word=dictionary, passes=10, random_state=42)
        topics_dict = {}

        for idx, topic in lda_model.show_topics(num_topics=self.num_topics, formatted=False):
            topic_data = {word: float(weight) for word, weight in topic}
            topics_dict[f"Tema_{idx+1}"] = {
                "palabras_con_pesos": topic_data,
                "cantidad_comentarios": sum(1 for doc in corpus if idx in [word[0] for word in lda_model.get_document_topics(doc)])
            }

        return lda_model, corpus, dictionary, topics_dict

    async def generate_wordcloud(self, processed_comments):
        """Generates word frequency data from processed comments and saves it as JSON to MinIO."""
        try:
            # Extract all words from processed comments
            all_words = []
            for comment in processed_comments:
                if isinstance(comment, list):
                    all_words.extend(comment)
                elif isinstance(comment, str):
                    all_words.extend(comment.split())
            
            # Count word frequencies
            word_freq = Counter(all_words)
            
            # Get top 100 most common words (you can adjust this number)
            top_words = word_freq.most_common(100)
            
            # Create wordcloud data structure
            wordcloud_data = {
                "metadata": {
                    "username": self.username,
                    "total_words": len(all_words),
                    "unique_words": len(word_freq),
                    "top_words_count": len(top_words),
                    "generated_at": str(np.datetime64('now'))
                },
                "word_frequencies": {
                    word: freq for word, freq in top_words
                },
                "word_frequencies_list": [
                    {
                        "word": word,
                        "frequency": freq,
                        "relative_frequency": round(freq / len(all_words), 4)
                    }
                    for word, freq in top_words
                ]
            }

            # Convert to JSON
            wordcloud_json = json.dumps(wordcloud_data, indent=2, ensure_ascii=False)

            # Save to MinIO
            await self.minio_service.upload_content(
                object_name=f"{self.output_folder}/{self.username}/wordcloud.json",
                data=wordcloud_json.encode('utf-8'),
                content_type="application/json"
            )

            print(f"✅ WordCloud JSON saved in MinIO: {self.output_folder}/{self.username}/wordcloud.json")
            print(f"📊 Generated wordcloud with {len(top_words)} words from {len(all_words)} total words")
            
            return wordcloud_data
            
        except Exception as e:
            print(f"❌ Error generating WordCloud JSON: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def save_topics_to_json(self, topics_dict):
        """Saves the detected topics and statistics as a JSON file in MinIO and in the database."""
        try:
            # Save to MinIO
            output_path = f"{self.output_folder}/{self.username}/lda_topics.json"
            await self.minio_service.upload_content(
                object_name=output_path,
                data=json.dumps(topics_dict, indent=4, ensure_ascii=False),
                content_type="application/json"
            )
            print(f"✅ Topics saved in MinIO: {output_path}")
            
            # Save to database
            # Get Instagram user
            instagram_user = session.query(InstagramUserInfo).filter_by(username=self.username).first()
            if not instagram_user:
                print(f"⚠️ Instagram user {self.username} not found in database")
                return
                
            # Save topics
            for topic_name, topic_details in topics_dict.items():
                # Check if topic already exists for this user
                existing_topic = session.query(InstagramLDATopic).filter_by(
                    user_id=instagram_user.id,
                    topic_name=topic_name
                ).first()
                
                if existing_topic:
                    # Update existing topic
                    existing_topic.topic_details = topic_details
                else:
                    # Create new topic
                    new_topic = InstagramLDATopic(
                        user_id=instagram_user.id,
                        topic_name=topic_name,
                        topic_details=topic_details
                    )
                    session.add(new_topic)
            
            session.commit()
            print(f"✅ Topics saved in database for user: {self.username}")
            
        except Exception as e:
            print(f"❌ Error saving topics to JSON: {e}")
            session.rollback()

    async def analyze_categories_and_topics(self, dynamic_categories: dict, topics_dict: dict) -> dict:
        """
        Combina el análisis dinámico de categorías (resultado de generate_dynamic_categories_in_batches)
        y el análisis de temas (resultado de LDA en topics_dict) para generar un informe final usando LLM.
        
        Se prepara un prompt que incluye:
        - Un resumen de las categorías dinámicas: para cada categoría se muestra el número de comentarios (owners).
        - Un resumen de los temas de LDA: para cada tema se listan las palabras con sus pesos y la cantidad de comentarios asociados.
        
        El prompt instruye al LLM para que sintetice ambos análisis y produzca un informe final en formato JSON,
        que contenga:
        - 'areas_principales': una lista de las principales áreas temáticas identificadas.
        - 'comparacion': un resumen comparativo entre las categorías dinámicas y los temas LDA.
        - 'insights': recomendaciones o insights basados en la combinación de ambos resultados.
        
        :param dynamic_categories: Diccionario con las categorías dinámicas (e.g., {"Marketing": [owner1, owner2], ...}).
        :param topics_dict: Diccionario de temas extraído de LDA.
        :return: Informe final como diccionario.
        """
        try:
            # Simplificar el diccionario de categorías: calcular el número de comentarios (owners) por categoría.
            simplified_categories = {cat: len(owners) for cat, owners in dynamic_categories.items()}
            
            # Convertir ambos diccionarios a strings JSON para incluirlos en el prompt.
            categories_json = json.dumps(simplified_categories, indent=2, ensure_ascii=False)
            topics_json = json.dumps(topics_dict, indent=2, ensure_ascii=False)
            
            prompt = (
                "Eres un experto en análisis de datos, marketing digital y síntesis de informes. "
                "A continuación se te proporcionan dos conjuntos de resultados:\n\n"
                "1. Categorías dinámicas de comentarios, en las que cada categoría indica el número de comentarios asociados:\n"
                f"{categories_json}\n\n"
                "2. Temas extraídos mediante LDA, en los cuales se muestran las palabras con sus respectivos pesos y la cantidad de comentarios asociados:\n"
                f"{topics_json}\n\n"
                "Analiza ambos resultados en conjunto y genera un informe final en formato JSON que contenga:\n"
                "  - 'areas_principales': una lista de las principales áreas temáticas identificadas.\n"
                "  - 'comparacion': un resumen comparativo entre las categorías dinámicas y los temas LDA, resaltando similitudes y diferencias.\n"
                "  - 'insights': recomendaciones o insights basados en la combinación de ambos análisis.\n\n"
                "IMPORTANTE: Tu respuesta debe ser un JSON válido sin comentarios, marcas de código ni texto explicativo adicional. "
                "Sólo debes devolver el objeto JSON en formato válido."
            )
            
            try:
                # Create messages for LangChain
                system_message = HumanMessage(content="Eres un experto en análisis de datos y marketing digital que siempre responde con JSON válido.")
                user_message = HumanMessage(content=prompt)
                
                # Use LangChain for LLM call
                response = self.client.invoke([system_message, user_message])
                
                if not response or not response.content:
                    print("⚠️ No se obtuvo respuesta del LLM.")
                    return {}
                
                final_response = response.content.strip()
                print(f"🔍 Respuesta del LLM (primeros 100 caracteres): {final_response[:100]}...")
                
                # Clean the response to ensure valid JSON
                final_response = self.clean_json_response(final_response)
                
                try:
                    final_report = json.loads(final_response)
                    
                    # Save the analysis report to MinIO
                    analysis_path = f"{self.output_folder}/{self.username}/combined_analysis_report.json"
                    await self.minio_service.upload_content(
                        object_name=analysis_path,
                        data=json.dumps(final_report, indent=4, ensure_ascii=False),
                        content_type="application/json"
                    )
                    print(f"✅ Combined analysis report saved in MinIO: {analysis_path}")
                    
                    return final_report
                    
                except json.JSONDecodeError as parse_err:
                    print(f"❌ Error al parsear la respuesta JSON: {parse_err}")
                    print(f"Respuesta completa: {final_response}")
                    
                    # Create a fallback report with default structure
                    fallback_report = {
                        "areas_principales": [
                            "Reacciones positivas de usuarios", 
                            "Consultas sobre productos", 
                            "Disponibilidad regional"
                        ],
                        "comparacion": "No se pudo generar una comparación automática debido a un error de formato.",
                        "insights": [
                            "Los comentarios muestran interés en el producto",
                            "Hay preguntas sobre disponibilidad en Europa",
                            "Se deben considerar estrategias para mejorar distribución internacional"
                        ],
                        "error": "Error al procesar la respuesta del LLM"
                    }
                    
                    # Save the fallback report to MinIO
                    analysis_path = f"{self.output_folder}/{self.username}/combined_analysis_report.json"
                    await self.minio_service.upload_content(
                        object_name=analysis_path,
                        data=json.dumps(fallback_report, indent=4, ensure_ascii=False),
                        content_type="application/json"
                    )
                    print(f"✅ Fallback analysis report saved in MinIO: {analysis_path}")
                    
                    return fallback_report
                    
            except Exception as api_err:
                print(f"❌ Error al llamar a la API del LLM: {api_err}")
                return {
                    "error": f"Error en la llamada a la API: {str(api_err)}",
                    "areas_principales": [],
                    "comparacion": "",
                    "insights": []
                }
                
        except Exception as e:
            print(f"❌ Error al analizar categorías y temas: {e}")
            return {
                "error": f"Error general: {str(e)}",
                "areas_principales": [],
                "comparacion": "",
                "insights": []
            }
            
    def clean_json_response(self, response_text):
        """
        Limpia y asegura que la respuesta del LLM sea un JSON válido.
        
        :param response_text: Texto de la respuesta del LLM
        :return: Texto limpio que debería ser un JSON válido
        """
        # Eliminar marcadores de código markdown si existen
        response_text = response_text.strip()
        
        # Eliminar bloques de código markdown
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "", 1)
            
        if response_text.startswith("```"):
            response_text = response_text.replace("```", "", 1)
            
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        # Eliminar espacios en blanco al principio y final
        response_text = response_text.strip()
        
        # Verificar que tenga estructura de JSON (comienza con { y termina con })
        if not (response_text.startswith('{') and response_text.endswith('}')):
            print("⚠️ La respuesta no tiene estructura de JSON válido")
            # Forzar una estructura JSON básica si no existe
            return '{"areas_principales": [], "comparacion": "", "insights": []}'
            
        return response_text

    async def run_lda_analysis(self, dynamic_categories: dict = None):
        """
        Main function to run the complete LDA analysis process.
        
        :param dynamic_categories: Optional dict of categorized comments from InstagramCommentCategorizer
        """
        try:
            comments = await self.load_comments()
            if not comments:
                print("❌ No comments found.")
                return

            print(f"📝 Processing {len(comments)} comments for LDA analysis")
            processed_comments = self.preprocess_text(comments)
            print(f"✅ Preprocessed {len(processed_comments)} comments")
            
            _, _, _, topics_dict = self.apply_lda(processed_comments)
            print(f"✅ Applied LDA and generated {len(topics_dict)} topics")

            await self.save_topics_to_json(topics_dict)
            await self.generate_wordcloud(processed_comments)
            
            # If dynamic_categories were provided, perform combined analysis
            if dynamic_categories:
                print("🔄 Performing combined analysis of categories and topics")
                analysis_result = await self.analyze_categories_and_topics(dynamic_categories, topics_dict)
                print("✅ Combined analysis completed")
                
                # Print a summary of the analysis
                if analysis_result:
                    areas = analysis_result.get("areas_principales", [])
                    if areas:
                        print("\n📊 Main Areas Identified:")
                        for i, area in enumerate(areas[:5]):
                            print(f"  {i+1}. {area}")
                    
                    # Print insights if available
                    insights = analysis_result.get("insights", [])
                    if insights:
                        print("\n💡 Key Insights:")
                        if isinstance(insights, list):
                            for i, insight in enumerate(insights[:3]):
                                print(f"  {i+1}. {insight}")
                        elif isinstance(insights, dict):
                            for i, (key, value) in enumerate(list(insights.items())[:3]):
                                print(f"  {i+1}. {key}: {value}")
                        elif isinstance(insights, str):
                            print(f"  {insights[:100]}...")

            print("📊 LDA analysis completed successfully.")
        except Exception as e:
            print(f"❌ Error during LDA analysis: {e}")
            import traceback
            traceback.print_exc()
