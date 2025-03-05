import json
import re
import spacy
import matplotlib.pyplot as plt
from collections import Counter
from wordcloud import WordCloud
from gensim import corpora, models
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import nltk
import numpy as np
from app.services.storage.minio_service import MinioService
from app.db.session import SessionLocal
import aisuite as ai
from io import BytesIO
from app.services.business.competitive_analysis.instagram.base_instagram_module import BaseInstagramAnalyzer
from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramLDATopic

# Initialize database session
session = SessionLocal()

class InstagramTopicModeling(BaseInstagramAnalyzer):
    def __init__(self, username, output_folder, num_topics=5, lang = 'en'):
        super().__init__(username, output_folder)
        self.num_topics = num_topics
        self.lang = lang
        if lang == "es":
            self.nlp = spacy.load("es_core_news_sm")
        else:
            self.nlp = spacy.load("en_core_web_sm")
        nltk.download('punkt')
        nltk.download('stopwords')

    def preprocess_text(self, comments):
        """Preprocesses comments by cleaning, tokenizing, and lemmatizing text."""
        stop_words = set(stopwords.words('spanish'))
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
        """Generates a word cloud from processed comments and saves it to MinIO."""
        try:
            all_words = " ".join([" ".join(comment) for comment in processed_comments])
            wordcloud = WordCloud(width=800, height=400, background_color="white").generate(all_words)

            plt.figure(figsize=(10, 5))
            plt.imshow(wordcloud, interpolation="bilinear")
            plt.axis("off")
            plt.title("🌟 Nube de Palabras de Comentarios", fontsize=14)

            img_buffer = BytesIO()
            plt.savefig(img_buffer, format='png')
            plt.close()

            img_buffer.seek(0)
            image_data = img_buffer.getvalue()

            await self.minio_service.upload_content(
                object_name=f"{self.output_folder}/wordcloud.png",
                data=image_data,
                content_type="image/png"
            )

            print(f"✅ WordCloud saved in MinIO: {self.output_folder}/wordcloud.png")
        except Exception as e:
            print(f"❌ Error generating WordCloud: {e}")

    async def save_topics_to_json(self, topics_dict):
        """Saves the detected topics and statistics as a JSON file in MinIO and in the database."""
        try:
            # Save to MinIO
            output_path = f"{self.output_folder}/lda_topics.json"
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

    async def run_lda_analysis(self):
        """Main function to run the complete LDA analysis process."""
        try:
            comments = await self.load_comments()
            if not comments:
                print("❌ No comments found.")
                return

            processed_comments = self.preprocess_text(comments)
            _, _, _, topics_dict = self.apply_lda(processed_comments)

            await self.save_topics_to_json(topics_dict)
            await self.generate_wordcloud(processed_comments)

            print("📊 LDA analysis completed successfully.")
        except Exception as e:
            print(f"❌ Error during LDA analysis: {e}")
