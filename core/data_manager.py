# core/data_manager.py
"""
GreenRec Data Manager
====================
Adatkezelési osztály, amely felelős:
- JSON adatok betöltéséért és validálásáért
- PostgreSQL kapcsolat kezeléséért
- Adatok előkészítéséért és normalizálásáért
"""

import json
import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
import os
from config import current_config

logger = logging.getLogger(__name__)

class DataManager:
    """Adatkezelő szolgáltatás"""
    
    def __init__(self):
        self.recipes_df: Optional[pd.DataFrame] = None
        self.is_loaded = False
    
    def load_recipe_data(self) -> pd.DataFrame:
        """
        Recept adatok betöltése JSON fájlból vagy demo adatok generálása
        
        Returns:
            pd.DataFrame: Betöltött és előkészített recept adatok
        """
        if self.is_loaded and self.recipes_df is not None:
            return self.recipes_df
        
        try:
            # Elsődleges adatfájl betöltése
            if os.path.exists(current_config.RECIPE_DATA_FILE):
                logger.info(f"Adatok betöltése: {current_config.RECIPE_DATA_FILE}")
                self.recipes_df = self._load_from_json(current_config.RECIPE_DATA_FILE)
            
            # Fallback fájl próbálkozás
            elif os.path.exists(current_config.BACKUP_DATA_FILE):
                logger.info(f"Fallback adatok betöltése: {current_config.BACKUP_DATA_FILE}")
                self.recipes_df = self._load_from_json(current_config.BACKUP_DATA_FILE)
            
            # Demo adatok generálása ha nincs fájl
            else:
                logger.warning("Adatfájl nem található, demo adatok generálása...")
                self.recipes_df = self._generate_demo_data()
            
            # Adatok előkészítése és normalizálása
            self.recipes_df = self._prepare_data(self.recipes_df)
            self.is_loaded = True
            
            logger.info(f"✅ {len(self.recipes_df)} recept sikeresen betöltve")
            return self.recipes_df
            
        except Exception as e:
            logger.error(f"❌ Adatbetöltési hiba: {e}")
            # Fallback demo adatokra
            self.recipes_df = self._generate_demo_data()
            self.recipes_df = self._prepare_data(self.recipes_df)
            self.is_loaded = True
            return self.recipes_df
    
    def _load_from_json(self, filepath: str) -> pd.DataFrame:
        """JSON fájl betöltése és DataFrame-mé alakítása"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Lista vagy dict kezelése
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            if 'recipes' in data:
                return pd.DataFrame(data['recipes'])
            else:
                return pd.DataFrame([data])
        else:
            raise ValueError(f"Érvénytelen JSON struktúra: {type(data)}")
    
    def _generate_demo_data(self) -> pd.DataFrame:
        """Demo receptadatok generálása tesztelési célokra"""
        np.random.seed(42)  # Reprodukálható eredményekért
        
        # Magyar ételnevek
        dish_names = [
            "Gulyásleves", "Schnitzel", "Lecsó", "Pörkölt", "Halászlé",
            "Rakott Krumpli", "Főzelék", "Túrógombóc", "Lángos", "Kürtőskalács",
            "Paprikáskrumpli", "Töltött Káposzta", "Marhapörkölt", "Csirkepaprikás",
            "Húsgombóc", "Rántott Szelet", "Körözött", "Zsíroskenyér",
            "Babgulyás", "Palócleves", "Jókai Bableves", "Újházy Tyúkhúsleves",
            "Gödöllői Töltött Krumpli", "Erdélyi Rakottkrumpli", "Borjúpörkölt"
        ]
        
        # Összetevők kategóriák
        ingredients_options = [
            "marhahús, hagyma, paprika, krumpli, paradicsom",
            "csirkemell, rizs, zöldség, fűszerek",
            "tészta, sajt, tejszín, sonka, bors",
            "hal, krumpli, hagyma, paprika, tejföl",
            "sertéshús, káposzta, rizs, tojás, fűszerek",
            "zöldségek, olívaolaj, fokhagyma, gyógynövények",
            "tojás, liszt, tej, vaj, cukor",
            "saláta, paradicsom, uborka, olaj, ecet"
        ]
        
        n_recipes = 50
        
        demo_data = {
            'recipe_id': range(1, n_recipes + 1),
            'name': [f"{np.random.choice(dish_names)} #{i}" for i in range(1, n_recipes + 1)],
            'ingredients': [np.random.choice(ingredients_options) for _ in range(n_recipes)],
            'environmental_impact': np.random.randint(20, 80, n_recipes),  # ESI (alacsonyabb = jobb)
            'health_score': np.random.randint(30, 90, n_recipes),  # HSI (magasabb = jobb)
            'popularity': np.random.randint(40, 95, n_recipes),  # PPI (magasabb = jobb)
            'category': np.random.choice(['Leves', 'Főétel', 'Saláta', 'Desszert', 'Snack'], n_recipes),
            'preparation_time': np.random.randint(15, 120, n_recipes),  # percek
            'difficulty': np.random.choice(['Könnyű', 'Közepes', 'Nehéz'], n_recipes)
        }
        
        return pd.DataFrame(demo_data)
    
    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adatok előkészítése és normalizálása
        
        Args:
            df: Nyers recept adatok
            
        Returns:
            pd.DataFrame: Előkészített adatok
        """
        df = df.copy()
        
        # ✅ GREENREC_DATASET.JSON MEZŐK MAPPELÉSE
        # JSON mezők → Template mezők átnevezése
        field_mapping = {
            'recipeid': 'recipe_id',      # recipeid → recipe_id
            'title': 'name',              # title → name
            'images': 'image_url',        # images → image_url
            # ESI, HSI, PPI már jó néven vannak a JSON-ban
        }
        
        # Mezők átnevezése ha léteznek
        for old_name, new_name in field_mapping.items():
            if old_name in df.columns and new_name not in df.columns:
                df = df.rename(columns={old_name: new_name})
                logger.info(f"✅ Mező átnevezve: {old_name} → {new_name}")
        
        # Kötelező oszlopok ellenőrzése és kiegészítése
        required_columns = {
            'recipe_id': list(range(1, len(df) + 1)),  # ← list() hozzáadása
            'name': [f"Recept #{i}" for i in range(1, len(df) + 1)],
            'ingredients': ['alapösszetevők'] * len(df),
            'ESI': [50] * len(df),  # Environmental Score Index
            'HSI': [60] * len(df),  # Health Score Index  
            'PPI': [70] * len(df),  # Popularity Index
            'category': ['Egyéb'] * len(df),
            'image_url': [None] * len(df)
        }
        
        # Hiányzó oszlopok hozzáadása
        for col, default_values in required_columns.items():
            if col not in df.columns:
                if isinstance(default_values, (list, np.ndarray)):
                    df[col] = default_values
                else:
                    df[col] = default_values
                logger.warning(f"⚠️ Hiányzó oszlop kiegészítve: {col}")
        
        # ✅ ADATTÍPUSOK JAVÍTÁSA
        # Recipe ID biztosan integer legyen
        if 'recipe_id' in df.columns:
            df['recipe_id'] = pd.to_numeric(df['recipe_id'], errors='coerce').fillna(range(1, len(df) + 1)).astype(int)
        
        # Numerikus oszlopok
        for col in ['ESI', 'HSI', 'PPI']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(50.0)
        
        # String oszlopok tisztítása
        for col in ['name', 'ingredients', 'category']:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna("N/A")
        
        # ✅ ESI INVERZ SZÁMÍTÁS (alacsonyabb ESI = jobb környezeti hatás)
        if 'ESI' in df.columns:
            # ESI normalizálása 0-100 skálára
            esi_min, esi_max = df['ESI'].min(), df['ESI'].max()
            if esi_max > esi_min:
                df['esi_normalized'] = 100 * (df['ESI'] - esi_min) / (esi_max - esi_min)
            else:
                df['esi_normalized'] = [50] * len(df)
            
            # ESI inverz: 100 - normalized (magasabb érték = jobb környezeti hatás)
            df['esi_inverted'] = 100 - df['esi_normalized']
            
            logger.info(f"✅ ESI feldolgozva: {esi_min:.1f}-{esi_max:.1f} → inverted")
        
        # ✅ HSI ÉS PPI NORMALIZÁLÁS
        for col, new_col in [('HSI', 'health_score'), ('PPI', 'popularity')]:
            if col in df.columns:
                col_min, col_max = df[col].min(), df[col].max()
                if col_max > col_min:
                    df[f'{col.lower()}_normalized'] = 100 * (df[col] - col_min) / (col_max - col_min)
                else:
                    df[f'{col.lower()}_normalized'] = [50] * len(df)
                
                # Eredeti név megtartása kompatibilitásért
                df[new_col] = df[col]
                logger.info(f"✅ {col} normalizálva")
        
        # ✅ KOMPOZIT PONTSZÁM SZÁMÍTÁSA
        if all(col in df.columns for col in ['esi_inverted', 'HSI', 'PPI']):
            # Súlyozott átlag a config alapján
            df['composite_score'] = (
                df['esi_inverted'] * current_config.ESI_WEIGHT +
                df.get('hsi_normalized', df['HSI']) * current_config.HSI_WEIGHT +
                df.get('ppi_normalized', df['PPI']) * current_config.PPI_WEIGHT
            )
            logger.info("✅ Kompozit pontszám kiszámítva")
        
        # ✅ KÉPEK URL VALIDÁLÁSA
        if 'image_url' in df.columns:
            # Csak érvényes HTTP URL-ek megtartása
            df['image_url'] = df['image_url'].apply(
                lambda x: x if (isinstance(x, str) and x.startswith('http')) else None
            )
            
            # Placeholder képek hiányzó esetekre
            missing_images = df['image_url'].isna().sum()
            if missing_images > 0:
                logger.info(f"⚠️ {missing_images} hiányzó kép URL")
        
        # ✅ ÖSSZETEVŐK SZÖVEG ELŐKÉSZÍTÉSE TF-IDF-hez
        if 'ingredients' in df.columns:
            df['ingredients_text'] = df['ingredients'].astype(str).str.lower()
        
        # ✅ KATEGÓRIA TISZTÍTÁS
        if 'category' in df.columns:
            # Üres kategóriák javítása
            df['category'] = df['category'].fillna('Egyéb')
            df['category'] = df['category'].replace('', 'Egyéb')
        
        logger.info(f"✅ Adatok előkészítve: {len(df)} recept, {len(df.columns)} oszlop")
        logger.info(f"📊 Oszlopok: {list(df.columns)}")
        
        return df
    
    def get_recipe_by_id(self, recipe_id: int) -> Optional[Dict]:
        """
        Recept lekérdezése ID alapján
        
        Args:
            recipe_id: Recept azonosító
            
        Returns:
            Dict vagy None: Recept adatok
        """
        if self.recipes_df is None:
            self.load_recipe_data()
        
        recipe = self.recipes_df[self.recipes_df['recipe_id'] == recipe_id]
        if len(recipe) > 0:
            return recipe.iloc[0].to_dict()
        return None
    
    def get_recipes_by_category(self, category: str) -> pd.DataFrame:
        """Receptek lekérdezése kategória alapján"""
        if self.recipes_df is None:
            self.load_recipe_data()
        
        if 'category' in self.recipes_df.columns:
            return self.recipes_df[self.recipes_df['category'] == category]
        return pd.DataFrame()
    
    def get_data_statistics(self) -> Dict:
        """Adatok statisztikáinak lekérdezése debug célokra"""
        if self.recipes_df is None:
            self.load_recipe_data()
        
        return {
            'total_recipes': len(self.recipes_df),
            'esi_range': (self.recipes_df['esi_inverted'].min(), self.recipes_df['esi_inverted'].max()),
            'health_range': (self.recipes_df['health_score'].min(), self.recipes_df['health_score'].max()),
            'composite_range': (self.recipes_df['composite_score'].min(), self.recipes_df['composite_score'].max()),
            'categories': list(self.recipes_df.get('category', pd.Series()).unique()),
            'avg_composite_score': self.recipes_df['composite_score'].mean()
        }

# Globális data manager instance
data_manager = DataManager()

