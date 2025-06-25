# services/data_service.py
"""
GreenRec Data Service
====================

Adatkezelési szolgáltatás, amely felelős:
- JSON adatok betöltéséért és validálásáért
- Adatok előkészítéséért és tisztításáért
- Recommendation engine inicializálásáért
- Adatok integritásának biztosításáért

Támogatott formátumok: JSON (greenrec_dataset.json)
Adatvalidáció: Kötelező mezők ellenőrzése
Hibakezelés: Graceful fallback megoldások
"""

import json
import pandas as pd
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import random

from models.recommendation import initialize_recommendation_engine


class DataService:
    """
    Adatkezelési szolgáltatás osztály
    
    Felelősségek:
    - JSON fájlok betöltése és validálása
    - DataFrame létrehozása és tisztítása
    - Adatok előkészítése ML algoritmushoz
    - Recommendation engine inicializálása
    """
    
    def __init__(self):
        """DataService inicializálása"""
        self.recipes_df = None
        self.is_initialized = False
        self.initialization_logs = []
        self.data_stats = {}
        
    def initialize_system(self) -> bool:
        """
        Teljes rendszer inicializálása
        
        Returns:
            bool: Sikeres inicializálás
        """
        try:
            self._log("🔄 GreenRec rendszer inicializálása...")
            
            # 1. JSON fájl betöltése
            json_data = self._load_json_data()
            if not json_data:
                return False
            
            # 2. DataFrame létrehozása
            self.recipes_df = self._create_dataframe(json_data)
            if self.recipes_df is None:
                return False
            
            # 3. Adatok validálása és tisztítása
            self._validate_and_clean_data()
            
            # 4. Statisztikák generálása
            self._generate_data_statistics()
            
            # 5. Recommendation engine inicializálása
            engine_success = initialize_recommendation_engine(self.recipes_df)
            if not engine_success:
                self._log("❌ Recommendation engine inicializálása sikertelen")
                return False
            
            self.is_initialized = True
            self._log(f"✅ Rendszer sikeresen inicializálva: {len(self.recipes_df)} recept")
            
            return True
            
        except Exception as e:
            self._log(f"❌ Kritikus inicializálási hiba: {e}")
            return False
    
    def _load_json_data(self) -> Optional[Dict]:
        """
        JSON adatok betöltése fájlból
        
        Támogatott fájlnevek prioritási sorrendben:
        1. greenrec_dataset.json
        2. data.json  
        3. recipes.json
        
        Returns:
            Optional[Dict]: Betöltött JSON adatok vagy None
        """
        possible_files = ['greenrec_dataset.json', 'data.json', 'recipes.json']
        
        for filename in possible_files:
            if os.path.exists(filename):
                try:
                    self._log(f"📄 JSON fájl megtalálva: {filename}")
                    
                    with open(filename, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Fájl méret és típus ellenőrzése
                    file_size = os.path.getsize(filename)
                    self._log(f"📊 Fájl méret: {file_size:,} byte")
                    
                    # JSON struktúra validálása
                    if self._validate_json_structure(data):
                        return data
                    else:
                        self._log(f"❌ Érvénytelen JSON struktúra: {filename}")
                        continue
                        
                except json.JSONDecodeError as e:
                    self._log(f"❌ JSON dekódolási hiba ({filename}): {e}")
                    continue
                except Exception as e:
                    self._log(f"❌ Fájl olvasási hiba ({filename}): {e}")
                    continue
        
        self._log("❌ Nem található érvényes JSON fájl")
        return None
    
    def _validate_json_structure(self, data: Dict) -> bool:
        """
        JSON struktúra validálása
        
        Elvárt struktúrák:
        1. {"recipes": [...]} - wrapped formátum
        2. [...] - direct list formátum
        3. {"data": [...]} - alternatív wrapped formátum
        
        Args:
            data: JSON adatok
            
        Returns:
            bool: Érvényes struktúra
        """
        try:
            recipes_list = None
            
            if isinstance(data, dict):
                # Wrapped formátum
                if 'recipes' in data:
                    recipes_list = data['recipes']
                elif 'data' in data:
                    recipes_list = data['data']
                else:
                    self._log("❌ JSON nem tartalmazza a 'recipes' vagy 'data' kulcsot")
                    return False
            elif isinstance(data, list):
                # Direct list formátum
                recipes_list = data
            else:
                self._log("❌ JSON nem dict vagy list típusú")
                return False
            
            # Lista validálása
            if not isinstance(recipes_list, list) or len(recipes_list) == 0:
                self._log("❌ Üres vagy érvénytelen receptlista")
                return False
            
            # Első recept struktúra ellenőrzése
            first_recipe = recipes_list[0]
            required_fields = ['title', 'ingredients']
            
            for field in required_fields:
                if field not in first_recipe:
                    self._log(f"❌ Hiányzó kötelező mező: {field}")
                    return False
            
            self._log(f"✅ JSON struktúra érvényes: {len(recipes_list)} recept")
            return True
            
        except Exception as e:
            self._log(f"❌ JSON validálási hiba: {e}")
            return False
    
    def _create_dataframe(self, json_data: Dict) -> Optional[pd.DataFrame]:
        """
        Pandas DataFrame létrehozása JSON adatokból
        
        Args:
            json_data: Validált JSON adatok
            
        Returns:
            Optional[pd.DataFrame]: Receptek DataFrame vagy None
        """
        try:
            # Receptlista kinyerése
            if isinstance(json_data, dict):
                recipes_list = json_data.get('recipes', json_data.get('data', []))
            else:
                recipes_list = json_data
            
            # DataFrame létrehozása
            df = pd.DataFrame(recipes_list)
            self._log(f"📊 DataFrame létrehozva: {len(df)} sor, {len(df.columns)} oszlop")
            
            # Oszlopok ellenőrzése
            self._log(f"📋 Oszlopok: {', '.join(df.columns.tolist())}")
            
            return df
            
        except Exception as e:
            self._log(f"❌ DataFrame létrehozási hiba: {e}")
            return None
    
    def _validate_and_clean_data(self) -> None:
        """
        Adatok validálása és tisztítása
        
        Műveletek:
        1. ID oszlop normalizálása
        2. Kötelező oszlopok ellenőrzése/létrehozása
        3. Hiányzó értékek kezelése
        4. Adattípusok korrigálása
        """
        try:
            self._log("🧹 Adatok tisztítása és validálása...")
            
            # 1. ID oszlop normalizálása
            self._normalize_id_column()
            
            # 2. Kötelező oszlopok biztosítása
            self._ensure_required_columns()
            
            # 3. Pontozási oszlopok kezelése
            self._handle_scoring_columns()
            
            # 4. Hiányzó értékek kezelése
            self._handle_missing_values()
            
            # 5. Adattípusok korrigálása
            self._correct_data_types()
            
            self._log("✅ Adatok sikeresen megtisztítva")
            
        except Exception as e:
            self._log(f"❌ Adattisztítási hiba: {e}")
    
    def _normalize_id_column(self) -> None:
        """ID oszlop normalizálása"""
        if 'recipeid' in self.recipes_df.columns:
            self.recipes_df['id'] = self.recipes_df['recipeid']
            self._log("✅ recipeid → id konverzió")
        elif 'id' not in self.recipes_df.columns:
            self.recipes_df['id'] = range(1, len(self.recipes_df) + 1)
            self._log("✅ Automatikus ID oszlop generálva")
    
    def _ensure_required_columns(self) -> None:
        """Kötelező oszlopok biztosítása"""
        required_columns = {
            'title': 'Névtelen Recept',
            'ingredients': 'Összetevők nem megadva',
            'category': 'Egyéb'
        }
        
        for col, default_value in required_columns.items():
            if col not in self.recipes_df.columns:
                self.recipes_df[col] = default_value
                self._log(f"✅ Hiányzó oszlop létrehozva: {col}")
    
    def _handle_scoring_columns(self) -> None:
        """
        Pontozási oszlopok (ESI, HSI, PPI) kezelése
        
        ESI: Környezeti hatás (inverz normalizálás szükséges)
        HSI: Egészségügyi érték (0-100 skála)
        PPI: Személyes preferencia (0-100 skála)
        """
        scoring_columns = ['ESI', 'HSI', 'PPI']
        
        for col in scoring_columns:
            if col not in self.recipes_df.columns:
                # Random értékek generálása hiányzó oszlopokhoz
                self.recipes_df[col] = [random.randint(30, 90) for _ in range(len(self.recipes_df))]
                self._log(f"⚠️ Hiányzó {col} oszlop: random értékekkel kitöltve")
            else:
                # Meglévő oszlop validálása
                non_null_count = self.recipes_df[col].notna().sum()
                self._log(f"✅ {col} oszlop: {non_null_count}/{len(self.recipes_df)} érvényes érték")
    
    def _handle_missing_values(self) -> None:
        """Hiányzó értékek kezelése"""
        # Szöveges oszlopok kitöltése
        text_columns = ['title', 'ingredients', 'instructions', 'category']
        for col in text_columns:
            if col in self.recipes_df.columns:
                null_count_before = self.recipes_df[col].isnull().sum()
                if null_count_before > 0:
                    self.recipes_df[col] = self.recipes_df[col].fillna(f'Hiányzó {col}')
                    self._log(f"✅ {col}: {null_count_before} hiányzó érték kitöltve")
        
        # Numerikus oszlopok kitöltése
        numeric_columns = ['ESI', 'HSI', 'PPI']
        for col in numeric_columns:
            if col in self.recipes_df.columns:
                null_count_before = self.recipes_df[col].isnull().sum()
                if null_count_before > 0:
                    median_value = self.recipes_df[col].median()
                    self.recipes_df[col] = self.recipes_df[col].fillna(median_value)
                    self._log(f"✅ {col}: {null_count_before} hiányzó érték kitöltve mediánnal ({median_value:.1f})")
    
    def _correct_data_types(self) -> None:
        """Adattípusok korrigálása"""
        try:
            # ID oszlop: integer
            self.recipes_df['id'] = pd.to_numeric(self.recipes_df['id'], errors='coerce').fillna(0).astype(int)
            
            # Pontozási oszlopok: float
            for col in ['ESI', 'HSI', 'PPI']:
                if col in self.recipes_df.columns:
                    self.recipes_df[col] = pd.to_numeric(self.recipes_df[col], errors='coerce').fillna(50.0)
            
            # Szöveges oszlopok: string
            text_columns = ['title', 'ingredients', 'instructions', 'category']
            for col in text_columns:
                if col in self.recipes_df.columns:
                    self.recipes_df[col] = self.recipes_df[col].astype(str)
            
            self._log("✅ Adattípusok korrigálva")
            
        except Exception as e:
            self._log(f"❌ Adattípus korrigálási hiba: {e}")
    
    def _generate_data_statistics(self) -> None:
        """Adatstatisztikák generálása"""
        try:
            self.data_stats = {
                'total_recipes': len(self.recipes_df),
                'columns': list(self.recipes_df.columns),
                'missing_values': self.recipes_df.isnull().sum().to_dict(),
                'data_types': self.recipes_df.dtypes.astype(str).to_dict(),
                'memory_usage': f"{self.recipes_df.memory_usage(deep=True).sum() / 1024:.1f} KB"
            }
            
            # Pontozási oszlopok statisztikái
            if 'ESI' in self.recipes_df.columns:
                self.data_stats['esi_stats'] = {
                    'min': float(self.recipes_df['ESI'].min()),
                    'max': float(self.recipes_df['ESI'].max()),
                    'mean': float(self.recipes_df['ESI'].mean()),
                    'std': float(self.recipes_df['ESI'].std())
                }
            
            # Kategóriák eloszlása
            if 'category' in self.recipes_df.columns:
                category_counts = self.recipes_df['category'].value_counts().head(10)
                self.data_stats['top_categories'] = category_counts.to_dict()
            
            self._log(f"📊 Statisztikák generálva: {self.data_stats['total_recipes']} recept")
            
        except Exception as e:
            self._log(f"❌ Statisztika generálási hiba: {e}")
    
    def get_recipes_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Receptek DataFrame lekérése
        
        Returns:
            Optional[pd.DataFrame]: Receptek DataFrame vagy None
        """
        return self.recipes_df if self.is_initialized else None
    
    def get_initialization_logs(self) -> List[str]:
        """
        Inicializálási logok lekérése
        
        Returns:
            List[str]: Log üzenetek listája
        """
        return self.initialization_logs.copy()
    
    def get_data_statistics(self) -> Dict:
        """
        Adatstatisztikák lekérése
        
        Returns:
            Dict: Statisztikai adatok
        """
        return self.data_stats.copy()
    
    def is_system_ready(self) -> bool:
        """
        Rendszer készenlét ellenőrzése
        
        Returns:
            bool: Rendszer kész a használatra
        """
        return (self.is_initialized and 
                self.recipes_df is not None and 
                len(self.recipes_df) > 0)
    
    def get_system_status(self) -> Dict:
        """
        Teljes rendszer státusz lekérése
        
        Returns:
            Dict: Rendszer állapot információk
        """
        return {
            'initialized': self.is_initialized,
            'ready': self.is_system_ready(),
            'recipe_count': len(self.recipes_df) if self.recipes_df is not None else 0,
            'last_update': datetime.now().isoformat(),
            'data_stats': self.data_stats,
            'log_count': len(self.initialization_logs)
        }
    
    def _log(self, message: str) -> None:
        """
        Log üzenet hozzáadása timestamppel
        
        Args:
            message: Log üzenet
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp}: {message}"
        self.initialization_logs.append(log_entry)
        print(f"DATA_SERVICE: {message}")


# Singleton pattern a globális eléréshez
_data_service = None

def get_data_service() -> DataService:
    """
    Globális DataService instance lekérése
    
    Returns:
        DataService: DataService instance
    """
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service

def initialize_data_service() -> bool:
    """
    Globális DataService inicializálása
    
    Returns:
        bool: Sikeres inicializálás
    """
    service = get_data_service()
    return service.initialize_system()

def ensure_data_service_initialized() -> bool:
    """
    DataService inicializáltságának biztosítása
    
    Returns:
        bool: DataService kész
    """
    service = get_data_service()
    if not service.is_system_ready():
        return service.initialize_system()
    return True
