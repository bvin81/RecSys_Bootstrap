# models/recommendation.py
"""
GreenRec Recommendation Engine
===============================

A GreenRec ajánlórendszer központi osztálya, amely felelős:
- Content-based filtering algoritmusért
- Hibrid scoring (similarity + sustainability) számításáért
- Személyre szabott ajánlások generálásáért
- Tanulási folyamat kezeléséért

Algoritmus: TF-IDF + Cosine Similarity + Kompozit Scoring
Tanulás: Felhasználói preferenciák alapján adaptív ajánlások
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Optional, Tuple
import random
from datetime import datetime


class GreenRecEngine:
    """
    GreenRec ajánlórendszer fő osztálya
    
    Felelősségek:
    - Content-based filtering (TF-IDF + Cosine Similarity)
    - Hibrid scoring (content + sustainability)
    - Személyre szabott ajánlások (tanulási alapú)
    - Kompozit pontszám számítása (ESI + HSI + PPI)
    """
    
    def __init__(self, recipes_df: pd.DataFrame = None):
        """
        Ajánlórendszer inicializálása
        
        Args:
            recipes_df: Receptek DataFrame ESI, HSI, PPI oszlopokkal
        """
        self.recipes_df = recipes_df
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.is_initialized = False
        
    def initialize(self, recipes_df: pd.DataFrame) -> bool:
        """
        Ajánlórendszer inicializálása adatokkal
        
        Args:
            recipes_df: Receptek DataFrame
            
        Returns:
            bool: Sikeres inicializálás
        """
        try:
            self.recipes_df = recipes_df.copy()
            
            # ESI inverz normalizálás (magasabb ESI = rosszabb környezetterhelés)
            self._normalize_esi_scores()
            
            # Kompozit pontszám számítása
            self._calculate_composite_scores()
            
            # TF-IDF vektorizálás beállítása
            self._setup_tfidf()
            
            self.is_initialized = True
            return True
            
        except Exception as e:
            print(f"❌ Recommendation Engine inicializálási hiba: {e}")
            return False
    
    def _normalize_esi_scores(self) -> None:
        """
        ESI pontszámok inverz normalizálása
        
        Logika: ESI magasabb érték = rosszabb környezetterhelés
        Ezért: ESI_final = 100 - normalizált_ESI
        """
        if 'ESI' in self.recipes_df.columns:
            esi_min = self.recipes_df['ESI'].min()
            esi_max = self.recipes_df['ESI'].max()
            
            # Normalizálás 0-100 közé
            self.recipes_df['ESI_normalized'] = 100 * (
                (self.recipes_df['ESI'] - esi_min) / (esi_max - esi_min)
            )
            
            # Inverz transzformáció (100 - normalizált)
            self.recipes_df['ESI_final'] = 100 - self.recipes_df['ESI_normalized']
            
            print(f"✅ ESI inverz normalizálás: {esi_min:.1f}-{esi_max:.1f} → 0-100 (inverz)")
        else:
            # Fallback: random ESI értékek
            self.recipes_df['ESI'] = [random.randint(30, 90) for _ in range(len(self.recipes_df))]
            self.recipes_df['ESI_final'] = 100 - self.recipes_df['ESI']
    
    def _calculate_composite_scores(self) -> None:
        """
        Kompozit pontszám számítása
        
        Képlet: ESI_final * 0.4 + HSI * 0.4 + PPI * 0.2
        
        Súlyozás:
        - ESI_final: 40% (környezeti hatás - inverz)
        - HSI: 40% (egészségügyi érték)
        - PPI: 20% (személyes preferencia)
        """
        # HSI és PPI ellenőrzése/létrehozása
        for col in ['HSI', 'PPI']:
            if col not in self.recipes_df.columns:
                self.recipes_df[col] = [random.randint(30, 90) for _ in range(len(self.recipes_df))]
        
        # Kompozit pontszám számítása
        self.recipes_df['composite_score'] = (
            self.recipes_df['ESI_final'] * 0.4 + 
            self.recipes_df['HSI'] * 0.4 + 
            self.recipes_df['PPI'] * 0.2
        )
        
        print(f"✅ Kompozit pontszám: "
              f"min={self.recipes_df['composite_score'].min():.1f}, "
              f"max={self.recipes_df['composite_score'].max():.1f}")
    
    def _setup_tfidf(self) -> None:
        """
        TF-IDF vektorizálás beállítása az összetevők alapján
        
        Paraméterek:
        - stop_words='english': Angol stopszavak kiszűrése
        - max_features=1000: Maximum 1000 feature
        - min_df=1: Minimum dokumentum gyakoriság
        """
        try:
            self.tfidf_vectorizer = TfidfVectorizer(
                stop_words='english', 
                max_features=1000, 
                min_df=1
            )
            
            # Összetevők szövegének előkészítése
            ingredients_text = self.recipes_df['ingredients'].fillna('').astype(str)
            
            # TF-IDF mátrix létrehozása
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(ingredients_text)
            
            print(f"✅ TF-IDF mátrix: {self.tfidf_matrix.shape}")
            
        except Exception as e:
            print(f"❌ TF-IDF beállítási hiba: {e}")
            self.tfidf_vectorizer = None
            self.tfidf_matrix = None
    
    def search_recipes(self, query: str, top_n: int = 10) -> List[Dict]:
        """
        Content-based keresés TF-IDF + Cosine Similarity alapján
        
        Args:
            query: Keresési kifejezés (összetevők)
            top_n: Visszaadandó receptek száma
            
        Returns:
            List[Dict]: Top N recept adatokkal
        """
        if not self.is_initialized or not query:
            return []
        
        try:
            # Query vektorizálása
            query_vec = self.tfidf_vectorizer.transform([query])
            
            # Cosine similarity számítása
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            
            # Hibrid scoring: 60% similarity + 40% composite score
            composite_normalized = self.recipes_df['composite_score'] / 100
            final_scores = similarities * 0.6 + composite_normalized * 0.4
            
            # Top N kiválasztása
            top_indices = final_scores.argsort()[-top_n:][::-1]
            
            # Eredmények összeállítása
            results = self.recipes_df.iloc[top_indices].copy()
            results['similarity_score'] = similarities[top_indices]
            results['final_score'] = final_scores[top_indices]
            results['recommendation_reason'] = 'Keresés alapján'
            
            return results.to_dict('records')
            
        except Exception as e:
            print(f"❌ Keresési hiba: {e}")
            return []
    
    def get_personalized_recommendations(self, user_preferences: Dict, 
                                       current_round: int = 1, 
                                       n: int = 6) -> List[Dict]:
        """
        Személyre szabott ajánlások generálása felhasználói preferenciák alapján
        
        Args:
            user_preferences: Felhasználói preferenciák dict
            current_round: Jelenlegi tanulási kör
            n: Ajánlások száma
            
        Returns:
            List[Dict]: Személyre szabott receptek
        """
        if not self.is_initialized:
            return []
        
        # 1. KÖR: Random receptek (baseline)
        if current_round == 1:
            return self._get_random_recommendations(n)
        
        # 2+ KÖR: Személyre szabott ajánlások
        if not user_preferences:
            return self._get_random_recommendations(n, reason="Nincs korábbi adat")
        
        return self._generate_preference_based_recommendations(user_preferences, n)
    
    def _get_random_recommendations(self, n: int, reason: str = "Kezdeti felfedezés") -> List[Dict]:
        """
        Random receptek kiválasztása (1. kör)
        
        Args:
            n: Receptek száma
            reason: Ajánlás indoklása
            
        Returns:
            List[Dict]: Random receptek
        """
        try:
            random_recipes = self.recipes_df.sample(n=min(n, len(self.recipes_df)))
            results = random_recipes.copy()
            results['similarity_score'] = 0.5
            results['recommendation_reason'] = reason
            
            return results.to_dict('records')
            
        except Exception as e:
            print(f"❌ Random ajánlások hiba: {e}")
            return []
    
    def _generate_preference_based_recommendations(self, preferences: Dict, n: int) -> List[Dict]:
        """
        Preferencia-alapú személyre szabott ajánlások
        
        Scoring logika:
        - Kategória egyezés: +30 pont
        - Összetevő egyezés: +20 pont/összetevő
        - ESI hasonlóság: +0-30 pont
        - HSI hasonlóság: +0-30 pont
        - Kompozit bonus: +0-20 pont
        
        Args:
            preferences: Felhasználói preferenciák
            n: Ajánlások száma
            
        Returns:
            List[Dict]: Személyre szabott receptek
        """
        try:
            scores = []
            reasons = []
            
            for idx, recipe in self.recipes_df.iterrows():
                score = 0
                reason_parts = []
                
                # 1. Kategória egyezés
                score += self._calculate_category_score(recipe, preferences, reason_parts)
                
                # 2. Összetevő egyezés
                score += self._calculate_ingredient_score(recipe, preferences, reason_parts)
                
                # 3. ESI hasonlóság
                score += self._calculate_esi_similarity_score(recipe, preferences, reason_parts)
                
                # 4. HSI hasonlóság
                score += self._calculate_hsi_similarity_score(recipe, preferences, reason_parts)
                
                # 5. Kompozit pontszám bonus
                score += recipe.get('composite_score', 50) * 0.2
                
                scores.append(score)
                reasons.append(", ".join(reason_parts) if reason_parts else "általános ajánlás")
            
            # Top kandidátusok kiválasztása (diverzitás érdekében top 3N-ből)
            recipes_copy = self.recipes_df.copy()
            recipes_copy['personalization_score'] = scores
            recipes_copy['recommendation_reason'] = reasons
            
            top_candidates = recipes_copy.nlargest(n*3, 'personalization_score')
            results = top_candidates.sample(n=min(n, len(top_candidates)))
            
            # Similarity score normalizálása
            results['similarity_score'] = results['personalization_score'] / 100
            
            return results.to_dict('records')
            
        except Exception as e:
            print(f"❌ Személyre szabott ajánlások hiba: {e}")
            return self._get_random_recommendations(n, "Fallback ajánlás")
    
    def _calculate_category_score(self, recipe: pd.Series, preferences: Dict, 
                                reason_parts: List[str]) -> float:
        """Kategória egyezés pontszám számítása"""
        if 'liked_categories' in preferences:
            if recipe.get('category') in preferences['liked_categories']:
                reason_parts.append("kedvelt kategória")
                return 30
        return 0
    
    def _calculate_ingredient_score(self, recipe: pd.Series, preferences: Dict, 
                                  reason_parts: List[str]) -> float:
        """Összetevő egyezés pontszám számítása"""
        if 'liked_ingredients' not in preferences:
            return 0
        
        ingredients = str(recipe.get('ingredients', '')).lower()
        liked_ingredients = [ing.lower() for ing in preferences['liked_ingredients']]
        matches = sum(1 for ing in liked_ingredients if ing in ingredients)
        
        if matches > 0:
            reason_parts.append(f"{matches} kedvelt összetevő")
            return matches * 20
        return 0
    
    def _calculate_esi_similarity_score(self, recipe: pd.Series, preferences: Dict, 
                                      reason_parts: List[str]) -> float:
        """ESI hasonlóság pontszám számítása"""
        if 'esi_scores' not in preferences or not preferences['esi_scores']:
            return 0
        
        avg_esi_pref = np.mean(preferences['esi_scores'])
        esi_similarity = 100 - abs(recipe.get('ESI_final', 50) - avg_esi_pref)
        
        if esi_similarity > 70:
            reason_parts.append("hasonló környezeti profil")
        
        return esi_similarity * 0.3
    
    def _calculate_hsi_similarity_score(self, recipe: pd.Series, preferences: Dict, 
                                      reason_parts: List[str]) -> float:
        """HSI hasonlóság pontszám számítása"""
        if 'hsi_scores' not in preferences or not preferences['hsi_scores']:
            return 0
        
        avg_hsi_pref = np.mean(preferences['hsi_scores'])
        hsi_similarity = 100 - abs(recipe.get('HSI', 50) - avg_hsi_pref)
        
        if hsi_similarity > 70:
            reason_parts.append("hasonló egészségügyi profil")
        
        return hsi_similarity * 0.3
    
    def get_recipe_explanation(self, recipe: Dict, group: str = 'explanations') -> str:
        """
        XAI magyarázat generálása recepthez
        
        Args:
            recipe: Recept adatok
            group: Felhasználói csoport
            
        Returns:
            str: Magyarázó szöveg
        """
        if group != 'explanations':
            return ""
        
        explanations = []
        
        # Környezeti szempontok
        if recipe.get('ESI_final', 0) > 70:
            explanations.append("🌍 Környezetbarát választás")
        
        # Egészségügyi szempontok
        if recipe.get('HSI', 0) > 70:
            explanations.append("💚 Egészséges összetevők")
        
        # Népszerűség
        if recipe.get('PPI', 0) > 70:
            explanations.append("👤 Népszerű recept")
        
        # Kompozit pontszám
        composite = recipe.get('composite_score', 0)
        explanations.append(f"⭐ Magas kompozit pontszám ({composite:.0f}/100)")
        
        # Ajánlás indoklása
        if recipe.get('recommendation_reason'):
            explanations.append(f"🎯 {recipe['recommendation_reason']}")
        
        return "<br>".join(explanations)
    
    def get_algorithm_stats(self) -> Dict:
        """
        Algoritmus statisztikák lekérése
        
        Returns:
            Dict: Algoritmus teljesítmény adatok
        """
        if not self.is_initialized:
            return {}
        
        return {
            'total_recipes': len(self.recipes_df),
            'tfidf_features': self.tfidf_matrix.shape[1] if self.tfidf_matrix is not None else 0,
            'esi_range': {
                'min': float(self.recipes_df['ESI_final'].min()),
                'max': float(self.recipes_df['ESI_final'].max()),
                'avg': float(self.recipes_df['ESI_final'].mean())
            },
            'composite_score_range': {
                'min': float(self.recipes_df['composite_score'].min()),
                'max': float(self.recipes_df['composite_score'].max()),
                'avg': float(self.recipes_df['composite_score'].mean())
            },
            'algorithm_type': 'Content-based + Hibrid Scoring',
            'features': ['TF-IDF', 'Cosine Similarity', 'Composite Scoring', 'Personalization']
        }


# Singleton pattern a globális eléréshez
_recommendation_engine = None

def get_recommendation_engine() -> GreenRecEngine:
    """
    Globális ajánlórendszer instance lekérése
    
    Returns:
        GreenRecEngine: Ajánlórendszer instance
    """
    global _recommendation_engine
    if _recommendation_engine is None:
        _recommendation_engine = GreenRecEngine()
    return _recommendation_engine

def initialize_recommendation_engine(recipes_df: pd.DataFrame) -> bool:
    """
    Globális ajánlórendszer inicializálása
    
    Args:
        recipes_df: Receptek DataFrame
        
    Returns:
        bool: Sikeres inicializálás
    """
    engine = get_recommendation_engine()
    return engine.initialize(recipes_df)
