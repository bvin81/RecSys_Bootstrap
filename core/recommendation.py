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
        liked_recipes = [r for r in user_ratings if r.get('rating', 0) >= 4]
        
        if not liked_recipes:
            return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
        
        # Kedvelt receptek ID-i
        liked_recipe_ids = [r['recipe_id'] for r in liked_recipes]
        
        # Content-based similarity számítás
        recommendations = self._get_content_similar_recipes(liked_recipe_ids, n * 2)
        
        # Random keveredés (A csoport nem látja a score-okat)
        return recommendations.sample(n=min(n, len(recommendations)))
    
    def _group_b_algorithm(self, user_ratings: List[Dict], round_number: int, n: int) -> pd.DataFrame:
        """
        B csoport: Score-enhanced recommendations
        Kompozit pontszám alapú ajánlás + content filtering
        """
        if round_number == 1 or not user_ratings:
            # Első kör: legjobb kompozit score-ok
            return self.recipes_df.nlargest(n, 'composite_score')
        
        # Hibrid megközelítés: content + score
        liked_recipes = [r for r in user_ratings if r.get('rating', 0) >= 4]
        
        if liked_recipes:
            # Content-based komponens
            liked_recipe_ids = [r['recipe_id'] for r in liked_recipes]
            content_recommendations = self._get_content_similar_recipes(liked_recipe_ids, n * 3)
            
            # Score-based rendezés
            return content_recommendations.nlargest(n, 'composite_score')
        else:
            # Fallback: legjobb score-ok
            return self.recipes_df.nlargest(n, 'composite_score')
    
    def _group_c_algorithm(self, user_ratings: List[Dict], round_number: int, n: int) -> pd.DataFrame:
        """
        C csoport: Advanced hybrid + explainable AI
        Személyre szabott súlyozás + diverzitás + tanulás
        """
        if round_number == 1 or not user_ratings:
            # Első kör: diverzitás-alapú kiválasztás
            return self._get_diverse_recommendations(n)
        
        # Haladó személyre szabás
        user_preferences = self._analyze_user_preferences(user_ratings)
        
        # Dinamikus scoring a preferenciák alapján
        personalized_df = self.recipes_df.copy()
        personalized_df['personalized_score'] = (
            personalized_df['esi_inverted'] * user_preferences['eco_weight'] +
            personalized_df['health_score'] * user_preferences['health_weight'] +
            personalized_df['popularity'] * user_preferences['popularity_weight']
        )
        
        # Diverzitás biztosítása
        diverse_recommendations = self._ensure_diversity(
            personalized_df.nlargest(n * 2, 'personalized_score'), n
        )
        
        return diverse_recommendations
    
    def _get_content_similar_recipes(self, liked_recipe_ids: List[int], n: int) -> pd.DataFrame:
        """
        Content-based hasonló receptek keresése TF-IDF alapján
        
        Args:
            liked_recipe_ids: Kedvelt receptek ID-i
            n: Visszaadandó receptek száma
            
        Returns:
            pd.DataFrame: Hasonló receptek
        """
        try:
            # Kedvelt receptek indexei
            liked_indices = []
            for recipe_id in liked_recipe_ids:
                idx = self.recipes_df[self.recipes_df['recipe_id'] == recipe_id].index
                if len(idx) > 0:
                    liked_indices.append(idx[0])
            
            if not liked_indices:
                return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
            
            # Átlagos TF-IDF vektor a kedvelt receptekből
            liked_vectors = self.tfidf_matrix[liked_indices]
            avg_vector = np.mean(liked_vectors.toarray(), axis=0)
            
            # Hasonlóság számítás minden recepttel
            similarities = cosine_similarity([avg_vector], self.tfidf_matrix)[0]
            
            # Top N hasonló recept (már értékelt receptek kizárása)
            recipe_scores = list(enumerate(similarities))
            recipe_scores = [(i, score) for i, score in recipe_scores 
                           if i not in liked_indices and score > current_config.SIMILARITY_THRESHOLD]
            recipe_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Top receptek kiválasztása
            top_indices = [i for i, _ in recipe_scores[:n]]
            
            if not top_indices:
                # Ha nincs elég hasonló, random kiválasztás
                available_indices = [i for i in range(len(self.recipes_df)) if i not in liked_indices]
                top_indices = random.sample(available_indices, min(n, len(available_indices)))
            
            return self.recipes_df.iloc[top_indices]
            
        except Exception as e:
            logger.error(f"Content similarity hiba: {e}")
            return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
    
    def _analyze_user_preferences(self, user_ratings: List[Dict]) -> Dict[str, float]:
        """
        Felhasználói preferenciák elemzése értékelések alapján
        
        Args:
            user_ratings: Felhasználói értékelések
            
        Returns:
            Dict: Preferencia súlyok
        """
        if not user_ratings:
            return {'eco_weight': 0.4, 'health_weight': 0.4, 'popularity_weight': 0.2}
        
        # Magasan értékelt receptek elemzése
        high_rated = [r for r in user_ratings if r.get('rating', 0) >= 4]
        low_rated = [r for r in user_ratings if r.get('rating', 0) <= 2]
        
        if not high_rated:
            return {'eco_weight': 0.4, 'health_weight': 0.4, 'popularity_weight': 0.2}
        
        # Átlagos értékek a jó és rossz értékelésekhez
        high_eco = np.mean([r.get('esi_inverted', 50) for r in high_rated])
        high_health = np.mean([r.get('health_score', 60) for r in high_rated])
        high_popularity = np.mean([r.get('popularity', 70) for r in high_rated])
        
        # Dinamikus súlyozás a preferenciák alapján
        total_score = high_eco + high_health + high_popularity
        
        if total_score > 0:
            eco_weight = high_eco / total_score
            health_weight = high_health / total_score
            popularity_weight = high_popularity / total_score
        else:
            eco_weight, health_weight, popularity_weight = 0.4, 0.4, 0.2
        
        return {
            'eco_weight': max(0.1, min(0.7, eco_weight)),  # Limitálás 10-70% között
            'health_weight': max(0.1, min(0.7, health_weight)),
            'popularity_weight': max(0.1, min(0.7, popularity_weight))
        }
    
    def _get_diverse_recommendations(self, n: int) -> pd.DataFrame:
        """
        Diverzitás-alapú ajánlások (C csoport első körében)
        
        Args:
            n: Ajánlások száma
            
        Returns:
            pd.DataFrame: Diverzitás-optimalizált receptek
        """
        try:
            # Kategóriák szerinti diverzitás
            if 'category' in self.recipes_df.columns:
                categories = self.recipes_df['category'].unique()
                recipes_per_category = max(1, n // len(categories))
                
                diverse_recipes = []
                for category in categories:
                    category_recipes = self.recipes_df[self.recipes_df['category'] == category]
                    if len(category_recipes) > 0:
                        # Legjobb kompozit score-ok kategóriánként
                        selected = category_recipes.nlargest(recipes_per_category, 'composite_score')
                        diverse_recipes.append(selected)
                
                diverse_df = pd.concat(diverse_recipes, ignore_index=True)
                
                # Ha kevés lett, kiegészítés
                if len(diverse_df) < n:
                    remaining = self.recipes_df[~self.recipes_df['recipe_id'].isin(diverse_df['recipe_id'])]
                    additional = remaining.nlargest(n - len(diverse_df), 'composite_score')
                    diverse_df = pd.concat([diverse_df, additional], ignore_index=True)
                
                return diverse_df.head(n)
            else:
                # Fallback: score alapú
                return self.recipes_df.nlargest(n, 'composite_score')
                
        except Exception as e:
            logger.error(f"Diverzitás hiba: {e}")
            return self.recipes_df.nlargest(n, 'composite_score')
    
    def _ensure_diversity(self, candidates: pd.DataFrame, n: int) -> pd.DataFrame:
        """
        Diverzitás biztosítása a végső ajánlásokban
        
        Args:
            candidates: Jelölt receptek
            n: Végső ajánlások száma
            
        Returns:
            pd.DataFrame: Diverzitás-optimalizált receptek
        """
        if len(candidates) <= n:
            return candidates
        
        try:
            # Greedy diverzitás algoritmus
            selected = []
            remaining = candidates.copy()
            
            # Első recept: legjobb score
            first = remaining.nlargest(1, 'personalized_score')
            selected.append(first.iloc[0])
            remaining = remaining[remaining['recipe_id'] != first.iloc[0]['recipe_id']]
            
            # További receptek: max diverzitás
            for _ in range(n - 1):
                if len(remaining) == 0:
                    break
                
                best_candidate = None
                max_diversity = -1
                
                for _, candidate in remaining.iterrows():
                    # Diverzitás számítás (ingrediens különbség)
                    diversity_score = self._calculate_diversity_score(candidate, selected)
                    
                    # Kombinált score: diverzitás + eredeti score
                    combined_score = 0.7 * diversity_score + 0.3 * candidate['personalized_score'] / 100
                    
                    if combined_score > max_diversity:
                        max_diversity = combined_score
                        best_candidate = candidate
                
                if best_candidate is not None:
                    selected.append(best_candidate)
                    remaining = remaining[remaining['recipe_id'] != best_candidate['recipe_id']]
            
            return pd.DataFrame(selected)
            
        except Exception as e:
            logger.error(f"Diverzitás biztosítási hiba: {e}")
            return candidates.head(n)
    
    def _calculate_diversity_score(self, candidate: pd.Series, selected: List[pd.Series]) -> float:
        """
        Diverzitás score számítása egy jelölt és a kiválasztott receptek között
        
        Args:
            candidate: Jelölt recept
            selected: Már kiválasztott receptek
            
        Returns:
            float: Diverzitás score (0-1)
        """
        if not selected:
            return 1.0
        
        try:
            # TF-IDF alapú diverzitás
            candidate_idx = candidate.name
            selected_indices = [s.name for s in selected]
            
            # Átlagos hasonlóság a kiválasztottakkal
            similarities = []
            for sel_idx in selected_indices:
                if self.cosine_sim_matrix is not None:
                    sim = self.cosine_sim_matrix[candidate_idx][sel_idx]
                else:
                    # On-the-fly számítás
                    candidate_vec = self.tfidf_matrix[candidate_idx]
                    selected_vec = self.tfidf_matrix[sel_idx]
                    sim = cosine_similarity(candidate_vec, selected_vec)[0][0]
                similarities.append(sim)
            
            # Diverzitás = 1 - átlagos hasonlóság
            avg_similarity = np.mean(similarities)
            return 1.0 - avg_similarity
            
        except Exception as e:
            logger.error(f"Diverzitás számítási hiba: {e}")
            return 0.5  # Közepes diverzitás fallback
    
    def search_recipes(self, query: str, max_results: int = 10) -> pd.DataFrame:
        """
        Keresés összetevők alapján TF-IDF-fel
        
        Args:
            query: Keresési kifejezés
            max_results: Maximális eredmények száma
            
        Returns:
            pd.DataFrame: Találatok
        """
        if not self.is_initialized:
            self.initialize()
        
        if not query or len(query.strip()) < 2:
            return pd.DataFrame()
        
        try:
            # Query vektorizálása
            query_vector = self.tfidf_vectorizer.transform([query.lower()])
            
            # Hasonlóság számítás
            similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]
            
            # Top találatok
            scored_recipes = list(enumerate(similarities))
            scored_recipes = [(i, score) for i, score in scored_recipes 
                            if score > current_config.SIMILARITY_THRESHOLD]
            scored_recipes.sort(key=lambda x: x[1], reverse=True)
            
            # Eredmények visszaadása
            top_indices = [i for i, _ in scored_recipes[:max_results]]
            results = self.recipes_df.iloc[top_indices].copy()
            
            # Relevancia score hozzáadása
            results['relevance_score'] = [scored_recipes[i][1] for i in range(len(top_indices))]
            
            return results
            
        except Exception as e:
            logger.error(f"Keresési hiba: {e}")
            return pd.DataFrame()
    
    def get_engine_stats(self) -> Dict:
        """Ajánlórendszer statisztikáinak lekérdezése"""
        if not self.is_initialized:
            return {'initialized': False}
        
        return {
            'initialized': True,
            'total_recipes': len(self.recipes_df),
            'tfidf_features': self.tfidf_matrix.shape[1] if self.tfidf_matrix is not None else 0,
            'has_similarity_matrix': self.cosine_sim_matrix is not None,
            'avg_composite_score': self.recipes_df['composite_score'].mean(),
            'score_range': (
                self.recipes_df['composite_score'].min(),
                self.recipes_df['composite_score'].max()
            )
        }

# Globális recommendation engine instance
recommendation_engine = RecommendationEngine()
