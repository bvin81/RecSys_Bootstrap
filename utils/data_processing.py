# utils/data_processing.py
"""
GreenRec Data Processing Utilities
==================================

Adatfeldolgozási és előkészítési funkciók a GreenRec ajánlórendszerhez.
Tartalmazza a TF-IDF számításokat, hasonlóság metrikákat, adattisztítást és feature engineering-et.
"""

import re
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Any, Optional, Union, Set
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
from sklearn.decomposition import PCA
from scipy.sparse import csr_matrix
import logging
from collections import Counter, defaultdict
import unicodedata
import string

from .helpers import (
    safe_float, safe_int, clean_text, extract_ingredients, 
    extract_categories, normalize_score, inverse_normalize_score
)

logger = logging.getLogger(__name__)

# =====================================
# Data Loading and Validation
# =====================================

class DataProcessor:
    """Központi adatfeldolgozó osztály"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.processed_data = None
        
        # TF-IDF paraméterek
        self.tfidf_params = {
            'max_features': self.config.get('tfidf_max_features', 5000),
            'min_df': self.config.get('tfidf_min_df', 1),
            'max_df': self.config.get('tfidf_max_df', 0.95),
            'ngram_range': self.config.get('tfidf_ngram_range', (1, 2)),
            'stop_words': 'english'
        }
        
        logger.info("DataProcessor initialized")
    
    def load_json_data(self, file_paths: List[str]) -> Optional[pd.DataFrame]:
        """
        JSON adatok betöltése és DataFrame-mé alakítása
        
        Args:
            file_paths: JSON fájlok elérési útjai
            
        Returns:
            Pandas DataFrame vagy None
        """
        all_data = []
        
        for file_path in file_paths:
            try:
                if not Path(file_path).exists():
                    logger.warning(f"File not found: {file_path}")
                    continue
                
                logger.info(f"Loading data from: {file_path}")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle different JSON structures
                if isinstance(data, list):
                    all_data.extend(data)
                elif isinstance(data, dict):
                    if 'recipes' in data:
                        all_data.extend(data['recipes'])
                    elif 'data' in data:
                        all_data.extend(data['data'])
                    else:
                        all_data.append(data)
                
                logger.info(f"Loaded {len(data)} records from {file_path}")
                
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
                continue
        
        if not all_data:
            logger.error("No data loaded from any file")
            return None
        
        df = pd.DataFrame(all_data)
        logger.info(f"Total loaded records: {len(df)}")
        
        return df
    
    def validate_data_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Adatstruktúra validálása
        
        Args:
            df: Validálandó DataFrame
            
        Returns:
            Validációs eredmények
        """
        validation_results = {
            'is_valid': True,
            'issues': [],
            'statistics': {},
            'missing_columns': [],
            'data_types': {}
        }
        
        # Kötelező oszlopok ellenőrzése
        required_columns = ['id', 'name']
        optional_columns = ['description', 'ingredients', 'categories', 'ESI', 'HSI', 'PPI']
        
        missing_required = [col for col in required_columns if col not in df.columns]
        missing_optional = [col for col in optional_columns if col not in df.columns]
        
        if missing_required:
            validation_results['is_valid'] = False
            validation_results['issues'].append(f"Missing required columns: {missing_required}")
            validation_results['missing_columns'].extend(missing_required)
        
        if missing_optional:
            validation_results['issues'].append(f"Missing optional columns: {missing_optional}")
            validation_results['missing_columns'].extend(missing_optional)
        
        # Adattípusok ellenőrzése
        for col in df.columns:
            validation_results['data_types'][col] = str(df[col].dtype)
        
        # Alapstatisztikák
        validation_results['statistics'] = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'duplicate_ids': df.duplicated(subset=['id']).sum() if 'id' in df.columns else 0,
            'missing_values': df.isnull().sum().to_dict()
        }
        
        # Specifikus ellenőrzések
        if 'ESI' in df.columns:
            esi_stats = df['ESI'].describe().to_dict()
            validation_results['statistics']['esi_range'] = (esi_stats['min'], esi_stats['max'])
        
        if 'HSI' in df.columns:
            hsi_stats = df['HSI'].describe().to_dict()
            validation_results['statistics']['hsi_range'] = (hsi_stats['min'], hsi_stats['max'])
        
        if 'PPI' in df.columns:
            ppi_stats = df['PPI'].describe().to_dict()
            validation_results['statistics']['ppi_range'] = (ppi_stats['min'], ppi_stats['max'])
        
        logger.info(f"Data validation completed. Valid: {validation_results['is_valid']}")
        
        return validation_results
    
    def clean_and_normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adatok tisztítása és normalizálása
        
        Args:
            df: Tisztítandó DataFrame
            
        Returns:
            Tisztított DataFrame
        """
        logger.info("Starting data cleaning and normalization")
        
        df_clean = df.copy()
        
        # 1. ID oszlop biztosítása
        if 'id' not in df_clean.columns:
            df_clean['id'] = range(len(df_clean))
        else:
            # ID-k string-re konvertálása
            df_clean['id'] = df_clean['id'].astype(str)
        
        # 2. Név tisztítása
        if 'name' in df_clean.columns:
            df_clean['name'] = df_clean['name'].apply(lambda x: clean_text(str(x)) if pd.notna(x) else "Unknown Recipe")
        
        # 3. Leírás tisztítása
        if 'description' in df_clean.columns:
            df_clean['description'] = df_clean['description'].apply(
                lambda x: clean_text(str(x)) if pd.notna(x) else ""
            )
        
        # 4. Összetevők feldolgozása
        if 'ingredients' in df_clean.columns:
            df_clean['ingredients_list'] = df_clean['ingredients'].apply(extract_ingredients)
            df_clean['ingredients_text'] = df_clean['ingredients_list'].apply(
                lambda x: ' '.join(x) if isinstance(x, list) else ""
            )
            df_clean['ingredient_count'] = df_clean['ingredients_list'].apply(len)
        
        # 5. Kategóriák feldolgozása
        if 'categories' in df_clean.columns:
            df_clean['categories_list'] = df_clean['categories'].apply(extract_categories)
            df_clean['categories_text'] = df_clean['categories_list'].apply(
                lambda x: ' '.join(x) if isinstance(x, list) else ""
            )
            df_clean['category_count'] = df_clean['categories_list'].apply(len)
        
        # 6. Numerikus értékek tisztítása és normalizálása
        numeric_columns = ['ESI', 'HSI', 'PPI']
        
        for col in numeric_columns:
            if col in df_clean.columns:
                # Biztonságos float konverzió
                df_clean[col] = df_clean[col].apply(safe_float)
                
                # Outlier kezelés (IQR módszer)
                Q1 = df_clean[col].quantile(0.25)
                Q3 = df_clean[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                # Outlier-ek capping-je
                df_clean[col] = df_clean[col].clip(lower=lower_bound, upper=upper_bound)
        
        # 7. ESI inverz normalizálása
        if 'ESI' in df_clean.columns:
            esi_min = df_clean['ESI'].min()
            esi_max = df_clean['ESI'].max()
            
            if esi_max > esi_min:
                df_clean['ESI_normalized'] = df_clean['ESI'].apply(
                    lambda x: normalize_score(x, esi_min, esi_max)
                )
                df_clean['ESI_final'] = 100 - df_clean['ESI_normalized']
            else:
                df_clean['ESI_final'] = 50.0  # Konstans érték ha nincs variancia
        
        # 8. HSI és PPI normalizálása (ha szükséges)
        for col in ['HSI', 'PPI']:
            if col in df_clean.columns:
                col_min = df_clean[col].min()
                col_max = df_clean[col].max()
                
                if col_max > col_min:
                    df_clean[f'{col}_normalized'] = df_clean[col].apply(
                        lambda x: normalize_score(x, col_min, col_max)
                    )
                else:
                    df_clean[f'{col}_normalized'] = df_clean[col]
        
        # 9. Kompozit pontszám számítása
        if all(col in df_clean.columns for col in ['ESI_final', 'HSI', 'PPI']):
            esi_weight = self.config.get('sustainability_weight', 0.4)
            hsi_weight = self.config.get('health_weight', 0.4)
            ppi_weight = self.config.get('popularity_weight', 0.2)
            
            df_clean['composite_score'] = (
                df_clean['ESI_final'] * esi_weight +
                df_clean['HSI'] * hsi_weight +
                df_clean['PPI'] * ppi_weight
            )
        
        # 10. Hiányzó értékek pótlása
        df_clean = self._fill_missing_values(df_clean)
        
        # 11. Duplikátumok eltávolítása
        initial_count = len(df_clean)
        df_clean = df_clean.drop_duplicates(subset=['name'], keep='first')
        removed_duplicates = initial_count - len(df_clean)
        
        if removed_duplicates > 0:
            logger.info(f"Removed {removed_duplicates} duplicate recipes")
        
        logger.info(f"Data cleaning completed. Final shape: {df_clean.shape}")
        
        return df_clean
    
    def _fill_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Hiányzó értékek intelligens pótlása
        
        Args:
            df: DataFrame hiányzó értékekkel
            
        Returns:
            DataFrame kitöltött értékekkel
        """
        df_filled = df.copy()
        
        # Numerikus oszlopok: median értékkel
        numeric_columns = ['ESI', 'HSI', 'PPI', 'ESI_final', 'composite_score']
        for col in numeric_columns:
            if col in df_filled.columns:
                median_value = df_filled[col].median()
                df_filled[col] = df_filled[col].fillna(median_value)
        
        # Szöveges oszlopok: üres string-gel
        text_columns = ['description', 'ingredients_text', 'categories_text']
        for col in text_columns:
            if col in df_filled.columns:
                df_filled[col] = df_filled[col].fillna("")
        
        # Lista oszlopok: üres listával
        list_columns = ['ingredients_list', 'categories_list']
        for col in list_columns:
            if col in df_filled.columns:
                df_filled[col] = df_filled[col].apply(lambda x: x if isinstance(x, list) else [])
        
        # Count oszlopok: 0-val
        count_columns = ['ingredient_count', 'category_count']
        for col in count_columns:
            if col in df_filled.columns:
                df_filled[col] = df_filled[col].fillna(0)
        
        return df_filled

# =====================================
# TF-IDF and Similarity Calculations
# =====================================

class SimilarityCalculator:
    """TF-IDF és hasonlóság számítások osztálya"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.vectorizers = {}
        self.matrices = {}
        
    def setup_tfidf_vectorizer(self, 
                              max_features: int = 5000,
                              min_df: int = 1,
                              max_df: float = 0.95,
                              ngram_range: Tuple[int, int] = (1, 2)) -> TfidfVectorizer:
        """
        TF-IDF vectorizer beállítása
        
        Args:
            max_features: Maximum feature-ök száma
            min_df: Minimum document frequency
            max_df: Maximum document frequency
            ngram_range: N-gram tartomány
            
        Returns:
            Konfigurált TfidfVectorizer
        """
        vectorizer = TfidfVectorizer(
            max_features=max_features,
            min_df=min_df,
            max_df=max_df,
            ngram_range=ngram_range,
            stop_words='english',
            lowercase=True,
            token_pattern=r'\b[a-zA-Z][a-zA-Z]+\b',  # Csak betűk, min 2 karakter
            strip_accents='unicode'
        )
        
        return vectorizer
    
    def create_content_vectors(self, df: pd.DataFrame) -> Dict[str, csr_matrix]:
        """
        Tartalom vektorok létrehozása TF-IDF-fel
        
        Args:
            df: Feldolgozott DataFrame
            
        Returns:
            Vektorok dictionary
        """
        vectors = {}
        
        # 1. Összetevők vektorai
        if 'ingredients_text' in df.columns:
            logger.info("Creating ingredients TF-IDF vectors")
            
            ingredients_vectorizer = self.setup_tfidf_vectorizer(
                max_features=2000,
                min_df=1,
                ngram_range=(1, 1)  # Csak unigram összetevőknél
            )
            
            ingredients_texts = df['ingredients_text'].fillna("").tolist()
            vectors['ingredients'] = ingredients_vectorizer.fit_transform(ingredients_texts)
            self.vectorizers['ingredients'] = ingredients_vectorizer
            
            logger.info(f"Ingredients vectors shape: {vectors['ingredients'].shape}")
        
        # 2. Kategóriák vektorai
        if 'categories_text' in df.columns:
            logger.info("Creating categories TF-IDF vectors")
            
            categories_vectorizer = self.setup_tfidf_vectorizer(
                max_features=500,
                min_df=1,
                ngram_range=(1, 1)
            )
            
            categories_texts = df['categories_text'].fillna("").tolist()
            vectors['categories'] = categories_vectorizer.fit_transform(categories_texts)
            self.vectorizers['categories'] = categories_vectorizer
            
            logger.info(f"Categories vectors shape: {vectors['categories'].shape}")
        
        # 3. Leírás vektorai
        if 'description' in df.columns:
            logger.info("Creating description TF-IDF vectors")
            
            description_vectorizer = self.setup_tfidf_vectorizer(
                max_features=3000,
                min_df=2,
                ngram_range=(1, 2)
            )
            
            descriptions = df['description'].fillna("").tolist()
            vectors['description'] = description_vectorizer.fit_transform(descriptions)
            self.vectorizers['description'] = description_vectorizer
            
            logger.info(f"Description vectors shape: {vectors['description'].shape}")
        
        # 4. Kombinált tartalom vektorok
        combined_texts = []
        for _, row in df.iterrows():
            text_parts = []
            
            # Név (3x súly)
            if 'name' in row and pd.notna(row['name']):
                text_parts.extend([row['name']] * 3)
            
            # Leírás (2x súly)  
            if 'description' in row and pd.notna(row['description']):
                text_parts.extend([row['description']] * 2)
            
            # Összetevők
            if 'ingredients_text' in row and pd.notna(row['ingredients_text']):
                text_parts.append(row['ingredients_text'])
            
            # Kategóriák
            if 'categories_text' in row and pd.notna(row['categories_text']):
                text_parts.append(row['categories_text'])
            
            combined_texts.append(' '.join(text_parts))
        
        if combined_texts:
            logger.info("Creating combined content TF-IDF vectors")
            
            combined_vectorizer = self.setup_tfidf_vectorizer(
                max_features=5000,
                min_df=1,
                ngram_range=(1, 2)
            )
            
            vectors['combined'] = combined_vectorizer.fit_transform(combined_texts)
            self.vectorizers['combined'] = combined_vectorizer
            
            logger.info(f"Combined vectors shape: {vectors['combined'].shape}")
        
        self.matrices = vectors
        return vectors
    
    def calculate_cosine_similarity(self, vectors: csr_matrix) -> np.ndarray:
        """
        Cosine similarity mátrix számítása
        
        Args:
            vectors: TF-IDF vektorok
            
        Returns:
            Similarity mátrix
        """
        similarity_matrix = cosine_similarity(vectors)
        return similarity_matrix
    
    def calculate_content_similarity(self, 
                                   item_idx: int, 
                                   vectors: Dict[str, csr_matrix],
                                   weights: Dict[str, float] = None) -> np.ndarray:
        """
        Súlyozott tartalmi hasonlóság számítása
        
        Args:
            item_idx: Elem index
            vectors: Vektorok dictionary
            weights: Súlyok dictionary
            
        Returns:
            Hasonlósági pontszámok array
        """
        if weights is None:
            weights = {
                'ingredients': 0.3,
                'categories': 0.2,
                'description': 0.2,
                'combined': 0.3
            }
        
        total_similarity = None
        total_weight = 0
        
        for vector_type, vector_matrix in vectors.items():
            if vector_type in weights:
                weight = weights[vector_type]
                
                # Egy elem hasonlósága az összes többihez
                item_vector = vector_matrix[item_idx:item_idx+1]
                similarity_scores = cosine_similarity(item_vector, vector_matrix).flatten()
                
                if total_similarity is None:
                    total_similarity = similarity_scores * weight
                else:
                    total_similarity += similarity_scores * weight
                
                total_weight += weight
        
        if total_similarity is not None and total_weight > 0:
            return total_similarity / total_weight
        else:
            return np.zeros(len(vectors[list(vectors.keys())[0]].toarray()))

# =====================================
# Feature Engineering
# =====================================

class FeatureEngineer:
    """Feature engineering és transformációk osztálya"""
    
    def __init__(self):
        self.scalers = {}
        self.encoders = {}
        self.feature_names = []
    
    def create_numerical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Numerikus feature-ök létrehozása
        
        Args:
            df: Bemeneti DataFrame
            
        Returns:
            DataFrame új feature-ökkel
        """
        df_features = df.copy()
        
        # 1. Összetevő-alapú feature-ök
        if 'ingredients_list' in df_features.columns:
            # Összetevők száma
            df_features['ingredient_count'] = df_features['ingredients_list'].apply(len)
            
            # Speciális összetevők jelzése
            df_features['has_meat'] = df_features['ingredients_list'].apply(
                lambda x: any(ingredient.lower() in ['chicken', 'beef', 'pork', 'fish', 'meat'] 
                             for ingredient in x)
            ).astype(int)
            
            df_features['has_dairy'] = df_features['ingredients_list'].apply(
                lambda x: any(ingredient.lower() in ['milk', 'cheese', 'butter', 'cream', 'yogurt'] 
                             for ingredient in x)
            ).astype(int)
            
            df_features['has_vegetables'] = df_features['ingredients_list'].apply(
                lambda x: any(ingredient.lower() in ['tomato', 'onion', 'carrot', 'pepper', 'spinach', 'broccoli'] 
                             for ingredient in x)
            ).astype(int)
        
        # 2. Kategória-alapú feature-ök
        if 'categories_list' in df_features.columns:
            df_features['category_count'] = df_features['categories_list'].apply(len)
            
            # Főbb kategóriák jelzése
            df_features['is_vegetarian'] = df_features['categories_list'].apply(
                lambda x: any('vegetarian' in str(cat).lower() for cat in x)
            ).astype(int)
            
            df_features['is_dessert'] = df_features['categories_list'].apply(
                lambda x: any('dessert' in str(cat).lower() or 'sweet' in str(cat).lower() for cat in x)
            ).astype(int)
            
            df_features['is_healthy'] = df_features['categories_list'].apply(
                lambda x: any(keyword in str(cat).lower() 
                             for cat in x 
                             for keyword in ['healthy', 'diet', 'low-fat', 'nutrition'])
            ).astype(int)
        
        # 3. Szöveg-alapú feature-ök
        if 'description' in df_features.columns:
            df_features['description_length'] = df_features['description'].apply(
                lambda x: len(str(x)) if pd.notna(x) else 0
            )
            
            df_features['description_word_count'] = df_features['description'].apply(
                lambda x: len(str(x).split()) if pd.notna(x) else 0
            )
        
        # 4. Fenntarthatósági kategóriák
        if 'composite_score' in df_features.columns:
            df_features['sustainability_level'] = pd.cut(
                df_features['composite_score'],
                bins=[0, 40, 70, 100],
                labels=['Low', 'Medium', 'High']
            )
            
            # One-hot encoding
            sustainability_dummies = pd.get_dummies(
                df_features['sustainability_level'], 
                prefix='sustainability'
            )
            df_features = pd.concat([df_features, sustainability_dummies], axis=1)
        
        # 5. Népszerűségi kategóriák
        if 'PPI' in df_features.columns:
            df_features['popularity_level'] = pd.cut(
                df_features['PPI'],
                bins=[0, 30, 70, 100],
                labels=['Niche', 'Popular', 'Trending']
            )
            
            popularity_dummies = pd.get_dummies(
                df_features['popularity_level'], 
                prefix='popularity'
            )
            df_features = pd.concat([df_features, popularity_dummies], axis=1)
        
        # 6. Interakciós feature-ök
        if all(col in df_features.columns for col in ['ESI_final', 'HSI']):
            # Eco-health balance
            df_features['eco_health_balance'] = (
                df_features['ESI_final'] + df_features['HSI']
            ) / 2
            
            # ESI-HSI különbség
            df_features['eco_health_diff'] = abs(
                df_features['ESI_final'] - df_features['HSI']
            )
        
        logger.info(f"Created {len(df_features.columns) - len(df.columns)} new features")
        
        return df_features
    
    def encode_categorical_features(self, df: pd.DataFrame, 
                                  categorical_columns: List[str] = None) -> pd.DataFrame:
        """
        Kategorikus változók kódolása
        
        Args:
            df: Bemeneti DataFrame
            categorical_columns: Kódolandó oszlopok
            
        Returns:
            DataFrame kódolt változókkal
        """
        df_encoded = df.copy()
        
        if categorical_columns is None:
            categorical_columns = ['sustainability_level', 'popularity_level']
        
        for col in categorical_columns:
            if col in df_encoded.columns:
                # Label encoding numerikus változókhoz
                if col not in self.encoders:
                    self.encoders[col] = LabelEncoder()
                    df_encoded[f'{col}_encoded'] = self.encoders[col].fit_transform(
                        df_encoded[col].astype(str)
                    )
                else:
                    df_encoded[f'{col}_encoded'] = self.encoders[col].transform(
                        df_encoded[col].astype(str)
                    )
        
        return df_encoded
    
    def scale_numerical_features(self, df: pd.DataFrame, 
                                numerical_columns: List[str] = None) -> pd.DataFrame:
        """
        Numerikus változók skálázása
        
        Args:
            df: Bemeneti DataFrame
            numerical_columns: Skálázandó oszlopok
            
        Returns:
            DataFrame skálázott változókkal
        """
        df_scaled = df.copy()
        
        if numerical_columns is None:
            numerical_columns = [
                'ESI_final', 'HSI', 'PPI', 'composite_score',
                'ingredient_count', 'category_count', 
                'description_length', 'description_word_count'
            ]
        
        # Csak a létező oszlopokat skálázzuk
        columns_to_scale = [col for col in numerical_columns if col in df_scaled.columns]
        
        if columns_to_scale:
            if 'numerical' not in self.scalers:
                self.scalers['numerical'] = StandardScaler()
                scaled_values = self.scalers['numerical'].fit_transform(
                    df_scaled[columns_to_scale]
                )
            else:
                scaled_values = self.scalers['numerical'].transform(
                    df_scaled[columns_to_scale]
                )
            
            # Skálázott értékek visszahelyezése
            for i, col in enumerate(columns_to_scale):
                df_scaled[f'{col}_scaled'] = scaled_values[:, i]
        
        return df_scaled
    
    def create_user_profile_features(self, user_ratings: Dict[str, int], 
                                   df: pd.DataFrame) -> Dict[str, Any]:
        """
        Felhasználói profil feature-ök létrehozása
        
        Args:
            user_ratings: Felhasználói értékelések {recipe_id: rating}
            df: Receptek DataFrame
            
        Returns:
            User profile feature dictionary
        """
        profile = {
            'preferred_categories': [],
            'preferred_ingredients': [],
            'avg_sustainability_preference': 0.0,
            'avg_health_preference': 0.0,
            'rating_count': 0,
            'rating_distribution': Counter(),
            'preference_strength': 0.0
        }
        
        if not user_ratings:
            return profile
        
        # Releváns receptek (rating >= 4)
        liked_recipes = [recipe_id for recipe_id, rating in user_ratings.items() if rating >= 4]
        
        if not liked_recipes:
            return profile
        
        # Kedvelt receptek adatainak lekérdezése
        liked_df = df[df['id'].isin(liked_recipes)]
        
        if len(liked_df) == 0:
            return profile
        
        # Kategória preferenciák
        all_categories = []
        for categories_list in liked_df['categories_list']:
            if isinstance(categories_list, list):
                all_categories.extend(categories_list)
        
        category_counts = Counter(all_categories)
        profile['preferred_categories'] = [cat for cat, count in category_counts.most_common(5)]
        
        # Összetevő preferenciák
        all_ingredients = []
        for ingredients_list in liked_df['ingredients_list']:
            if isinstance(ingredients_list, list):
                all_ingredients.extend([ing.lower() for ing in ingredients_list])
        
        ingredient_counts = Counter(all_ingredients)
        profile['preferred_ingredients'] = [ing for ing, count in ingredient_counts.most_common(10)]
        
        # Fenntarthatósági és egészségességi preferenciák
        if 'composite_score' in liked_df.columns:
            profile['avg_sustainability_preference'] = liked_df['composite_score'].mean()
        
        if 'HSI' in liked_df.columns:
            profile['avg_health_preference'] = liked_df['HSI'].mean()
        
        # Rating statisztikák
        profile['rating_count'] = len(user_ratings)
        profile['rating_distribution'] = Counter(user_ratings.values())
        
        # Preferencia erősség (mennyire konzisztens a felhasználó)
        ratings_list = list(user_ratings.values())
        if len(ratings_list) > 1:
            profile['preference_strength'] = 1.0 - (np.std(ratings_list) / 2.0)  # Normalizált std
        else:
            profile['preference_strength'] = 0.5
        
        return profile

# =====================================
# Advanced Data Processing
# =====================================

class AdvancedProcessor:
    """Fejlett adatfeldolgozási módszerek"""
    
    def __init__(self):
        self.pca_models = {}
        self.clustering_models = {}
    
    def apply_dimensionality_reduction(self, 
                                     vectors: csr_matrix, 
                                     n_components: int = 100,
                                     method: str = 'pca') -> np.ndarray:
        """
        Dimenziócsökkentés alkalmazása
        
        Args:
            vectors: Bemeneti vektorok
            n_components: Komponensek száma
            method: Módszer ('pca', 'truncated_svd')
            
        Returns:
            Csökkentett dimenziójú vektorok
        """
        if method == 'pca':
            # Dense mátrixra konvertálás PCA-hoz
            dense_vectors = vectors.toarray()
            
            if method not in self.pca_models:
                self.pca_models[method] = PCA(n_components=min(n_components, dense_vectors.shape[1]))
                reduced_vectors = self.pca_models[method].fit_transform(dense_vectors)
            else:
                reduced_vectors = self.pca_models[method].transform(dense_vectors)
            
            logger.info(f"PCA reduced dimensions from {dense_vectors.shape[1]} to {reduced_vectors.shape[1]}")
            return reduced_vectors
        
        elif method == 'truncated_svd':
            from sklearn.decomposition import TruncatedSVD
            
            if method not in self.pca_models:
                self.pca_models[method] = TruncatedSVD(n_components=min(n_components, vectors.shape[1]))
                reduced_vectors = self.pca_models[method].fit_transform(vectors)
            else:
                reduced_vectors = self.pca_models[method].transform(vectors)
            
            logger.info(f"TruncatedSVD reduced dimensions from {vectors.shape[1]} to {reduced_vectors.shape[1]}")
            return reduced_vectors
        
        else:
            raise ValueError(f"Unknown dimensionality reduction method: {method}")
    
    def create_recipe_clusters(self, 
                              df: pd.DataFrame, 
                              vectors: csr_matrix,
                              n_clusters: int = 10,
                              method: str = 'kmeans') -> pd.DataFrame:
        """
        Recept klaszterek létrehozása
        
        Args:
            df: Receptek DataFrame
            vectors: TF-IDF vektorok
            n_clusters: Klaszterek száma
            method: Klaszterezési módszer
            
        Returns:
            DataFrame klaszter labelekkel
        """
        from sklearn.cluster import KMeans, DBSCAN
        
        df_clustered = df.copy()
        
        # Dimenziócsökkentés a klaszterezés előtt
        reduced_vectors = self.apply_dimensionality_reduction(vectors, n_components=50)
        
        if method == 'kmeans':
            if method not in self.clustering_models:
                self.clustering_models[method] = KMeans(
                    n_clusters=n_clusters, 
                    random_state=42,
                    n_init=10
                )
                cluster_labels = self.clustering_models[method].fit_predict(reduced_vectors)
            else:
                cluster_labels = self.clustering_models[method].predict(reduced_vectors)
            
        elif method == 'dbscan':
            if method not in self.clustering_models:
                self.clustering_models[method] = DBSCAN(
                    eps=0.5, 
                    min_samples=5
                )
                cluster_labels = self.clustering_models[method].fit_predict(reduced_vectors)
            else:
                # DBSCAN nem támogatja a predict-et, újra fit kell
                cluster_labels = self.clustering_models[method].fit_predict(reduced_vectors)
        
        else:
            raise ValueError(f"Unknown clustering method: {method}")
        
        df_clustered['cluster'] = cluster_labels
        
        # Klaszter statisztikák
        cluster_stats = df_clustered['cluster'].value_counts().to_dict()
        logger.info(f"Created {len(cluster_stats)} clusters with {method}: {cluster_stats}")
        
        return df_clustered
    
    def analyze_cluster_characteristics(self, 
                                      df_clustered: pd.DataFrame) -> Dict[str, Any]:
        """
        Klaszter jellemzők elemzése
        
        Args:
            df_clustered: Klaszterezett DataFrame
            
        Returns:
            Klaszter jellemzők dictionary
        """
        cluster_analysis = {}
        
        for cluster_id in df_clustered['cluster'].unique():
            if cluster_id == -1:  # DBSCAN noise
                continue
            
            cluster_data = df_clustered[df_clustered['cluster'] == cluster_id]
            
            characteristics = {
                'size': len(cluster_data),
                'avg_sustainability': cluster_data['composite_score'].mean() if 'composite_score' in cluster_data.columns else 0,
                'avg_health': cluster_data['HSI'].mean() if 'HSI' in cluster_data.columns else 0,
                'top_categories': [],
                'top_ingredients': []
            }
            
            # Top kategóriák
            all_categories = []
            for categories_list in cluster_data['categories_list']:
                if isinstance(categories_list, list):
                    all_categories.extend(categories_list)
            
            if all_categories:
                category_counts = Counter(all_categories)
                characteristics['top_categories'] = [cat for cat, count in category_counts.most_common(5)]
            
            # Top összetevők
            all_ingredients = []
            for ingredients_list in cluster_data['ingredients_list']:
                if isinstance(ingredients_list, list):
                    all_ingredients.extend(ingredients_list)
            
            if all_ingredients:
                ingredient_counts = Counter(all_ingredients)
                characteristics['top_ingredients'] = [ing for ing, count in ingredient_counts.most_common(5)]
            
            cluster_analysis[f'cluster_{cluster_id}'] = characteristics
        
        return cluster_analysis

# =====================================
# Text Processing Utilities
# =====================================

def preprocess_text_for_search(text: str) -> str:
    """
    Szöveg előfeldolgozása kereséshez
    
    Args:
        text: Előfeldolgozandó szöveg
        
    Returns:
        Előfeldolgozott szöveg
    """
    if not text or pd.isna(text):
        return ""
    
    # Unicode normalizálás
    text = unicodedata.normalize('NFKD', str(text))
    
    # Kisbetűsítés
    text = text.lower()
    
    # Központozás eltávolítása
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Extra whitespace eltávolítása
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Speciális karakterek eltávolítása
    text = re.sub(r'[^\w\s]', '', text)
    
    return text

def extract_keywords_from_text(text: str, 
                              min_length: int = 3,
                              max_keywords: int = 20) -> List[str]:
    """
    Kulcsszavak kinyerése szövegből
    
    Args:
        text: Szöveg
        min_length: Minimum szó hossz
        max_keywords: Maximum kulcsszavak száma
        
    Returns:
        Kulcsszavak listája
    """
    if not text:
        return []
    
    # Szöveg előfeldolgozása
    cleaned_text = preprocess_text_for_search(text)
    
    # Szavakra bontás
    words = cleaned_text.split()
    
    # Szűrés hossz alapján
    words = [word for word in words if len(word) >= min_length]
    
    # Gyakoriság számítása
    word_counts = Counter(words)
    
    # Top kulcsszavak
    keywords = [word for word, count in word_counts.most_common(max_keywords)]
    
    return keywords

def calculate_text_similarity_score(text1: str, text2: str) -> float:
    """
    Két szöveg hasonlóságának számítása
    
    Args:
        text1: Első szöveg
        text2: Második szöveg
        
    Returns:
        Hasonlósági pontszám (0.0 - 1.0)
    """
    if not text1 or not text2:
        return 0.0
    
    # Kulcsszavak kinyerése
    keywords1 = set(extract_keywords_from_text(text1))
    keywords2 = set(extract_keywords_from_text(text2))
    
    if not keywords1 or not keywords2:
        return 0.0
    
    # Jaccard hasonlóság
    intersection = len(keywords1.intersection(keywords2))
    union = len(keywords1.union(keywords2))
    
    jaccard_similarity = intersection / union if union > 0 else 0.0
    
    return jaccard_similarity

# =====================================
# Data Quality Assessment
# =====================================

def assess_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Adatminőség értékelése
    
    Args:
        df: Értékelendő DataFrame
        
    Returns:
        Adatminőségi jelentés
    """
    quality_report = {
        'overall_score': 0.0,
        'dimensions': {},
        'issues': [],
        'recommendations': []
    }
    
    # 1. Teljességi dimenzió
    completeness_scores = {}
    total_cells = len(df) * len(df.columns)
    missing_cells = df.isnull().sum().sum()
    
    completeness_scores['overall'] = 1.0 - (missing_cells / total_cells)
    
    # Kritikus oszlopok ellenőrzése
    critical_columns = ['id', 'name', 'ESI', 'HSI', 'PPI']
    for col in critical_columns:
        if col in df.columns:
            completeness_scores[col] = 1.0 - (df[col].isnull().sum() / len(df))
    
    quality_report['dimensions']['completeness'] = completeness_scores
    
    # 2. Egyediség dimenzió
    uniqueness_scores = {}
    
    if 'id' in df.columns:
        uniqueness_scores['id'] = len(df['id'].unique()) / len(df)
    
    if 'name' in df.columns:
        uniqueness_scores['name'] = len(df['name'].unique()) / len(df)
    
    quality_report['dimensions']['uniqueness'] = uniqueness_scores
    
    # 3. Konzisztencia dimenzió
    consistency_scores = {}
    
    # Numerikus tartományok ellenőrzése
    numeric_columns = ['ESI', 'HSI', 'PPI', 'composite_score']
    for col in numeric_columns:
        if col in df.columns:
            values = df[col].dropna()
            if len(values) > 0:
                # Elvárt tartomány: 0-100
                in_range = ((values >= 0) & (values <= 100)).sum()
                consistency_scores[col] = in_range / len(values)
    
    quality_report['dimensions']['consistency'] = consistency_scores
    
    # 4. Pontosság dimenzió (egyszerűsített)
    accuracy_scores = {}
    
    # Szöveges mezők hossz ellenőrzése
    if 'name' in df.columns:
        names = df['name'].dropna()
        reasonable_length = ((names.str.len() >= 2) & (names.str.len() <= 100)).sum()
        accuracy_scores['name_length'] = reasonable_length / len(names) if len(names) > 0 else 0
    
    quality_report['dimensions']['accuracy'] = accuracy_scores
    
    # 5. Összesített pontszám számítása
    all_scores = []
    for dimension, scores in quality_report['dimensions'].items():
        if isinstance(scores, dict):
            all_scores.extend(scores.values())
        else:
            all_scores.append(scores)
    
    quality_report['overall_score'] = np.mean(all_scores) if all_scores else 0.0
    
    # 6. Problémák és ajánlások
    if completeness_scores['overall'] < 0.9:
        quality_report['issues'].append("Magas hiányzó adat arány")
        quality_report['recommendations'].append("Hiányzó értékek pótlása szükséges")
    
    if 'id' in uniqueness_scores and uniqueness_scores['id'] < 1.0:
        quality_report['issues'].append("Duplikált ID-k találhatók")
        quality_report['recommendations'].append("ID duplikátumok eltávolítása")
    
    for col, score in consistency_scores.items():
        if score < 0.95:
            quality_report['issues'].append(f"{col} oszlopban tartományon kívüli értékek")
            quality_report['recommendations'].append(f"{col} értékek validálása és tisztítása")
    
    return quality_report

# =====================================
# Data Export and Serialization
# =====================================

def export_processed_data(df: pd.DataFrame, 
                         vectors: Dict[str, csr_matrix],
                         output_dir: str) -> Dict[str, str]:
    """
    Feldolgozott adatok exportálása
    
    Args:
        df: Feldolgozott DataFrame
        vectors: TF-IDF vektorok
        output_dir: Kimeneti könyvtár
        
    Returns:
        Exportált fájlok listája
    """
    from scipy.sparse import save_npz
    import pickle
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    exported_files = {}
    
    try:
        # 1. DataFrame exportálása
        csv_path = output_path / 'processed_recipes.csv'
        df.to_csv(csv_path, index=False, encoding='utf-8')
        exported_files['dataframe'] = str(csv_path)
        
        # 2. JSON export (kisebb fájlméret érdekében csak főbb oszlopok)
        json_columns = ['id', 'name', 'description', 'ESI_final', 'HSI', 'PPI', 'composite_score']
        json_data = df[json_columns].to_dict('records')
        
        json_path = output_path / 'processed_recipes.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        exported_files['json'] = str(json_path)
        
        # 3. TF-IDF vektorok exportálása
        vectors_dir = output_path / 'vectors'
        vectors_dir.mkdir(exist_ok=True)
        
        for vector_name, vector_matrix in vectors.items():
            vector_path = vectors_dir / f'{vector_name}_vectors.npz'
            save_npz(vector_path, vector_matrix)
            exported_files[f'vectors_{vector_name}'] = str(vector_path)
        
        # 4. Metaadatok exportálása
        metadata = {
            'export_timestamp': pd.Timestamp.now().isoformat(),
            'total_recipes': len(df),
            'feature_columns': list(df.columns),
            'vector_dimensions': {name: matrix.shape for name, matrix in vectors.items()},
            'data_quality_score': assess_data_quality(df)['overall_score']
        }
        
        metadata_path = output_path / 'metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        exported_files['metadata'] = str(metadata_path)
        
        logger.info(f"Data exported successfully to {output_dir}")
        
    except Exception as e:
        logger.error(f"Data export failed: {e}")
        raise
    
    return exported_files

# =====================================
# Main Processing Pipeline
# =====================================

def create_processing_pipeline(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Teljes adatfeldolgozási pipeline létrehozása
    
    Args:
        config: Konfigurációs paraméterek
        
    Returns:
        Pipeline komponensek dictionary
    """
    pipeline = {
        'data_processor': DataProcessor(config),
        'similarity_calculator': SimilarityCalculator(config),
        'feature_engineer': FeatureEngineer(),
        'advanced_processor': AdvancedProcessor()
    }
    
    return pipeline

def run_full_processing_pipeline(file_paths: List[str],
                                config: Dict[str, Any] = None,
                                output_dir: str = None) -> Dict[str, Any]:
    """
    Teljes adatfeldolgozási pipeline futtatása
    
    Args:
        file_paths: Bemeneti fájlok
        config: Konfiguráció
        output_dir: Kimeneti könyvtár
        
    Returns:
        Feldolgozási eredmények
    """
    logger.info("Starting full data processing pipeline")
    
    # Pipeline létrehozása
    pipeline = create_processing_pipeline(config)
    
    # 1. Adatok betöltése
    df_raw = pipeline['data_processor'].load_json_data(file_paths)
    if df_raw is None:
        raise ValueError("Failed to load data")
    
    # 2. Adatok validálása
    validation_results = pipeline['data_processor'].validate_data_structure(df_raw)
    if not validation_results['is_valid']:
        logger.warning(f"Data validation issues: {validation_results['issues']}")
    
    # 3. Adatok tisztítása és normalizálása
    df_clean = pipeline['data_processor'].clean_and_normalize_data(df_raw)
    
    # 4. Feature engineering
    df_features = pipeline['feature_engineer'].create_numerical_features(df_clean)
    df_encoded = pipeline['feature_engineer'].encode_categorical_features(df_features)
    df_scaled = pipeline['feature_engineer'].scale_numerical_features(df_encoded)
    
    # 5. TF-IDF vektorok létrehozása
    vectors = pipeline['similarity_calculator'].create_content_vectors(df_scaled)
    
    # 6. Klaszterezés (opcionális)
    if config and config.get('enable_clustering', False):
        df_clustered = pipeline['advanced_processor'].create_recipe_clusters(
            df_scaled, vectors['combined']
        )
        cluster_analysis = pipeline['advanced_processor'].analyze_cluster_characteristics(df_clustered)
    else:
        df_clustered = df_scaled
        cluster_analysis = {}
    
    # 7. Adatminőség értékelése
    quality_report = assess_data_quality(df_clustered)
    
    # 8. Export (ha megadva)
    exported_files = {}
    if output_dir:
        exported_files = export_processed_data(df_clustered, vectors, output_dir)
    
    # Eredmények összesítése
    results = {
        'processed_dataframe': df_clustered,
        'vectors': vectors,
        'pipeline_components': pipeline,
        'validation_results': validation_results,
        'quality_report': quality_report,
        'cluster_analysis': cluster_analysis,
        'exported_files': exported_files,
        'statistics': {
            'original_rows': len(df_raw),
            'processed_rows': len(df_clustered),
            'features_created': len(df_clustered.columns) - len(df_raw.columns),
            'vector_dimensions': {name: matrix.shape for name, matrix in vectors.items()}
        }
    }
    
    logger.info("Data processing pipeline completed successfully")
    
    return results

# =====================================
# Export Functions
# =====================================

__all__ = [
    # Main classes
    'DataProcessor', 'SimilarityCalculator', 'FeatureEngineer', 'AdvancedProcessor',
    
    # Text processing
    'preprocess_text_for_search', 'extract_keywords_from_text', 'calculate_text_similarity_score',
    
    # Data quality
    'assess_data_quality',
    
    # Export functions
    'export_processed_data',
    
    # Pipeline functions
    'create_processing_pipeline', 'run_full_processing_pipeline'
]
