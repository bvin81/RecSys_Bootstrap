# models/recommendation_engine.py - ML Ajánlórendszer
"""
GreenRec Recommendation Engine
==============================
Machine Learning algoritmusok a receptajánlásokhoz:
- Content-based filtering (TF-IDF + Cosine Similarity)
- ESI inverz normalizálás és kompozit scoring
- A/B/C csoport algoritmusok
- Személyre szabott tanulás
"""

import pandas as pd
import numpy as np
import json
import random
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import Config
from utils.data_processing import normalize_esi_scores, calculate_composite_scores
from utils.helpers import safe_int, safe_float

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """
    GreenRec ML Ajánlórendszer
    ==========================
    """
    
    def __init__(self):
        """Recommendation engine inicializálása"""
        self.recipes_df: Optional[pd.DataFrame] = None
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.initialized = False
        
        # Inicializálás
        self._load_data()
        self._setup_ml_components()
    
    def _load_data(self):
        """Recept adatok betöltése"""
        logger.info("📊 Loading recipe data...")
        
        # Adatfájlok keresése
        data = None
        for filename in Config.DATA_FILES:
            try:
                file_path = Path(filename)
                if file_path.exists():
                    if filename.endswith('.json'):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        logger.info(f"✅ JSON data loaded: {filename}")
                        break
                    elif filename.endswith('.csv'):
                        df = pd.read_csv(file_path, encoding='utf-8')
                        data = df.to_dict('records')
                        logger.info(f"✅ CSV data loaded: {filename}")
                        break
            except Exception as e:
                logger.warning(f"⚠️ Could not load {filename}: {e}")
                continue
        
        # Fallback: demo adatok
        if data is None:
            logger.warning("⚠️ No data files found, generating demo data")
            data = self._generate_demo_data()
        
        # DataFrame létrehozása
        self.recipes_df = pd.DataFrame(data)
        self._process_recipe_data()
        
        logger.info(f"✅ Loaded {len(self.recipes_df)} recipes")
    
    def _process_recipe_data(self):
        """Recept adatok feldolgozása és normalizálása"""
        logger.info("🔧 Processing recipe data...")
        
        # ✅ ESI INVERZ NORMALIZÁLÁS
        if 'ESI' in self.recipes_df.columns:
            self.recipes_df = normalize_esi_scores(self.recipes_df)
            logger.info("✅ ESI scores normalized and inverted")
        else:
            # Ha nincs ESI, random értékek
            self.recipes_df['ESI_final'] = np.random.uniform(30, 80, len(self.recipes_df))
            logger.warning("⚠️ No ESI column found, using random values")
        
        # HSI és PPI ellenőrzése
        if 'HSI' not in self.recipes_df.columns:
            self.recipes_df['HSI'] = np.random.uniform(30, 95, len(self.recipes_df))
            logger.warning("⚠️ No HSI column found, using random values")
        
        if 'PPI' not in self.recipes_df.columns:
            self.recipes_df['PPI'] = np.random.uniform(20, 90, len(self.recipes_df))
            logger.warning("⚠️ No PPI column found, using random values")
        
        # ✅ KOMPOZIT PONTSZÁM SZÁMÍTÁSA
        self.recipes_df = calculate_composite_scores(self.recipes_df, Config.SCORE_WEIGHTS)
        
        # Recept nevek és képek biztosítása
        self._ensure_recipe_names_and_images()
        
        # Szükséges oszlopok ellenőrzése
        self._ensure_required_columns()
        
        # ID oszlop biztosítása
        if 'recipeid' not in self.recipes_df.columns and 'id' not in self.recipes_df.columns:
            self.recipes_df['recipeid'] = [f"recipe_{i+1}" for i in range(len(self.recipes_df))]
    
    def _ensure_recipe_names_and_images(self):
        """✅ Recept nevek és képek biztosítása"""
        
        # Recept nevek
        if 'recipe_name' not in self.recipes_df.columns and 'name' not in self.recipes_df.columns:
            hungarian_names = [
                "Gulyásleves", "Schnitzel burgonyával", "Lángos", "Halászlé",
                "Paprikash csirkével", "Töltött káposzta", "Lecsó", "Kürtőskalács",
                "Túrós csusza", "Bableves", "Rostélyos", "Rántott sajt",
                "Goulash", "Csörögefánk", "Túrógombóc", "Wiener Schnitzel",
                "Stefánia szelet", "Mákos guba", "Somlói galuska", "Dobostorta",
                "Vegán curry", "Quinoa saláta", "Avokádó toast", "Green smoothie",
                "Buddha bowl", "Lencsecurry", "Vegán pizza", "Chia puding",
                "Mandulatejes zabkása", "Spenótos lasagne", "Thai curry",
                "Pad thai", "Ramen leves", "Pho leves", "Caesar saláta",
                "Görög saláta", "Caprese saláta", "Waldorf saláta", "Tiramisu",
                "Panna cotta", "Brownie", "Granola bowl", "Smoothie bowl",
                "Acai bowl", "Overnight oats", "French toast", "Pancakes",
                "Muesli", "Fruit salad", "Energy balls", "Protein smoothie"
            ]
            
            self.recipes_df['recipe_name'] = [
                random.choice(hungarian_names) for _ in range(len(self.recipes_df))
            ]
        
        # Képek URL-jei
        if 'image_url' not in self.recipes_df.columns and 'images' not in self.recipes_df.columns:
            self.recipes_df['image_url'] = [
                f"{Config.IMAGE_PLACEHOLDER_BASE}{i+100}" 
                for i in range(len(self.recipes_df))
            ]
        
        # Fallback name oszlopra
        if 'recipe_name' not in self.recipes_df.columns and 'name' in self.recipes_df.columns:
            self.recipes_df['recipe_name'] = self.recipes_df['name']
    
    def _ensure_required_columns(self):
        """Szükséges oszlopok biztosítása"""
        required_columns = {
            'category': ['Főétel', 'Leves', 'Saláta', 'Desszert', 'Snack', 'Reggeli'],
            'ingredients': ['hagyma, fokhagyma, paradicsom, paprika, olívaolaj']
        }
        
        for col, default_values in required_columns.items():
            if col not in self.recipes_df.columns:
                if isinstance(default_values, list) and len(default_values) > 1:
                    self.recipes_df[col] = [
                        random.choice(default_values) for _ in range(len(self.recipes_df))
                    ]
                else:
                    self.recipes_df[col] = default_values[0]
                logger.info(f"✅ Added missing column: {col}")
    
    def _setup_ml_components(self):
        """Machine learning komponensek inicializálása"""
        logger.info("🤖 Setting up ML components...")
        
        try:
            # TF-IDF vektorizáció
            content = []
            for _, recipe in self.recipes_df.iterrows():
                recipe_name = recipe.get('recipe_name', recipe.get('name', ''))
                category = recipe.get('category', '')
                ingredients = recipe.get('ingredients', '')
                text = f"{recipe_name} {category} {ingredients}"
                content.append(text.lower())
            
            # TF-IDF inicializálása
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=Config.TFIDF_MAX_FEATURES,
                ngram_range=Config.TFIDF_NGRAM_RANGE,
                stop_words=None  # Magyar szavakhoz nincs beépített stop words
            )
            
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(content)
            
            self.initialized = True
            logger.info("✅ TF-IDF vectorizer initialized")
            logger.info(f"📊 TF-IDF matrix shape: {self.tfidf_matrix.shape}")
            
        except Exception as e:
            logger.error(f"❌ ML setup error: {e}")
            self.initialized = False
    
    def _generate_demo_data(self) -> List[Dict]:
        """Demo receptek generálása"""
        categories = ['Főétel', 'Leves', 'Saláta', 'Desszert', 'Snack', 'Reggeli']
        ingredients_lists = [
            'hagyma, fokhagyma, paradicsom, paprika, olívaolaj',
            'csirkemell, brokkoli, rizs, szójaszósz, gyömbér',
            'saláta, uborka, paradicsom, olívaolaj, citrom',
            'tojás, liszt, cukor, vaj, vanília, csokoládé',
            'mandula, dió, méz, zabpehely, áfonya, banán',
            'avokádó, spenót, banán, chia mag, kókusztej',
            'quinoa, fekete bab, kukorica, lime, koriander',
            'lazac, spárga, citrom, olívaolaj, fokhagyma'
        ]
        
        recipe_names = [
            "Magyaros gulyás", "Zöldséges curry", "Caesar saláta", "Csokoládé mousse",
            "Granola bowl", "Avokádó toast", "Pad thai", "Görög saláta",
            "Tiramisu", "Smoothie bowl", "Ramen leves", "Caprese saláta",
            "Brownie", "Acai bowl", "Thai curry", "Quinoa saláta",
            "Panna cotta", "Chia puding", "Pho leves", "Waldorf saláta",
            "Lángos", "Halászlé", "Kürtőskalács", "Lecsó",
            "Túrós csusza", "Schnitzel", "Goulash", "Paprikash",
            "Energy balls", "Green smoothie", "Buddha bowl", "Overnight oats"
        ]
        
        demo_recipes = []
        for i in range(60):  # Több demo recept
            demo_recipes.append({
                'recipeid': f'demo_recipe_{i+1}',
                'recipe_name': recipe_names[i % len(recipe_names)],
                'category': random.choice(categories),
                'ingredients': random.choice(ingredients_lists),
                'image_url': f"{Config.IMAGE_PLACEHOLDER_BASE}{i+200}",
                'ESI': random.uniform(10, 90),  # Környezeti hatás (magasabb = rosszabb)
                'HSI': random.uniform(30, 95),  # Egészségügyi (magasabb = jobb)
                'PPI': random.uniform(20, 90)   # Népszerűség (magasabb = jobb)
            })
        
        return demo_recipes
    
    # ============================================
    # AJÁNLÁSI ALGORITMUSOK
    # ============================================
    
    def get_personalized_recommendations(self, user_id: str, user_group: str, 
                                       learning_round: int, previous_ratings: Dict,
                                       n: int = 5) -> pd.DataFrame:
        """
        Személyre szabott ajánlások generálása A/B/C csoportok szerint
        """
        if not self.initialized:
            logger.error("❌ Recommendation engine not initialized")
            return pd.DataFrame()
        
        try:
            # 1. kör: Random receptek (baseline minden csoportnak)
            if learning_round == 1 or not previous_ratings:
                selected = self.recipes_df.sample(n=min(n, len(self.recipes_df)))
                logger.info(f"🎲 Random recommendations for {user_group} (round {learning_round})")
                return selected
            
            # 2+ kör: Csoportonkénti algoritmusok
            return self._get_algorithm_specific_recommendations(
                user_group, previous_ratings, n
            )
            
        except Exception as e:
            logger.error(f"❌ Recommendation generation error: {e}")
            # Fallback: random receptek
            return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
    
    def _get_algorithm_specific_recommendations(self, user_group: str, 
                                              previous_ratings: Dict, n: int) -> pd.DataFrame:
        """Csoportonkénti ajánlási algoritmusok"""
        
        # Kedvelt receptek elemzése (rating >= 4)
        liked_recipe_ids = [
            rid for rid, rating in previous_ratings.items() 
            if rating >= Config.RELEVANCE_THRESHOLD
        ]
        
        if not liked_recipe_ids:
            # Ha nincs kedvelt recept, magas kompozit pontszámúakat ajánljunk
            selected = self.recipes_df.nlargest(n, 'composite_score')
            logger.info(f"📊 High-score fallback for group {user_group}")
            return selected
        
        # Preferenciák tanulása
        liked_recipes = self.recipes_df[
            self.recipes_df['recipeid'].isin(liked_recipe_ids)
        ]
        
        if len(liked_recipes) == 0:
            return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
        
        # Még nem értékelt receptek
        unrated_recipes = self.recipes_df[
            ~self.recipes_df['recipeid'].isin(previous_ratings.keys())
        ].copy()
        
        if len(unrated_recipes) == 0:
            return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
        
        # Csoportonkénti algoritmusok
        if user_group == 'A':
            # ✅ Content-based (REJTETT pontszámok)
            selected = self._content_based_algorithm(liked_recipes, unrated_recipes, n)
            
        elif user_group == 'B':
            # Score-enhanced (pontszámok LÁTHATÓK)
            selected = self._score_enhanced_algorithm(liked_recipes, unrated_recipes, n)
            
        else:  # user_group == 'C'
            # Hybrid + XAI (pontszámok + magyarázatok)
            selected = self._hybrid_xai_algorithm(liked_recipes, unrated_recipes, n)
        
        logger.info(f"🎯 {user_group} algorithm: {len(selected)} recommendations")
        return selected
    
    def _content_based_algorithm(self, liked_recipes: pd.DataFrame, 
                                unrated_recipes: pd.DataFrame, n: int) -> pd.DataFrame:
        """A csoport: Content-based filtering (rejtett pontszámok)"""
        
        # Kategória preferenciák
        preferred_categories = liked_recipes['category'].value_counts().index.tolist()
        
        # Egyszerű kategória-alapú scoring
        unrated_recipes['score'] = unrated_recipes['category'].apply(
            lambda cat: 3.0 if cat in preferred_categories[:2] else 
                       2.0 if cat in preferred_categories[:4] else 1.0
        )
        
        # Random komponens hozzáadása a diverzitásért
        unrated_recipes['score'] += np.random.uniform(0, 0.5, len(unrated_recipes))
        
        return unrated_recipes.nlargest(n, 'score')
    
    def _score_enhanced_algorithm(self, liked_recipes: pd.DataFrame,
                                 unrated_recipes: pd.DataFrame, n: int) -> pd.DataFrame:
        """B csoport: Score-enhanced recommendations"""
        
        # Kategória és pontszám preferenciák
        preferred_categories = liked_recipes['category'].value_counts().index.tolist()
        avg_composite = liked_recipes['composite_score'].mean()
        
        # Kategória boost
        category_boost = unrated_recipes['category'].apply(
            lambda cat: 30 if cat in preferred_categories[:2] else 
                       20 if cat in preferred_categories[:4] else 10
        )
        
        # Kompozit pontszám similaritás
        composite_similarity = 1 - np.abs(unrated_recipes['composite_score'] - avg_composite) / 100
        
        # Kombinált scoring
        unrated_recipes['score'] = (
            unrated_recipes['composite_score'] * 0.5 +
            category_boost * 0.3 +
            composite_similarity * 20 * 0.2
        )
        
        return unrated_recipes.nlargest(n, 'score')
    
    def _hybrid_xai_algorithm(self, liked_recipes: pd.DataFrame,
                             unrated_recipes: pd.DataFrame, n: int) -> pd.DataFrame:
        """C csoport: Hybrid + XAI approach"""
        
        # Összes preferencia típus figyelembevétele
        preferred_categories = liked_recipes['category'].value_counts().index.tolist()
        avg_esi = liked_recipes['ESI_final'].mean()
        avg_hsi = liked_recipes['HSI'].mean()
        avg_ppi = liked_recipes['PPI'].mean()
        
        # Multi-dimensional similarity
        esi_similarity = 1 - np.abs(unrated_recipes['ESI_final'] - avg_esi) / 100
        hsi_similarity = 1 - np.abs(unrated_recipes['HSI'] - avg_hsi) / 100
        ppi_similarity = 1 - np.abs(unrated_recipes['PPI'] - avg_ppi) / 100
        
        # Kategória boost
        category_boost = unrated_recipes['category'].apply(
            lambda cat: 2.5 if cat in preferred_categories[:2] else 
                       1.5 if cat in preferred_categories[:4] else 1.0
        )
        
        # Kombinált scoring (legösszetettebb)
        unrated_recipes['score'] = (
            esi_similarity * 25 +      # Környezeti hasonlóság
            hsi_similarity * 25 +      # Egészségügyi hasonlóság  
            ppi_similarity * 15 +      # Népszerűségi hasonlóság
            category_boost * 15 +      # Kategória preferencia
            unrated_recipes['composite_score'] * 0.2  # Abszolút pontszám
        )
        
        return unrated_recipes.nlargest(n, 'score')
    
    # ============================================
    # KERESÉSI FUNKCIÓK
    # ============================================
    
    def search_by_ingredients(self, query: str, limit: int = 15) -> List[Dict]:
        """Összetevők alapján recept keresés TF-IDF hasonlósággal"""
        
        if not self.initialized or not query or len(query.strip()) < 2:
            return []
        
        try:
            # Query vektorizálása
            query_vector = self.tfidf_vectorizer.transform([query.lower()])
            
            # Cosine similarity számítása
            similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
            
            # Top eredmények kiválasztása
            top_indices = similarities.argsort()[-limit:][::-1]
            
            results = []
            for idx in top_indices:
                if similarities[idx] > Config.SEARCH_MIN_SIMILARITY:
                    recipe = self.recipes_df.iloc[idx]
                    results.append({
                        'recipeid': recipe.get('recipeid', f'recipe_{idx}'),
                        'recipe_name': recipe.get('recipe_name', recipe.get('name', f'Recept {idx+1}')),
                        'category': recipe.get('category', ''),
                        'ingredients': recipe.get('ingredients', ''),
                        'image_url': recipe.get('image_url', recipe.get('images', Config.DEFAULT_RECIPE_IMAGE)),
                        'similarity': round(similarities[idx], 3),
                        'composite_score': round(recipe.get('composite_score', 0), 1),
                        'ESI_final': round(recipe.get('ESI_final', 0), 1),
                        'HSI': round(recipe.get('HSI', 0), 1),
                        'PPI': round(recipe.get('PPI', 0), 1)
                    })
            
            logger.info(f"🔍 Search '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return []
    
    # ============================================
    # UTILITY ÉS STATUS FUNKCIÓK
    # ============================================
    
    def is_initialized(self) -> bool:
        """Engine inicializálási állapot"""
        return self.initialized and self.recipes_df is not None
    
    def tfidf_ready(self) -> bool:
        """TF-IDF ready állapot"""
        return self.tfidf_vectorizer is not None and self.tfidf_matrix is not None
    
    def get_recipe_count(self) -> int:
        """Betöltött receptek száma"""
        return len(self.recipes_df) if self.recipes_df is not None else 0
    
    def get_recipe_by_id(self, recipe_id: str) -> Optional[Dict]:
        """Recept lekérése ID alapján"""
        if not self.initialized:
            return None
        
        try:
            recipe = self.recipes_df[self.recipes_df['recipeid'] == recipe_id]
            if len(recipe) > 0:
                return recipe.iloc[0].to_dict()
            return None
        except Exception as e:
            logger.error(f"❌ Recipe lookup error: {e}")
            return None
    
    def get_data_statistics(self) -> Dict:
        """Adatok statisztikái"""
        if not self.initialized:
            return {}
        
        try:
            stats = {
                'total_recipes': len(self.recipes_df),
                'categories': self.recipes_df['category'].value_counts().to_dict(),
                'score_ranges': {
                    'ESI_final': {
                        'min': float(self.recipes_df['ESI_final'].min()),
                        'max': float(self.recipes_df['ESI_final'].max()),
                        'mean': float(self.recipes_df['ESI_final'].mean())
                    },
                    'HSI': {
                        'min': float(self.recipes_df['HSI'].min()),
                        'max': float(self.recipes_df['HSI'].max()),
                        'mean': float(self.recipes_df['HSI'].mean())
                    },
                    'PPI': {
                        'min': float(self.recipes_df['PPI'].min()),
                        'max': float(self.recipes_df['PPI'].max()),
                        'mean': float(self.recipes_df['PPI'].mean())
                    },
                    'composite_score': {
                        'min': float(self.recipes_df['composite_score'].min()),
                        'max': float(self.recipes_df['composite_score'].max()),
                        'mean': float(self.recipes_df['composite_score'].mean())
                    }
                },
                'tfidf_features': self.tfidf_matrix.shape[1] if self.tfidf_matrix is not None else 0,
                'missing_images': len(self.recipes_df[self.recipes_df['image_url'].isna()]) if 'image_url' in self.recipes_df.columns else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Statistics calculation error: {e}")
            return {}
    
    def refresh_data(self):
        """Adatok újratöltése és ML komponensek újrainicializálása"""
        logger.info("🔄 Refreshing recommendation engine data...")
        
        self.initialized = False
        self.recipes_df = None
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        
        # Újrainicializálás
        self._load_data()
        self._setup_ml_components()
        
        logger.info("✅ Recommendation engine refreshed")
    
    def get_random_recipes(self, n: int = 5) -> pd.DataFrame:
        """Random receptek lekérése (fallback funkcióhoz)"""
        if not self.initialized:
            return pd.DataFrame()
        
        return self.recipes_df.sample(n=min(n, len(self.recipes_df)))
    
    def validate_engine(self) -> Dict[str, bool]:
        """Engine validálása és hibaellenőrzés"""
        validation_results = {
            'data_loaded': self.recipes_df is not None,
            'has_recipes': len(self.recipes_df) > 0 if self.recipes_df is not None else False,
            'has_required_columns': False,
            'tfidf_initialized': self.tfidf_vectorizer is not None,
            'tfidf_matrix_ready': self.tfidf_matrix is not None,
            'scores_calculated': False,
            'images_available': False
        }
        
        if self.recipes_df is not None:
            required_cols = ['recipeid', 'recipe_name', 'category', 'ingredients', 'ESI_final', 'HSI', 'PPI', 'composite_score']
            validation_results['has_required_columns'] = all(col in self.recipes_df.columns for col in required_cols)
            
            validation_results['scores_calculated'] = 'composite_score' in self.recipes_df.columns
            validation_results['images_available'] = 'image_url' in self.recipes_df.columns
        
        # Összesített validation
        validation_results['overall_valid'] = all([
            validation_results['data_loaded'],
            validation_results['has_recipes'],
            validation_results['has_required_columns'],
            validation_results['tfidf_initialized'],
            validation_results['scores_calculated']
        ])
        
        return validation_results

# ============================================
# SINGLETON PATTERN IMPLEMENTATION
# ============================================

_recommendation_engine_instance = None

def get_recommendation_engine() -> RecommendationEngine:
    """Singleton pattern - egyetlen engine instance"""
    global _recommendation_engine_instance
    
    if _recommendation_engine_instance is None:
        _recommendation_engine_instance = RecommendationEngine()
        logger.info("✅ Recommendation engine singleton created")
    
    return _recommendation_engine_instance

def reset_recommendation_engine():
    """Engine reset (testing/debugging célokra)"""
    global _recommendation_engine_instance
    _recommendation_engine_instance = None
    logger.info("🔄 Recommendation engine singleton reset")

# Export
__all__ = ['RecommendationEngine', 'get_recommendation_engine', 'reset_recommendation_engine']
