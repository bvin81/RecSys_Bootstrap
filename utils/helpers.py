# utils/helpers.py
"""
GreenRec Helper Functions
========================

Általános segédfunkciók és utilities a GreenRec alkalmazáshoz.
Tartalmazza a gyakran használt funkciókat, formázási segédeket és közös logikát.
"""

import re
import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
from functools import wraps, lru_cache
from pathlib import Path
import logging
import pandas as pd
import numpy as np
from flask import session, request, jsonify, current_app

logger = logging.getLogger(__name__)

# =====================================
# ID Generation and Session Management
# =====================================

def generate_user_id(prefix: str = "user") -> str:
    """
    Egyedi felhasználói azonosító generálása
    
    Args:
        prefix: Azonosító előtagja
        
    Returns:
        Egyedi user ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = secrets.token_hex(4)
    return f"{prefix}_{timestamp}_{random_part}"

def generate_session_id() -> str:
    """Egyedi session azonosító generálása"""
    return str(uuid.uuid4()).replace('-', '')[:16]

def assign_user_group(user_id: str, group_weights: Dict[str, float] = None) -> str:
    """
    Felhasználó A/B/C csoporthoz rendelése determinisztikus módon
    
    Args:
        user_id: Felhasználó azonosító
        group_weights: Csoportok súlyozása {'A': 0.33, 'B': 0.33, 'C': 0.34}
        
    Returns:
        Csoport betűjel ('A', 'B', vagy 'C')
    """
    if group_weights is None:
        group_weights = {'A': 0.33, 'B': 0.33, 'C': 0.34}
    
    # Determinisztikus hash a user_id alapján
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    random_value = (hash_value % 10000) / 10000  # 0.0-1.0 tartomány
    
    # Csoporthoz rendelés súlyok alapján
    cumulative = 0
    for group, weight in group_weights.items():
        cumulative += weight
        if random_value <= cumulative:
            return group
    
    return 'C'  # Fallback

def get_or_create_user_session() -> Dict[str, Any]:
    """
    Felhasználói session lekérdezése vagy létrehozása
    
    Returns:
        Session dictionary user_id, group, round stb. információkkal
    """
    if 'user_id' not in session:
        user_id = generate_user_id()
        user_group = assign_user_group(user_id)
        
        session.update({
            'user_id': user_id,
            'user_group': user_group,
            'learning_round': 1,
            'ratings': {},
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat()
        })
        
        logger.info(f"New user session created: {user_id} (Group: {user_group})")
    
    # Update last activity
    session['last_activity'] = datetime.now().isoformat()
    
    return {
        'user_id': session['user_id'],
        'user_group': session['user_group'],
        'learning_round': session.get('learning_round', 1),
        'ratings': session.get('ratings', {}),
        'created_at': session.get('created_at'),
        'last_activity': session['last_activity']
    }

# =====================================
# Data Formatting and Conversion
# =====================================

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Biztonságos float konverzió
    
    Args:
        value: Konvertálandó érték
        default: Alapértelmezett érték hiba esetén
        
    Returns:
        Float érték vagy default
    """
    try:
        if pd.isna(value) or value is None or value == '':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value: Any, default: int = 0) -> int:
    """
    Biztonságos integer konverzió
    
    Args:
        value: Konvertálandó érték
        default: Alapértelmezett érték hiba esetén
        
    Returns:
        Integer érték vagy default
    """
    try:
        if pd.isna(value) or value is None or value == '':
            return default
        return int(float(value))  # float-on keresztül a biztonság kedvéért
    except (ValueError, TypeError):
        return default

def normalize_score(value: float, min_val: float, max_val: float) -> float:
    """
    Pontszám normalizálása 0-100 skálára
    
    Args:
        value: Normalizálandó érték
        min_val: Minimum érték a tartományban
        max_val: Maximum érték a tartományban
        
    Returns:
        Normalizált érték 0-100 között
    """
    if max_val == min_val:
        return 50.0  # Középérték ha nincs variancia
    
    normalized = 100 * (value - min_val) / (max_val - min_val)
    return max(0.0, min(100.0, normalized))

def inverse_normalize_score(value: float, min_val: float, max_val: float) -> float:
    """
    Inverz pontszám normalizálása (magasabb érték = rosszabb, pl. ESI)
    
    Args:
        value: Normalizálandó érték
        min_val: Minimum érték a tartományban
        max_val: Maximum érték a tartományban
        
    Returns:
        Inverz normalizált érték 0-100 között
    """
    normalized = normalize_score(value, min_val, max_val)
    return 100.0 - normalized

def calculate_composite_score(esi: float, hsi: float, ppi: float, 
                            esi_weight: float = 0.4, hsi_weight: float = 0.4, 
                            ppi_weight: float = 0.2) -> float:
    """
    Kompozit pontszám számítása ESI, HSI, PPI alapján
    
    Args:
        esi: Environmental Score Index (inverz normalizált)
        hsi: Health Score Index
        ppi: Popularity Index  
        esi_weight: ESI súly (default: 0.4)
        hsi_weight: HSI súly (default: 0.4)
        ppi_weight: PPI súly (default: 0.2)
        
    Returns:
        Kompozit pontszám 0-100 között
    """
    # Biztonsági ellenőrzés
    esi = safe_float(esi, 50.0)
    hsi = safe_float(hsi, 50.0)
    ppi = safe_float(ppi, 50.0)
    
    composite = (esi * esi_weight + hsi * hsi_weight + ppi * ppi_weight)
    return max(0.0, min(100.0, composite))

def format_number(number: Union[int, float], decimals: int = 1) -> str:
    """
    Szám formázása magyar lokalizációval
    
    Args:
        number: Formázandó szám
        decimals: Tizedesjegyek száma
        
    Returns:
        Formázott szám string
    """
    try:
        if decimals == 0:
            return f"{int(number):,}".replace(',', ' ')
        else:
            return f"{number:.{decimals}f}".replace('.', ',')
    except (ValueError, TypeError):
        return "N/A"

def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Százalék formázása
    
    Args:
        value: Érték 0-1 között
        decimals: Tizedesjegyek száma
        
    Returns:
        Formázott százalék string
    """
    try:
        percentage = value * 100
        return f"{percentage:.{decimals}f}%".replace('.', ',')
    except (ValueError, TypeError):
        return "N/A%"

def format_duration(seconds: Union[int, float]) -> str:
    """
    Időtartam formázása emberi olvasható formába
    
    Args:
        seconds: Másodpercek száma
        
    Returns:
        Formázott időtartam string
    """
    try:
        seconds = int(seconds)
        
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    except (ValueError, TypeError):
        return "N/A"

# =====================================
# String Processing and Validation
# =====================================

def clean_text(text: str) -> str:
    """
    Szöveg tisztítása és normalizálása
    
    Args:
        text: Tisztítandó szöveg
        
    Returns:
        Tisztított szöveg
    """
    if not text or pd.isna(text):
        return ""
    
    # String-re konvertálás
    text = str(text).strip()
    
    # Extra whitespace eltávolítása
    text = re.sub(r'\s+', ' ', text)
    
    # HTML tagek eltávolítása (alapvető)
    text = re.sub(r'<[^>]+>', '', text)
    
    return text

def extract_ingredients(ingredients_text: str) -> List[str]:
    """
    Összetevők kinyerése szövegből
    
    Args:
        ingredients_text: Összetevők szöveg (vesszővel vagy sortöréssel elválasztva)
        
    Returns:
        Összetevők listája
    """
    if not ingredients_text or pd.isna(ingredients_text):
        return []
    
    # Tisztítás és normalizálás
    text = clean_text(ingredients_text)
    
    # Elválasztás vesszővel vagy sortöréssel
    if ',' in text:
        ingredients = [item.strip() for item in text.split(',')]
    elif '\n' in text:
        ingredients = [item.strip() for item in text.split('\n')]
    else:
        # Szavankénti felosztás ha nincs egyértelmű elválasztó
        ingredients = [item.strip() for item in text.split()]
    
    # Üres és túl rövid elemek kiszűrése
    ingredients = [ing for ing in ingredients if len(ing) > 2]
    
    return ingredients[:20]  # Maximum 20 összetevő

def extract_categories(categories_text: str) -> List[str]:
    """
    Kategóriák kinyerése szövegből
    
    Args:
        categories_text: Kategóriák szöveg
        
    Returns:
        Kategóriák listája
    """
    if not categories_text or pd.isna(categories_text):
        return []
    
    text = clean_text(categories_text)
    
    # Gyakori elválasztók
    for separator in [',', ';', '|', '\n']:
        if separator in text:
            categories = [cat.strip() for cat in text.split(separator)]
            break
    else:
        categories = [text]
    
    # Tisztítás és normalizálás
    categories = [cat.lower().title() for cat in categories if len(cat) > 1]
    
    return categories[:10]  # Maximum 10 kategória

def validate_rating(rating: Any) -> bool:
    """
    Értékelés validálása (1-5 skála)
    
    Args:
        rating: Validálandó értékelés
        
    Returns:
        True ha valid, False egyébként
    """
    try:
        rating_int = int(rating)
        return 1 <= rating_int <= 5
    except (ValueError, TypeError):
        return False

# =====================================
# Date and Time Utilities
# =====================================

def parse_datetime(date_string: str) -> Optional[datetime]:
    """
    Dátum string parsing különböző formátumokkal
    
    Args:
        date_string: Dátum string
        
    Returns:
        Datetime objektum vagy None
    """
    if not date_string or pd.isna(date_string):
        return None
    
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y/%m/%d'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(str(date_string), fmt)
        except ValueError:
            continue
    
    return None

def time_ago(timestamp: Union[str, datetime]) -> str:
    """
    Relatív időt ad vissza (pl. "2 órája")
    
    Args:
        timestamp: Időbélyeg string vagy datetime
        
    Returns:
        Relatív idő string
    """
    if isinstance(timestamp, str):
        timestamp = parse_datetime(timestamp)
    
    if not timestamp:
        return "Ismeretlen"
    
    now = datetime.now()
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Most"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} perce"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} órája"
    elif seconds < 2592000:  # 30 days
        days = int(seconds // 86400)
        return f"{days} napja"
    else:
        months = int(seconds // 2592000)
        return f"{months} hónapja"

# =====================================
# List and Dictionary Utilities
# =====================================

def safe_get(dictionary: Dict, key: str, default: Any = None) -> Any:
    """
    Biztonságos dictionary érték lekérdezés
    
    Args:
        dictionary: Dictionary objektum
        key: Kulcs
        default: Alapértelmezett érték
        
    Returns:
        Érték vagy default
    """
    try:
        return dictionary.get(key, default)
    except AttributeError:
        return default

def deep_get(data: Dict, path: str, default: Any = None, separator: str = '.') -> Any:
    """
    Mély dictionary érték lekérdezés dot notation-nal
    
    Args:
        data: Dictionary objektum
        path: Kulcs útvonal (pl. "user.preferences.theme")
        default: Alapértelmezett érték
        separator: Elválasztó karakter
        
    Returns:
        Érték vagy default
    """
    keys = path.split(separator)
    value = data
    
    try:
        for key in keys:
            if isinstance(value, dict):
                value = value[key]
            else:
                return default
        return value
    except (KeyError, TypeError):
        return default

def flatten_dict(data: Dict, parent_key: str = '', separator: str = '_') -> Dict:
    """
    Nested dictionary laposítása
    
    Args:
        data: Dictionary objektum
        parent_key: Szülő kulcs előtag
        separator: Kulcs elválasztó
        
    Returns:
        Lapos dictionary
    """
    items = []
    
    for key, value in data.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key
        
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, separator).items())
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, f"{new_key}{separator}{i}", separator).items())
                else:
                    items.append((f"{new_key}{separator}{i}", item))
        else:
            items.append((new_key, value))
    
    return dict(items)

def chunk_list(data: List, chunk_size: int) -> List[List]:
    """
    Lista felosztása kisebb chunkok-ra
    
    Args:
        data: Lista
        chunk_size: Chunk méret
        
    Returns:
        Chunkok listája
    """
    chunks = []
    for i in range(0, len(data), chunk_size):
        chunks.append(data[i:i + chunk_size])
    return chunks

def deduplicate_list(data: List, key: Callable = None) -> List:
    """
    Lista deduplikálása
    
    Args:
        data: Lista
        key: Kulcs függvény duplikáció detektáláshoz
        
    Returns:
        Deduplikált lista
    """
    if key is None:
        return list(dict.fromkeys(data))  # Sorrend megtartása
    
    seen = set()
    result = []
    
    for item in data:
        item_key = key(item)
        if item_key not in seen:
            seen.add(item_key)
            result.append(item)
    
    return result

# =====================================
# Decorators and Performance
# =====================================

def timer(func: Callable) -> Callable:
    """
    Függvény futási idő mérése decorator
    
    Args:
        func: Mérni kívánt függvény
        
    Returns:
        Wrapped függvény
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        logger.debug(f"{func.__name__} executed in {duration:.3f}s")
        
        return result
    return wrapper

def retry(max_attempts: int = 3, delay: float = 1.0, 
          exceptions: Tuple = (Exception,)) -> Callable:
    """
    Újrapróbálkozás decorator
    
    Args:
        max_attempts: Maximum próbálkozások száma
        delay: Késleltetés másodpercekben
        exceptions: Kivételek amikre újrapróbálkozik
        
    Returns:
        Retry decorator
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        import time
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts")
            
            raise last_exception
        return wrapper
    return decorator

@lru_cache(maxsize=128)
def cached_calculation(data_hash: str, calculation_func: str) -> Any:
    """
    Számítások cache-elése hash alapján
    
    Args:
        data_hash: Adat hash
        calculation_func: Számítási függvény neve
        
    Returns:
        Cache-elt eredmény
    """
    # Ez egy placeholder - valós implementációban a funkció alapján számolna
    return None

# =====================================
# File and Data Utilities
# =====================================

def load_json_safe(file_path: Union[str, Path]) -> Optional[Dict]:
    """
    Biztonságos JSON fájl betöltés
    
    Args:
        file_path: Fájl elérési út
        
    Returns:
        JSON adatok vagy None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error(f"JSON loading failed for {file_path}: {e}")
        return None

def save_json_safe(data: Dict, file_path: Union[str, Path]) -> bool:
    """
    Biztonságos JSON fájl mentés
    
    Args:
        data: Mentendő adatok
        file_path: Fájl elérési út
        
    Returns:
        True ha sikeres, False egyébként
    """
    try:
        # Backup létrehozása ha a fájl már létezik
        if Path(file_path).exists():
            backup_path = f"{file_path}.backup"
            Path(file_path).rename(backup_path)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"JSON saved successfully to {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"JSON saving failed for {file_path}: {e}")
        return False

def get_file_hash(file_path: Union[str, Path]) -> str:
    """
    Fájl MD5 hash számítása
    
    Args:
        file_path: Fájl elérési út
        
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except FileNotFoundError:
        return ""

# =====================================
# Flask Specific Utilities
# =====================================

def jsonify_response(data: Any, status_code: int = 200, 
                    message: str = "success") -> Tuple[Dict, int]:
    """
    Standardizált JSON válasz generálása
    
    Args:
        data: Válasz adatok
        status_code: HTTP status kód
        message: Státusz üzenet
        
    Returns:
        JSON response és status kód
    """
    response = {
        'status': 'success' if status_code < 400 else 'error',
        'message': message,
        'data': data,
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(response), status_code

def get_client_ip() -> str:
    """
    Kliens IP cím lekérdezése
    
    Returns:
        IP cím string
    """
    # X-Forwarded-For header ellenőrzése proxy/load balancer esetén
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'

def get_user_agent() -> str:
    """
    User-Agent string lekérdezése
    
    Returns:
        User-Agent string
    """
    return request.headers.get('User-Agent', 'unknown')

def is_ajax_request() -> bool:
    """
    AJAX kérés detektálása
    
    Returns:
        True ha AJAX kérés
    """
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

# =====================================
# Data Analysis Helpers
# =====================================

def calculate_statistics(data: List[float]) -> Dict[str, float]:
    """
    Alapvető statisztikák számítása
    
    Args:
        data: Számok listája
        
    Returns:
        Statisztikai adatok dictionary
    """
    if not data:
        return {
            'count': 0, 'mean': 0, 'median': 0, 'std': 0,
            'min': 0, 'max': 0, 'q25': 0, 'q75': 0
        }
    
    data = [x for x in data if not pd.isna(x)]  # NaN értékek kiszűrése
    
    if not data:
        return {
            'count': 0, 'mean': 0, 'median': 0, 'std': 0,
            'min': 0, 'max': 0, 'q25': 0, 'q75': 0
        }
    
    return {
        'count': len(data),
        'mean': float(np.mean(data)),
        'median': float(np.median(data)),
        'std': float(np.std(data)),
        'min': float(np.min(data)),
        'max': float(np.max(data)),
        'q25': float(np.percentile(data, 25)),
        'q75': float(np.percentile(data, 75))
    }

def bucket_values(values: List[float], num_buckets: int = 5) -> Dict[str, int]:
    """
    Értékek bucketing-je histogram-hoz
    
    Args:
        values: Értékek listája
        num_buckets: Bucket-ek száma
        
    Returns:
        Bucket counts dictionary
    """
    if not values:
        return {}
    
    values = [x for x in values if not pd.isna(x)]
    
    if not values:
        return {}
    
    min_val, max_val = min(values), max(values)
    
    if min_val == max_val:
        return {f"{min_val:.1f}": len(values)}
    
    bucket_size = (max_val - min_val) / num_buckets
    buckets = {}
    
    for i in range(num_buckets):
        bucket_start = min_val + i * bucket_size
        bucket_end = bucket_start + bucket_size
        bucket_label = f"{bucket_start:.1f}-{bucket_end:.1f}"
        
        count = sum(1 for v in values if bucket_start <= v < bucket_end)
        if i == num_buckets - 1:  # Utolsó bucket tartalmazza a max értéket is
            count = sum(1 for v in values if bucket_start <= v <= bucket_end)
        
        buckets[bucket_label] = count
    
    return buckets

# =====================================
# Export Functions
# =====================================

# A leggyakrabban használt függvények exportálása
__all__ = [
    # ID and session management
    'generate_user_id', 'generate_session_id', 'assign_user_group', 'get_or_create_user_session',
    
    # Data formatting
    'safe_float', 'safe_int', 'normalize_score', 'inverse_normalize_score', 
    'calculate_composite_score', 'format_number', 'format_percentage', 'format_duration',
    
    # String processing
    'clean_text', 'extract_ingredients', 'extract_categories', 'validate_rating',
    
    # Date/time utilities
    'parse_datetime', 'time_ago',
    
    # List/dict utilities
    'safe_get', 'deep_get', 'flatten_dict', 'chunk_list', 'deduplicate_list',
    
    # Decorators
    'timer', 'retry', 'cached_calculation',
    
    # File utilities
    'load_json_safe', 'save_json_safe', 'get_file_hash',
    
    # Flask utilities
    'jsonify_response', 'get_client_ip', 'get_user_agent', 'is_ajax_request',
    
    # Analytics helpers
    'calculate_statistics', 'bucket_values'
]
