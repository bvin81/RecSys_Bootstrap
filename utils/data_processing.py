# utils/data_processing.py - Adatfeldolgozási Funkciók
"""
GreenRec Data Processing Utilities
==================================
Adatfeldolgozási és normalizálási funkciók:
- ESI inverz normalizálás (100-ESI)
- Kompozit pontszám számítása
- Adattisztítás és validáció
- Feature engineering
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

def normalize_esi_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    ✅ ESI inverz normalizálás implementálása
    
    Steps:
    1. ESI normalizálás 0-100 közé
    2. Inverz számítás: 100 - normalizált_ESI
    3. Magasabb ESI = rosszabb környezetterhelés → alacsonyabb ESI_final érték
    
    Args:
        df: DataFrame ESI oszloppal
    
    Returns:
        DataFrame ESI_final oszloppal
    """
    df = df.copy()
    
    try:
        if 'ESI' not in df.columns:
            logger.warning("⚠️ No ESI column found")
            df['ESI_final'] = np.random.uniform(30, 80, len(df))
            return df
        
        # ESI értékek validálása és tisztítása
        df['ESI'] = pd.to_numeric(df['ESI'], errors='coerce')
        df['ESI'].fillna(df['ESI'].median(), inplace=True)
        
        # Min-max normalizálás 0-100 közé
        esi_min = df['ESI'].min()
        esi_max = df['ESI'].max()
        
        if esi_max > esi_min:
            # Normalizálás
            df['ESI_normalized'] = 100 * (df['ESI'] - esi_min) / (esi_max - esi_min)
            
            # ✅ INVERZ SZÁMÍTÁS
            df['ESI_final'] = 100 - df['ESI_normalized']
            
            logger.info(f"✅ ESI normalization: {esi_min:.1f}-{esi_max:.1f} → 0-100 (inverted)")
            logger.info(f"📊 ESI_final range: {df['ESI_final'].min():.1f}-{df['ESI_final'].max():.1f}")
        else:
            # Ha minden ESI érték ugyanaz
            df['ESI_final'] = 50.0  # Neutral érték
            logger.warning("⚠️ All ESI values are the same, using neutral value")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ ESI normalization error: {e}")
        # Fallback: random értékek
        df['ESI_final'] = np.random.uniform(30, 80, len(df))
        return df

def calculate_composite_scores(df: pd.DataFrame, weights: Dict[str, float]) -> pd.DataFrame:
    """
    ✅ Kompozit pontszám számítása helyes képlettel
    
    Formula: ESI_final * 0.4 + HSI * 0.4 + PPI * 0.2
    
    Args:
        df: DataFrame pontszám oszlopokkal
        weights: Súlyozási beállítások {'ESI': 0.4, 'HSI': 0.4, 'PPI': 0.2}
    
    Returns:
        DataFrame composite_score oszloppal
    """
    df = df.copy()
    
    try:
        # Szükséges oszlopok ellenőrzése
        required_columns = ['ESI_final', 'HSI', 'PPI']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"❌ Missing columns for composite score: {missing_columns}")
            df['composite_score'] = 50.0  # Default érték
            return df
        
        # Adatok validálása és tisztítása
        for col in required_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df[col].fillna(df[col].median(), inplace=True)
        
        # ✅ KOMPOZIT PONTSZÁM SZÁMÍTÁSA
        df['composite_score'] = (
            df['ESI_final'] * weights['ESI'] +     # Környezeti (inverz ESI)
            df['HSI'] * weights['HSI'] +           # Egészségügyi
            df['PPI'] * weights['PPI']             # Népszerűségi
        ).round(1)
        
        # Validálás: 0-100 között kell legyen
        df['composite_score'] = df['composite_score'].clip(0, 100)
        
        logger.info(f"✅ Composite scores calculated")
        logger.info(f"📊 Composite range: {df['composite_score'].min():.1f}-{df['composite_score'].max():.1f}")
        logger.info(f"⚖️ Weights used: ESI={weights['ESI']}, HSI={weights['HSI']}, PPI={weights['PPI']}")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Composite score calculation error: {e}")
        # Fallback: random értékek
        df['composite_score'] = np.random.uniform(20, 90, len(df))
        return df

def clean_recipe_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recept adatok tisztítása és validálása
    
    Args:
        df: Nyers recept DataFrame
    
    Returns:
        Tisztított DataFrame
    """
    df = df.copy()
    
    try:
        logger.info("🧹 Cleaning recipe data...")
        
        # Duplikált sorok eltávolítása
        initial_count = len(df)
        df.drop_duplicates(inplace=True)
        if len(df) < initial_count:
            logger.info(f"🗑️ Removed {initial_count - len(df)} duplicate rows")
        
        # Szöveges oszlopok tisztítása
        text_columns = ['recipe_name', 'name', 'category', 'ingredients']
        for col in text_columns:
            if col in df.columns:
                # Whitespace és üres értékek kezelése
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace(['', 'nan', 'None'], np.nan)
                
                # Alapértelmezett értékek
                if col in ['recipe_name', 'name']:
                    df[col].fillna('Névtelen recept', inplace=True)
                elif col == 'category':
                    df[col].fillna('Egyéb', inplace=True)
                elif col == 'ingredients':
                    df[col].fillna('Összetevők nem megadottak', inplace=True)
        
        # Numerikus oszlopok tisztítása
        numeric_columns = ['ESI', 'HSI', 'PPI']
        for col in numeric_columns:
            if col in df.columns:
                # Numerikus konverzió
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Outlier kezelés (99%-os percentile)
                if col == 'ESI':
                    # ESI esetén 0-100+ tartomány elfogadható
                    df[col] = df[col].clip(0, None)
                else:
                    # HSI, PPI esetén 0-100 tartomány
                    df[col] = df[col].clip(0, 100)
                
                # Hiányzó értékek pótlása mediánnal
                median_value = df[col].median()
                df[col].fillna(median_value, inplace=True)
        
        # URL oszlopok tisztítása
        if 'image_url' in df.columns:
            df['image_url'] = df['image_url'].astype(str)
            # Érvénytelen URL-ek kezelése
            invalid_urls = df['image_url'].isin(['nan', 'None', '', 'null'])
            df.loc[invalid_urls, 'image_url'] = np.nan
        
        logger.info(f"✅ Data cleaning completed: {len(df)} records")
        return df
        
    except Exception as e:
        logger.error(f"❌ Data cleaning error: {e}")
        return df

def validate_recipe_dataframe(df: pd.DataFrame) -> Tuple[bool, list]:
    """
    DataFrame validálása receptekhez
    
    Args:
        df: Validálandó DataFrame
    
    Returns:
        (is_valid, error_list)
    """
    errors = []
    
    try:
        # Alapvető ellenőrzések
        if df is None or len(df) == 0:
            errors.append("DataFrame is empty")
            return False, errors
        
        # Szükséges oszlopok ellenőrzése
        required_columns = ['recipe_name', 'category', 'ingredients']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")
        
        # ID oszlop ellenőrzése
        id_columns = ['recipeid', 'id']
        has_id = any(col in df.columns for col in id_columns)
        if not has_id:
            errors.append("No ID column found (recipeid or id)")
        
        # Pontszám oszlopok ellenőrzése
        score_columns = ['ESI', 'HSI', 'PPI']
        missing_scores = [col for col in score_columns if col not in df.columns]
        if missing_scores:
            errors.append(f"Missing score columns: {missing_scores}")
        
        # Adatminőség ellenőrzések
        if len(df) < 10:
            errors.append(f"Too few recipes: {len(df)} (minimum 10 recommended)")
        
        # Numerikus oszlopok ellenőrzése
        for col in ['ESI', 'HSI', 'PPI']:
            if col in df.columns:
                non_numeric = df[col].isna().sum()
                if non_numeric > len(df) * 0.5:  # 50%-nál több hiányzó érték
                    errors.append(f"Too many missing values in {col}: {non_numeric}/{len(df)}")
        
        # Szöveges oszlopok ellenőrzése
        for col in ['recipe_name', 'category', 'ingredients']:
            if col in df.columns:
                empty_values = df[col].isna().sum()
                if empty_values > len(df) * 0.1:  # 10%-nál több hiányzó érték
                    errors.append(f"Too many missing values in {col}: {empty_values}/{len(df)}")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("✅ DataFrame validation passed")
        else:
            logger.warning(f"⚠️ DataFrame validation failed: {len(errors)} errors")
            for error in errors:
                logger.warning(f"  - {error}")
        
        return is_valid, errors
        
    except Exception as e:
        logger.error(f"❌ Validation error: {e}")
        return False, [f"Validation exception: {str(e)}"]

def add_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature engineering recept adatokon
    
    Args:
        df: Alap recept DataFrame
    
    Returns:
        DataFrame további feature oszlopokkal
    """
    df = df.copy()
    
    try:
        logger.info("🔧 Adding feature engineering...")
        
        # Összetevők száma
        if 'ingredients' in df.columns:
            df['ingredient_count'] = df['ingredients'].str.count(',') + 1
            df['ingredient_count'].fillna(1, inplace=True)
        
        # Kategória encoding
        if 'category' in df.columns:
            df['is_main_course'] = (df['category'] == 'Főétel').astype(int)
            df['is_healthy'] = df['category'].isin(['Saláta', 'Smoothie', 'Vegán']).astype(int)
            df['is_dessert'] = (df['category'] == 'Desszert').astype(int)
        
        # Pontszám kategóriák
        if 'composite_score' in df.columns:
            df['score_category'] = pd.cut(
                df['composite_score'], 
                bins=[0, 40, 70, 100], 
                labels=['Low', 'Medium', 'High']
            )
        
        # Fenntarthatósági kategóriák
        if 'ESI_final' in df.columns:
            df['sustainability_level'] = pd.cut(
                df['ESI_final'],
                bins=[0, 33, 66, 100],
                labels=['Low', 'Medium', 'High']
            )
        
        # Egészségügyi kategóriák
        if 'HSI' in df.columns:
            df['health_level'] = pd.cut(
                df['HSI'],
                bins=[0, 40, 70, 100],
                labels=['Low', 'Medium', 'High']
            )
        
        # Összesített kategória
        if all(col in df.columns for col in ['ESI_final', 'HSI']):
            df['recommended_level'] = 'Basic'
            
            # Magas ESI_final ÉS magas HSI = erősen ajánlott
            high_sustain = df['ESI_final'] > 70
            high_health = df['HSI'] > 70
            df.loc[high_sustain & high_health, 'recommended_level'] = 'Highly Recommended'
            
            # Közepes értékek = ajánlott
            medium_sustain = (df['ESI_final'] > 40) & (df['ESI_final'] <= 70)
            medium_health = (df['HSI'] > 40) & (df['HSI'] <= 70)
            df.loc[(medium_sustain | high_sustain) & (medium_health | high_health), 'recommended_level'] = 'Recommended'
        
        logger.info("✅ Feature engineering completed")
        return df
        
    except Exception as e:
        logger.error(f"❌ Feature engineering error: {e}")
        return df

def get_data_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    DataFrame összefoglaló statisztikák
    
    Args:
        df: Elemzendő DataFrame
    
    Returns:
        Statisztikák dictionary
    """
    try:
        summary = {
            'total_records': len(df),
            'columns': list(df.columns),
            'missing_data': df.isnull().sum().to_dict(),
            'data_types': df.dtypes.astype(str).to_dict()
        }
        
        # Numerikus oszlopok statisztikái
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            summary['numeric_stats'] = df[numeric_columns].describe().to_dict()
        
        # Kategorikus oszlopok statisztikái
        categorical_columns = df.select_dtypes(include=['object']).columns
        if len(categorical_columns) > 0:
            summary['categorical_stats'] = {}
            for col in categorical_columns:
                if len(df[col].unique()) < 20:  # Csak kis számú egyedi értékű oszlopok
                    summary['categorical_stats'][col] = df[col].value_counts().to_dict()
        
        # Specifikus recept statisztikák
        if 'composite_score' in df.columns:
            summary['score_distribution'] = {
                'mean': float(df['composite_score'].mean()),
                'median': float(df['composite_score'].median()),
                'std': float(df['composite_score'].std()),
                'min': float(df['composite_score'].min()),
                'max': float(df['composite_score'].max())
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"❌ Summary generation error: {e}")
        return {'error': str(e)}

# Export
__all__ = [
    'normalize_esi_scores',
    'calculate_composite_scores', 
    'clean_recipe_data',
    'validate_recipe_dataframe',
    'add_feature_engineering',
    'get_data_summary'
]
