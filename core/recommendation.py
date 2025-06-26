# core/recommendation.py
"""
GreenRec Recommendation Engine
=============================
Machine Learning alapú ajánlórendszer, amely felelős:
- Content-based filtering (TF-IDF + Cosine Similarity)
- A/B/C csoport algoritmusok implementálásáért
- Személyre szabott ajánlások generálásáért
- ESI inverz normalizálás kezeléséért
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Optional, Tuple
import logging
import random

from config import current_config
from core.data_manager import data_manager

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """ML alapú ajánlórendszer"""
    
    def __init__(self):
        self.recipes_df: Optional[pd.DataFrame] = None
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.cosine_sim_matrix = None
        self.is_initialized = False
    
    def initialize(self) -> bool:
        """
        Ajánlórendszer inicializálása
        
        Returns:
            bool: Sikeres inicializálás
        """
        try:
            # Adatok betöltése
            self.recipes_df = data_manager.load_recipe_data()
            
            # TF-IDF modell létrehozása
            self._setup_tfidf_model()
            
            self.is_initialized = True
            logger.info("✅ RecommendationEngine inicializálva")
            return True
            
        except Exception as e:
            logger.error(f"❌ RecommendationEngine inicializálási hiba: {e}")
            return False
    
    def _setup_tfidf_model(self):
        """TF-IDF modell beállítása content-based filteringhez"""
        if self.recipes_df is None or len(self.recipes_df) == 0:
            raise ValueError("Nincs betöltött recept adat")
        
        # TF-IDF vektorizáló létrehozása
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=current_config.TFIDF_MAX_FEATURES,
            stop_words=None,  # Magyar stopwords később
            ngram_range=current_config.TFIDF_NGRAM_RANGE,
            min_df=1,
            lowercase=True
        )
        
        # TF-IDF mátrix számítása
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(
            self.recipes_df['ingredients_text']
        )
        
        # Cosine similarity mátrix előszámítása (opcionális, ha kevés recept)
        if len(self.recipes_df) <= 1000:  # Csak kis adatseteknél
            self.cosine_sim_matrix = cosine_similarity(self.tfidf_matrix)
        
        logger.info(f"TF-IDF modell kész: {self.tfidf_matrix.shape}")
    
    def get_recommendations(self, user_group: str, user_ratings: List[Dict] = None, 
                          round_number: int = 1, n: int = 5) -> pd.DataFrame:
        """
        Ajánlások generálása A/B/C teszt alapján
        
        Args:
            user_group: 'A', 'B', vagy 'C' csoport
            user_ratings: Korábbi felhasználói értékelések
            round_number: Jelenlegi tanulási kör
            n: Ajánlások száma
            
        Returns:
            pd.DataFrame: Ajánlott receptek
        """
        if not self.is_initialized:
            self.initialize()
        
        try:
            if user_group == 'A':
                return self._group_a_algorithm(user_ratings, round_number, n)
            elif user_group == 'B':
                return self._group_b_algorithm(user_ratings, round_number, n)
            elif user_group == 'C':
                return self._group_c_algorithm(user_ratings, round_number, n)
            else:
                logger.warning(f"Ismeretlen csoport: {user_group}, fallback A csoportra")
                return self._group_a_algorithm(user_ratings, round_number, n)
                
        except Exception as e:
            logger.error(f"❌ Ajánlás generálási hiba: {e}")
            # Fallback: random ajánlások
            return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
    
    def _group_a_algorithm(self, user_ratings: List[Dict], round_number: int, n: int) -> pd.DataFrame:
        """
        A csoport: Tiszta content-based filtering (score rejtve)
        Csak összetevő-alapú hasonlóság, nincs score guidance
        """
        if round_number == 1 or not user_ratings:
            # Első kör: random vagy népszerűség alapú
            return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
        
        # Content-based ajánlás a kedvelt receptek alapján
