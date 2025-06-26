# services/rating_service.py
"""
GreenRec Rating Service
======================
Értékelési szolgáltatás, amely felelős:
- Felhasználói értékelések kezeléséért
- Session-based adattárolásért
- Tanulási körök követéséért
- PostgreSQL integráció előkészítéséért
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import uuid
import hashlib
from dataclasses import dataclass, asdict
from flask import session

from config import current_config
from core.data_manager import data_manager

logger = logging.getLogger(__name__)

@dataclass
class UserRating:
    """Felhasználói értékelés adatmodell"""
    rating_id: str
    user_id: str
    recipe_id: int
    rating: int  # 1-5 csillag
    round_number: int
    user_group: str  # A, B, vagy C
    timestamp: str
    recipe_data: Optional[Dict] = None

@dataclass
class UserSession:
    """Felhasználói session adatmodell"""
    user_id: str
    user_group: str
    current_round: int
    ratings_history: List[UserRating]
    session_start: str
    last_activity: str

class RatingService:
    """Értékelési szolgáltatás"""
    
    def __init__(self):
        self.sessions_cache = {}  # Memory cache session adatokhoz
    
    def initialize_user_session(self) -> Tuple[str, str, int]:
        """
        Felhasználói session inicializálása vagy visszaállítása
        
        Returns:
            Tuple[str, str, int]: (user_id, user_group, current_round)
        """
        try:
            # Meglévő session ellenőrzése
            if 'user_id' in session and 'user_group' in session:
                user_id = session['user_id']
                user_group = session['user_group']
                current_round = session.get('current_round', 1)
                
                logger.info(f"Meglévő session: {user_id} (Csoport: {user_group}, Kör: {current_round})")
                return user_id, user_group, current_round
            
            # Új session létrehozása
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            user_group = self._assign_user_group(user_id)
            current_round = 1
            
            # Session adatok mentése
            session['user_id'] = user_id
            session['user_group'] = user_group
            session['current_round'] = current_round
            session['session_start'] = datetime.now().isoformat()
            session['ratings_history'] = []
            session.permanent = True
            
            logger.info(f"Új session létrehozva: {user_id} (Csoport: {user_group})")
            return user_id, user_group, current_round
            
        except Exception as e:
            logger.error(f"Session inicializálási hiba: {e}")
            # Fallback értékek
            return "anonymous", "A", 1
    
    def _assign_user_group(self, user_id: str) -> str:
        """
        Felhasználó determinisztikus A/B/C csoport kiosztása
        
        Args:
            user_id: Felhasználó azonosító
            
        Returns:
            str: Csoport azonosító ('A', 'B', vagy 'C')
        """
        # Determinisztikus hash-based assignment
        hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        group_index = hash_value % len(current_config.ABC_GROUPS)
        
        return current_config.ABC_GROUPS[group_index]
    
    def save_rating(self, recipe_id: int, rating: int, round_number: int) -> bool:
        """
        Értékelés mentése
        
        Args:
            recipe_id: Recept azonosító
            rating: Értékelés (1-5)
            round_number: Tanulási kör száma
            
        Returns:
            bool: Sikeres mentés
        """
        try:
            # Session adatok lekérése
            user_id = session.get('user_id', 'anonymous')
            user_group = session.get('user_group', 'A')
            
            # Input validáció
            if not (1 <= rating <= 5):
                logger.error(f"Érvénytelen értékelés: {rating}")
                return False
            
            if not (1 <= round_number <= current_config.MAX_LEARNING_ROUNDS):
                logger.error(f"Érvénytelen kör száma: {round_number}")
                return False
            
            # Recept adatok lekérése
            recipe_data = data_manager.get_recipe_by_id(recipe_id)
            if not recipe_data:
                logger.error(f"Recept nem található: {recipe_id}")
                return False
            
            # Értékelés objektum létrehozása
            rating_obj = UserRating(
                rating_id=f"{user_id}_{recipe_id}_{round_number}_{datetime.now().timestamp()}",
                user_id=user_id,
                recipe_id=recipe_id,
                rating=rating,
                round_number=round_number,
                user_group=user_group,
                timestamp=datetime.now().isoformat(),
                recipe_data=recipe_data
            )
            
            # Session-be mentés
            if 'ratings_history' not in session:
                session['ratings_history'] = []
            
            # Duplikált értékelés ellenőrzése (ugyanaz a recept ugyanabban a körben)
            existing_ratings = session['ratings_history']
            duplicate_rating = any(
                r.get('recipe_id') == recipe_id and r.get('round_number') == round_number
                for r in existing_ratings
            )
            
            if duplicate_rating:
                # Frissítés meglévő értékeléshez
                for i, r in enumerate(existing_ratings):
                    if r.get('recipe_id') == recipe_id and r.get('round_number') == round_number:
                        existing_ratings[i] = asdict(rating_obj)
                        break
                logger.info(f"Értékelés frissítve: {recipe_id} -> {rating}")
            else:
                # Új értékelés hozzáadása
                existing_ratings.append(asdict(rating_obj))
                logger.info(f"Új értékelés mentve: {recipe_id} -> {rating}")
            
            session['ratings_history'] = existing_ratings
            session['last_activity'] = datetime.now().isoformat()
            
            return True
            
        except Exception as e:
            logger.error(f"Értékelés mentési hiba: {e}")
            return False
    
    def get_user_ratings(self, round_number: Optional[int] = None) -> List[Dict]:
        """
        Felhasználó értékeléseinek lekérdezése
        
        Args:
            round_number: Opcionális kör szűrés
            
        Returns:
            List[Dict]: Értékelések listája
        """
        try:
            ratings_history = session.get('ratings_history', [])
            
            if round_number is not None:
                # Kör szerinti szűrés
                filtered_ratings = [
                    r for r in ratings_history 
                    if r.get('round_number') == round_number
                ]
                return filtered_ratings
            
            return ratings_history
            
        except Exception as e:
            logger.error(f"Értékelések lekérdezési hiba: {e}")
            return []
    
    def can_proceed_to_next_round(self, current_round: int) -> Tuple[bool, int, int]:
        """
        Ellenőrzi, hogy lehet-e a következő körre lépni
        
        Args:
            current_round: Jelenlegi kör
            
        Returns:
            Tuple[bool, int, int]: (lehet_lepni, aktualis_ertekelesek, szukseges_ertekelesek)
        """
        try:
            current_round_ratings = self.get_user_ratings(current_round)
            rating_count = len(current_round_ratings)
            required_ratings = current_config.MIN_RATINGS_FOR_NEXT_ROUND
            
            can_proceed = rating_count >= required_ratings
            
            return can_proceed, rating_count, required_ratings
            
        except Exception as e:
            logger.error(f"Következő kör ellenőrzési hiba: {e}")
            return False, 0, current_config.MIN_RATINGS_FOR_NEXT_ROUND
    
    def advance_to_next_round(self) -> Tuple[bool, int]:
        """
        Következő körre lépés
        
        Returns:
            Tuple[bool, int]: (sikeres_lepes, uj_kor_szama)
        """
        try:
            current_round = session.get('current_round', 1)
            
            # Ellenőrzés, hogy lehet-e lépni
            can_proceed, rating_count, required = self.can_proceed_to_next_round(current_round)
            
            if not can_proceed:
                logger.warning(f"Nem lehet lépni: {rating_count}/{required} értékelés")
                return False, current_round
            
            # Maximum kör ellenőrzése
            if current_round >= current_config.MAX_LEARNING_ROUNDS:
                logger.info("Utolsó kör elérve, tanulmány befejezése")
                session['study_completed'] = True
                return True, current_round  # Marad az utolsó kör
            
            # Következő körre lépés
            new_round = current_round + 1
            session['current_round'] = new_round
            session['last_activity'] = datetime.now().isoformat()
            
            logger.info(f"Sikeres lépés: {current_round} -> {new_round}")
            return True, new_round
            
        except Exception as e:
            logger.error(f"Következő kör lépési hiba: {e}")
            return False, session.get('current_round', 1)
    
    def is_study_completed(self) -> bool:
        """Ellenőrzi, hogy a tanulmány befejeződött-e"""
        current_round = session.get('current_round', 1)
        study_completed = session.get('study_completed', False)
        
        return study_completed or current_round >= current_config.MAX_LEARNING_ROUNDS
    
    def get_user_session_summary(self) -> Dict:
        """
        Felhasználói session összefoglalója
        
        Returns:
            Dict: Session statisztikák
        """
        try:
            ratings_history = session.get('ratings_history', [])
            
            # Alapstatisztikák
            total_ratings = len(ratings_history)
            ratings_by_round = {}
            
            for round_num in range(1, current_config.MAX_LEARNING_ROUNDS + 1):
                round_ratings = [r for r in ratings_history if r.get('round_number') == round_num]
                ratings_by_round[f'round_{round_num}'] = len(round_ratings)
            
            # Értékelési szokások
            rating_distribution = {i: 0 for i in range(1, 6)}
            for rating in ratings_history:
                rating_val = rating.get('rating', 0)
                if 1 <= rating_val <= 5:
                    rating_distribution[rating_val] += 1
            
            # Session időtartam
            session_start = session.get('session_start')
            session_duration = None
            if session_start:
                start_time = datetime.fromisoformat(session_start)
                duration = datetime.now() - start_time
                session_duration = duration.total_seconds() / 60  # percek
            
            return {
                'user_id': session.get('user_id', 'unknown'),
                'user_group': session.get('user_group', 'unknown'),
                'current_round': session.get('current_round', 1),
                'total_ratings': total_ratings,
                'ratings_by_round': ratings_by_round,
                'rating_distribution': rating_distribution,
                'session_duration_minutes': session_duration,
                'study_completed': self.is_study_completed(),
                'last_activity': session.get('last_activity')
            }
            
        except Exception as e:
            logger.error(f"Session összefoglaló hiba: {e}")
            return {'error': str(e)}
    
    def clear_user_session(self) -> bool:
        """
        Felhasználói session törlése (új kezdés)
        
        Returns:
            bool: Sikeres törlés
        """
        try:
            # Session kulcsok törlése
            keys_to_clear = [
                'user_id', 'user_group', 'current_round', 
                'ratings_history', 'session_start', 'last_activity',
                'study_completed'
            ]
            
            for key in keys_to_clear:
                session.pop(key, None)
            
            logger.info("Session sikeresen törölve")
            return True
            
        except Exception as e:
            logger.error(f"Session törlési hiba: {e}")
            return False

# Globális rating service instance
rating_service = RatingService() 
