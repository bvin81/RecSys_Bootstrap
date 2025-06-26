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
        
        # Kötelező oszlopok ellenőrzése és kiegészítése
        required_columns = {
            'recipe_id': range(1, len(df) + 1),
            'name': [f"Recept #{i}" for i in range(1, len(df) + 1)],
            'ingredients': ['alapösszetevők'] * len(df),
            'environmental_impact': [50] * len(df),
            'health_score': [60] * len(df),
            'popularity': [70] * len(df)
        }
        
        for col, default_values in required_columns.items():
            if col not in df.columns:
                df[col] = default_values
                logger.warning(f"Hiányzó oszlop kiegészítve: {col}")
        
        # ESI inverz normalizálás (alacsonyabb ESI = jobb környezeti hatás)
        df['esi_raw'] = df['environmental_impact']
        df['esi_inverted'] = 100 - df['environmental_impact']  # Inverz: magasabb = jobb
        
        # Normalizálás 0-100 skálára
        for col in ['esi_inverted', 'health_score', 'popularity']:
            if col in df.columns:
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val > min_val:
                    df[f'{col}_normalized'] = 100 * (df[col] - min_val) / (max_val - min_val)
                else:
                    df[f'{col}_normalized'] = [50] * len(df)
        
        # Kompozit pontszám számítása (ESI×0.4 + HSI×0.4 + PPI×0.2)
        df['composite_score'] = (
            df.get('esi_inverted_normalized', df['esi_inverted']) * current_config.ESI_WEIGHT +
            df.get('health_score_normalized', df['health_score']) * current_config.HSI_WEIGHT +
            df.get('popularity_normalized', df['popularity']) * current_config.PPI_WEIGHT
        )
        
        # Placeholder képek hozzáadása
        if 'image_url' not in df.columns:
            df['image_url'] = [
                f"https://images.unsplash.com/photo-1565299624946-b28f40a0ca4b?w=300&h=200&fit=crop&q=80&sig={i}"
                for i in range(len(df))
            ]
        
        # Összetevők szöveg előkészítése TF-IDF-hez
        df['ingredients_text'] = df['ingredients'].astype(str).str.lower()
        
        logger.info("✅ Adatok előkészítése befejezve")
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

