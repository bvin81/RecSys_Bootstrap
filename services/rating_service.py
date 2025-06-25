# services/rating_service.py
"""
GreenRec Rating Service
======================

Felhasználói értékelési szolgáltatás, amely felelős:
- Értékelések mentéséért és kezeléséért
- Felhasználói preferenciák tanulásáért
- Binary relevance konverzióért (rating → relevant/irrelevant)
- User metrics számításáért (Precision@K, Recall@K, F1@K)
- Tanulási folyamat trackingéért (körök kezelése)

Algoritmus: Rating >= 4 = relevant, < 4 = irrelevant
Tanulás: Kategória, összetevő, ESI/HSI/PPI preferenciák
Metrikák: Precision@5, Recall@5, F1-Score@5
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import defaultdict

from models.recommendation import get_recommendation_engine
from services.data_service import get_data_service


@dataclass
class Rating:
    """Értékelés adatstruktúra"""
    timestamp: str
    user_id: str
    recipe_id: int
    rating: int  # 1-5 skála
    relevance: int  # 0=irrelevant, 1=relevant
    comment: str
    group: str  # A/B/C csoport
    round: int  # Tanulási kör


@dataclass
class UserPreferences:
    """Felhasználói preferenciák adatstruktúra"""
    liked_categories: List[str]
    liked_ingredients: List[str]
    esi_scores: List[float]
    hsi_scores: List[float]
    ppi_scores: List[float]
    
    def to_dict(self) -> Dict:
        """Konverzió dictionary-vé"""
        return asdict(self)


@dataclass
class UserMetrics:
    """Felhasználói metrikák adatstruktúra"""
    precision: float
    recall: float
    f1_score: float
    true_positives: int
    false_positives: int
    false_negatives: int
    num_ratings: int
    num_relevant: int
    round_metrics: Dict[str, float]
    current_round: int


class RatingService:
    """
    Értékelési szolgáltatás osztály
    
    Felelősségek:
    - Felhasználói értékelések kezelése
    - Preferenciák tanulása és tárolása
    - Binary relevance számítása
    - User-level metrikák számítása
    - Tanulási folyamat tracking
    """
    
    def __init__(self):
        """RatingService inicializálása"""
        self.ratings: List[Rating] = []
        self.user_preferences: Dict[str, UserPreferences] = {}
        self.user_sessions: Dict[str, Dict] = {}
        
    def save_rating(self, user_id: str, recipe_id: int, rating: int, 
                   comment: str = "", group: str = "control", round_num: int = 1) -> Optional[Rating]:
        """
        Felhasználói értékelés mentése
        
        Args:
            user_id: Felhasználó azonosító
            recipe_id: Recept azonosító
            rating: Értékelés (1-5 skála)
            comment: Opcionális megjegyzés
            group: A/B/C csoport
            round_num: Tanulási kör száma
            
        Returns:
            Optional[Rating]: Mentett értékelés vagy None hiba esetén
        """
        try:
            # Input validálás
            if not (1 <= rating <= 5):
                raise ValueError(f"Érvénytelen rating: {rating} (1-5 között kell lennie)")
            
            # Binary relevance számítása
            # Rating >= 4 = relevant (1), < 4 = irrelevant (0)
            relevance = 1 if rating >= 4 else 0
            
            # Rating objektum létrehozása
            rating_obj = Rating(
                timestamp=datetime.now().isoformat(),
                user_id=str(user_id),
                recipe_id=int(recipe_id),
                rating=int(rating),
                relevance=relevance,
                comment=comment,
                group=group,
                round=round_num
            )
            
            # Meglévő értékelés felülírása (ha van)
            self._remove_existing_rating(user_id, recipe_id)
            
            # Új értékelés hozzáadása
            self.ratings.append(rating_obj)
            
            # Felhasználói preferenciák frissítése
            self._update_user_preferences(user_id, recipe_id, rating)
            
            # Session információk frissítése
            self._update_user_session(user_id, round_num)
            
            return rating_obj
            
        except Exception as e:
            print(f"❌ Rating mentési hiba: {e}")
            return None
    
    def _remove_existing_rating(self, user_id: str, recipe_id: int) -> None:
        """Meglévő értékelés eltávolítása (ha van)"""
        self.ratings = [
            r for r in self.ratings 
            if not (r.user_id == str(user_id) and r.recipe_id == int(recipe_id))
        ]
    
    def _update_user_preferences(self, user_id: str, recipe_id: int, rating: int) -> None:
        """
        Felhasználói preferenciák frissítése az értékelés alapján
        
        Tanulási logika:
        - Rating >= 4: Pozitív példa → preferenciák frissítése
        - Rating < 4: Negatív példa → nincs preferencia frissítés
        
        Args:
            user_id: Felhasználó azonosító
            recipe_id: Recept azonosító  
            rating: Értékelés
        """
        try:
            # Csak pozitív értékeléseknél tanulunk
            if rating < 4:
                return
            
            # Recept adatok lekérése
            data_service = get_data_service()
            recipes_df = data_service.get_recipes_dataframe()
            
            if recipes_df is None:
                return
            
            recipe_data = recipes_df[recipes_df['id'] == int(recipe_id)]
            if recipe_data.empty:
                return
            
            recipe = recipe_data.iloc[0]
            
            # Preferenciák inicializálása (ha szükséges)
            if user_id not in self.user_preferences:
                self.user_preferences[user_id] = UserPreferences(
                    liked_categories=[],
                    liked_ingredients=[],
                    esi_scores=[],
                    hsi_scores=[],
                    ppi_scores=[]
                )
            
            prefs = self.user_preferences[user_id]
            
            # 1. Kedvelt kategóriák tanulása
            category = recipe.get('category', 'Unknown')
            if category not in prefs.liked_categories:
                prefs.liked_categories.append(category)
            
            # 2. Kedvelt összetevők tanulása (első 3 szó)
            ingredients = str(recipe.get('ingredients', '')).split()[:3]
            for ingredient in ingredients:
                if ingredient.lower() not in [ing.lower() for ing in prefs.liked_ingredients]:
                    prefs.liked_ingredients.append(ingredient.lower())
            
            # 3. ESI/HSI/PPI preferenciák tanulása
            esi_final = recipe.get('ESI_final', recipe.get('ESI', 50))
            hsi = recipe.get('HSI', 50)
            ppi = recipe.get('PPI', 50)
            
            prefs.esi_scores.append(float(esi_final))
            prefs.hsi_scores.append(float(hsi))
            prefs.ppi_scores.append(float(ppi))
            
            # Preferenciák listáinak limitálása (memória optimalizálás)
            self._limit_preference_lists(prefs)
            
        except Exception as e:
            print(f"❌ Preferencia frissítési hiba: {e}")
    
    def _limit_preference_lists(self, prefs: UserPreferences, max_items: int = 20) -> None:
        """Preferencia listák méretének korlátozása"""
        prefs.liked_categories = prefs.liked_categories[-max_items:]
        prefs.liked_ingredients = prefs.liked_ingredients[-max_items:]
        prefs.esi_scores = prefs.esi_scores[-max_items:]
        prefs.hsi_scores = prefs.hsi_scores[-max_items:]
        prefs.ppi_scores = prefs.ppi_scores[-max_items:]
    
    def _update_user_session(self, user_id: str, round_num: int) -> None:
        """Felhasználói session információk frissítése"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'current_round': round_num,
                'ratings_per_round': defaultdict(int),
                'last_activity': datetime.now().isoformat()
            }
        
        session = self.user_sessions[user_id]
        session['current_round'] = max(session['current_round'], round_num)
        session['ratings_per_round'][round_num] += 1
        session['last_activity'] = datetime.now().isoformat()
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """
        Felhasználói preferenciák lekérése
        
        Args:
            user_id: Felhasználó azonosító
            
        Returns:
            Optional[Dict]: Preferenciák dictionary vagy None
        """
        if user_id in self.user_preferences:
            return self.user_preferences[user_id].to_dict()
        return None
    
    def get_user_ratings(self, user_id: str, round_num: Optional[int] = None) -> List[Rating]:
        """
        Felhasználó értékelései lekérése
        
        Args:
            user_id: Felhasználó azonosító
            round_num: Opcionális kör szűrés
            
        Returns:
            List[Rating]: Értékelések listája
        """
        user_ratings = [r for r in self.ratings if r.user_id == str(user_id)]
        
        if round_num is not None:
            user_ratings = [r for r in user_ratings if r.round == round_num]
        
        return user_ratings
    
    def calculate_user_metrics(self, user_id: str, k: int = 5) -> Optional[UserMetrics]:
        """
        Felhasználói metrikák számítása (Precision@K, Recall@K, F1@K)
        
        Algoritmus:
        1. Felhasználó relevant receptjei (rating >= 4)
        2. Legutóbbi ajánlások generálása (top K)
        3. Precision = |relevant ∩ recommended| / |recommended|
        4. Recall = |relevant ∩ recommended| / |relevant|
        5. F1 = 2 * (precision * recall) / (precision + recall)
        
        Args:
            user_id: Felhasználó azonosító
            k: Top-K ajánlások száma
            
        Returns:
            Optional[UserMetrics]: Számított metrikák vagy None
        """
        try:
            user_ratings = self.get_user_ratings(user_id)
            
            # Minimum 3 értékelés szükséges
            if len(user_ratings) < 3:
                return None
            
            # Relevant receptek (rating >= 4)
            relevant_recipes: Set[int] = {r.recipe_id for r in user_ratings if r.relevance == 1}
            
            if not relevant_recipes:
                return None
            
            # Ajánlások generálása a jelenlegi preferenciák alapján
            recommended_recipes = self._generate_recommendations_for_metrics(user_id, k)
            recommended_ids: Set[int] = {r for r in recommended_recipes}
            
            # Metrikák számítása
            true_positives = len(recommended_ids.intersection(relevant_recipes))
            false_positives = len(recommended_ids - relevant_recipes)
            false_negatives = len(relevant_recipes - recommended_ids)
            
            # Precision, Recall, F1 számítása
            precision = true_positives / len(recommended_ids) if len(recommended_ids) > 0 else 0.0
            recall = true_positives / len(relevant_recipes) if len(relevant_recipes) > 0 else 0.0
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            # Körönkénti metrikák számítása
            round_metrics = self._calculate_round_metrics(user_id)
            
            # Jelenlegi kör meghatározása
            current_round = max([r.round for r in user_ratings]) if user_ratings else 1
            
            return UserMetrics(
                precision=precision,
                recall=recall,
                f1_score=f1,
                true_positives=true_positives,
                false_positives=false_positives,
                false_negatives=false_negatives,
                num_ratings=len(user_ratings),
                num_relevant=len(relevant_recipes),
                round_metrics=round_metrics,
                current_round=current_round
            )
            
        except Exception as e:
            print(f"❌ User metrics számítási hiba: {e}")
            return None
    
    def _generate_recommendations_for_metrics(self, user_id: str, k: int) -> List[int]:
        """
        Ajánlások generálása metrikák számításához
        
        Args:
            user_id: Felhasználó azonosító
            k: Ajánlások száma
            
        Returns:
            List[int]: Ajánlott recept ID-k
        """
        try:
            engine = get_recommendation_engine()
            user_prefs = self.get_user_preferences(user_id)
            current_round = self.user_sessions.get(user_id, {}).get('current_round', 1)
            
            recommendations = engine.get_personalized_recommendations(
                user_preferences=user_prefs or {},
                current_round=current_round,
                n=k
            )
            
            return [rec['id'] for rec in recommendations]
            
        except Exception as e:
            print(f"❌ Ajánlások generálási hiba metrikákhoz: {e}")
            return []
    
    def _calculate_round_metrics(self, user_id: str) -> Dict[str, float]:
        """
        Körönkénti metrikák számítása
        
        Args:
            user_id: Felhasználó azonosító
            
        Returns:
            Dict[str, float]: Körönkénti átlagos értékelések
        """
        round_metrics = {}
        user_ratings = self.get_user_ratings(user_id)
        
        # Csoportosítás körök szerint
        rounds_data = defaultdict(list)
        for rating in user_ratings:
            rounds_data[rating.round].append(rating.rating)
        
        # Átlagok számítása körönként
        for round_num, ratings_list in rounds_data.items():
            avg_rating = np.mean(ratings_list)
            round_metrics[f'round_{round_num}_avg_rating'] = avg_rating
        
        return round_metrics
    
    def can_advance_round(self, user_id: str, min_ratings: int = 6) -> bool:
        """
        Ellenőrzi, hogy a felhasználó továbbléphet-e a következő körre
        
        Args:
            user_id: Felhasználó azonosító
            min_ratings: Minimum értékelések száma körönként
            
        Returns:
            bool: Továbbléphet a következő körre
        """
        if user_id not in self.user_sessions:
            return False
        
        current_round = self.user_sessions[user_id]['current_round']
        current_round_ratings = len(self.get_user_ratings(user_id, current_round))
        
        return current_round_ratings >= min_ratings
    
    def advance_user_round(self, user_id: str) -> Tuple[bool, int]:
        """
        Felhasználó továbbítása a következő körre
        
        Args:
            user_id: Felhasználó azonosító
            
        Returns:
            Tuple[bool, int]: (Sikeres továbblépés, Új kör száma)
        """
        if not self.can_advance_round(user_id):
            current_round = self.user_sessions.get(user_id, {}).get('current_round', 1)
            return False, current_round
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {'current_round': 1, 'ratings_per_round': defaultdict(int)}
        
        self.user_sessions[user_id]['current_round'] += 1
        new_round = self.user_sessions[user_id]['current_round']
        
        return True, new_round
    
    def get_user_session_info(self, user_id: str) -> Dict:
        """
        Felhasználói session információk lekérése
        
        Args:
            user_id: Felhasználó azonosító
            
        Returns:
            Dict: Session információk
        """
        if user_id not in self.user_sessions:
            return {
                'current_round': 1,
                'total_ratings': 0,
                'ratings_in_current_round': 0,
                'can_advance': False
            }
        
        session = self.user_sessions[user_id]
        current_round = session['current_round']
        total_ratings = len(self.get_user_ratings(user_id))
        current_round_ratings = len(self.get_user_ratings(user_id, current_round))
        
        return {
            'current_round': current_round,
            'total_ratings': total_ratings,
            'ratings_in_current_round': current_round_ratings,
            'can_advance': self.can_advance_round(user_id),
            'ratings_per_round': dict(session['ratings_per_round']),
            'last_activity': session.get('last_activity', 'Unknown')
        }
    
    def get_all_ratings(self) -> List[Rating]:
        """
        Összes értékelés lekérése
        
        Returns:
            List[Rating]: Összes értékelés
        """
        return self.ratings.copy()
    
    def get_rating_statistics(self) -> Dict:
        """
        Értékelési statisztikák lekérése
        
        Returns:
            Dict: Statisztikai adatok
        """
        if not self.ratings:
            return {
                'total_ratings': 0,
                'unique_users': 0,
                'avg_rating': 0.0,
                'relevance_rate': 0.0
            }
        
        total_ratings = len(self.ratings)
        unique_users = len(set(r.user_id for r in self.ratings))
        avg_rating = np.mean([r.rating for r in self.ratings])
        relevant_count = sum(1 for r in self.ratings if r.relevance == 1)
        relevance_rate = relevant_count / total_ratings
        
        # Csoportonkénti statisztikák
        group_stats = defaultdict(list)
        for rating in self.ratings:
            group_stats[rating.group].append(rating.rating)
        
        group_averages = {
            group: np.mean(ratings) 
            for group, ratings in group_stats.items()
        }
        
        return {
            'total_ratings': total_ratings,
            'unique_users': unique_users,
            'avg_rating': float(avg_rating),
            'relevance_rate': float(relevance_rate),
            'group_averages': group_averages,
            'ratings_by_round': self._get_ratings_by_round_stats()
        }
    
    def _get_ratings_by_round_stats(self) -> Dict[int, int]:
        """Körönkénti értékelési statisztikák"""
        round_counts = defaultdict(int)
        for rating in self.ratings:
            round_counts[rating.round] += 1
        return dict(round_counts)


# Singleton pattern a globális eléréshez
_rating_service = None

def get_rating_service() -> RatingService:
    """
    Globális RatingService instance lekérése
    
    Returns:
        RatingService: RatingService instance
    """
    global _rating_service
    if _rating_service is None:
        _rating_service = RatingService()
    return _rating_service
