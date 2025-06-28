import random
import json
import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import logging

# Logging beállítása
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VirtualUser:
    """
    Virtuális felhasználó A/B/C csoportonkénti láthatósággal
    JAVÍTOTT VERZIÓ - csoportonkénti döntési logikával
    """
    
    def __init__(self, user_type, username, group='A'):
        self.user_type = user_type
        self.username = username
        self.group = group
        self.session = requests.Session()
        self.base_url = "https://boots-c9ce40a0998d.herokuapp.com"
        
        # Preferencia súlyok (0-1 skála)
        self.preferences = self._get_preferences(user_type)
        
        # Választási statisztikák
        self.choices_made = []
        self.session_start_time = None
        self.total_choices = 0
        
    def _get_preferences(self, user_type):
        """Felhasználó típus alapján preferencia súlyok"""
        preferences = {
            'egeszsegtudatos': {
                'hsi_weight': 0.8,
                'esi_weight': 0.1, 
                'ppi_weight': 0.1,
                'choice_probability': 0.85,
                'choices_per_session': (4, 8),
                'description': 'Magas HSI értékeket keres'
            },
            'kornyezettudatos': {
                'hsi_weight': 0.2,
                'esi_weight': 0.7,
                'ppi_weight': 0.1,
                'choice_probability': 0.80,
                'choices_per_session': (3, 7),
                'description': 'Alacsony környezeti hatást keres'
            },
            'izorgia': {
                'hsi_weight': 0.1,
                'esi_weight': 0.1,
                'ppi_weight': 0.8,
                'choice_probability': 0.90,
                'choices_per_session': (5, 10),
                'description': 'Magas PPI értékeket keres'
            },
            'kiegyensulyozott': {
                'hsi_weight': 0.33,
                'esi_weight': 0.33,
                'ppi_weight': 0.34,
                'choice_probability': 0.75,
                'choices_per_session': (3, 6),
                'description': 'Minden szempontot egyformán fontosnak tart'
            },
            'kenyelmi': {
                'hsi_weight': 0.2,
                'esi_weight': 0.1,
                'ppi_weight': 0.7,
                'choice_probability': 0.95,
                'choices_per_session': (2, 5),
                'description': 'Népszerű, könnyű recepteket keres'
            },
            'ujdonsagkereso': {
                'hsi_weight': 0.3,
                'esi_weight': 0.3,
                'ppi_weight': 0.4,
                'novelty_bonus': 0.5,
                'choice_probability': 0.70,
                'choices_per_session': (4, 9),
                'description': 'Ritka recepteket preferál'
            }
        }
        return preferences.get(user_type, preferences['kiegyensulyozott'])
    
    def register(self):
        """Regisztráció a rendszerbe"""
        try:
            # GET a regisztrációs oldalhoz
            response = self.session.get(f"{self.base_url}/register", timeout=10)
            
            # POST regisztráció
            register_data = {
                'username': self.username,
                'password': 'test123',
                'confirm_password': 'test123'
            }
            
            response = self.session.post(f"{self.base_url}/register", data=register_data, timeout=10)
            
            if response.status_code == 200 and 'Sikeres regisztráció' in response.text:
                logger.info(f"✅ {self.username} regisztrálva")
                return True
            else:
                logger.warning(f"❌ {self.username} regisztráció sikertelen")
                return False
                
        except Exception as e:
            logger.error(f"❌ Regisztráció hiba {self.username}: {e}")
            return False
    
    def login(self):
        """Bejelentkezés"""
        try:
            login_data = {
                'username': self.username,
                'password': 'test123'
            }
            
            response = self.session.post(f"{self.base_url}/login", data=login_data, timeout=10)
            
            if response.status_code == 200 and ('Üdvözöllek' in response.text or 'üdvözöllek' in response.text):
                logger.info(f"✅ {self.username} bejelentkezve")
                
                # Csoport kinyerése a HTML-ből
                if 'A csoport' in response.text or 'group-indicator">Tesztcsoport: A' in response.text:
                    self.group = 'A'
                elif 'B csoport' in response.text or 'group-indicator">Tesztcsoport: B' in response.text:
                    self.group = 'B'
                elif 'C csoport' in response.text or 'group-indicator">Tesztcsoport: C' in response.text:
                    self.group = 'C'
                
                logger.info(f"🎯 {self.username} besorolva: {self.group} csoport")
                return True
            else:
                logger.warning(f"❌ {self.username} bejelentkezés sikertelen")
                return False
                
        except Exception as e:
            logger.error(f"❌ Bejelentkezés hiba {self.username}: {e}")
            return False
    
    def get_recommendations(self):
        """Valós körönkénti ajánlások lekérése"""
        try:
            # Valós API hívás - NEM mock!
            response = self.session.post(
                f"{self.base_url}/recommend", 
                headers={'Content-Type': 'application/json'},
                json={},  # Üres JSON body
                timeout=15
            )
            
            if response.status_code == 200:
                try:
                    # Próbáljuk meg JSON-ként parsolni
                    recommendations = response.json().get('recommendations', [])
                    
                    if recommendations:
                        logger.info(f"🎯 {self.username} kapott {len(recommendations)} VALÓS ajánlást")
                        
                        # Ellenőrizzük van-e round_number és recommendation_type
                        if recommendations and 'round_number' in recommendations[0]:
                            round_num = recommendations[0]['round_number']
                            rec_types = [rec.get('recommendation_type', 'unknown') for rec in recommendations]
                            logger.info(f"📊 {self.username} - {round_num}. kör, típusok: {set(rec_types)}")
                        
                        return recommendations
                    else:
                        logger.warning(f"⚠️ {self.username} - Üres ajánlások a válaszban")
                        return self._generate_mock_recommendations()
                        
                except ValueError:
                    # Nem JSON válasz - valószínűleg HTML
                    logger.warning(f"⚠️ {self.username} - HTML válasz, mock használata")
                    return self._generate_mock_recommendations()
            else:
                logger.warning(f"❌ {self.username} - HTTP {response.status_code}")
                return self._generate_mock_recommendations()
                
        except Exception as e:
            logger.error(f"❌ {self.username} ajánlás hiba: {e}")
            return self._generate_mock_recommendations()
    
    def _generate_mock_recommendations(self):
        """Mock ajánlások generálása fallback-ként"""
        recommendations = []
        for i in range(5):  # 5 ajánlás
            recipe = {
                'id': random.randint(1, 1000),
                'title': f"Virtuális Recept {i+1}",
                'hsi': random.randint(30, 95),
                'esi': random.randint(20, 200),
                'ppi': random.randint(40, 90),
                'category': random.choice(['Főétel', 'Saláta', 'Leves', 'Desszert']),
                'ingredients': f"Mock összetevők {i+1}",
                'composite_score': 0,
                'round_number': len(self.choices_made) + 1,
                'recommendation_type': 'mock'
            }
            
            # Kompozit pontszám számítása
            recipe['composite_score'] = (
                0.4 * recipe['hsi'] +
                0.4 * (255 - recipe['esi']) +
                0.2 * recipe['ppi']
            ) / 2.55
            
            recommendations.append(recipe)
        
        return recommendations
    
    def calculate_preference_score(self, recipe):
        """
        Recept értékelése CSOPORTONKÉNT ELTÉRŐ INFORMÁCIÓ alapján
        A/B/C teszt hatásának szimulálása
        """
        
        # ===== CSOPORTONKÉNTI LÁTHATÓSÁG =====
        if self.group == 'A':
            # A CSOPORT: NEM látja a pontszámokat
            score = self._calculate_intuitive_score(recipe)
            
        elif self.group == 'B':
            # B CSOPORT: LÁTJA a HSI/ESI/PPI pontszámokat
            hsi = recipe.get('hsi', 50)
            esi = recipe.get('esi', 50) 
            ppi = recipe.get('ppi', 50)
            score = self._calculate_informed_score(recipe, hsi, esi, ppi)
            
        elif self.group == 'C':
            # C CSOPORT: LÁTJA a pontszámokat + MAGYARÁZATOT
            hsi = recipe.get('hsi', 50)
            esi = recipe.get('esi', 50)
            ppi = recipe.get('ppi', 50) 
            score = self._calculate_explained_score(recipe, hsi, esi, ppi)
        
        else:
            # Fallback
            score = 50.0
        
        # Zaj hozzáadása (emberi unpredictability)
        noise = random.uniform(-5, 5)
        score += noise
        
        return max(0, min(100, score))
    
    def _calculate_intuitive_score(self, recipe):
        """
        A CSOPORT: Intuitív döntés pontszámok nélkül
        Csak cím, kategória, összetevők alapján
        """
        score = 50.0  # Alappontszám
        
        title = recipe.get('title', '').lower()
        category = recipe.get('category', '').lower()
        ingredients = recipe.get('ingredients', '').lower()
        
        # ===== INTUITÍV PREFERENCIÁK =====
        
        # Egészségtudatos felhasználók
        if self.user_type == 'egeszsegtudatos':
            healthy_keywords = ['saláta', 'zöldség', 'quinoa', 'avokádó', 'brokkoli', 
                               'spenót', 'natúr', 'bio', 'teljes kiőrlésű']
            for keyword in healthy_keywords:
                if keyword in title or keyword in ingredients:
                    score += 15
            
            unhealthy_keywords = ['sült', 'rántott', 'szalonna', 'kolbász', 'zsíros']
            for keyword in unhealthy_keywords:
                if keyword in title or keyword in ingredients:
                    score -= 10
        
        # Környezettudatos felhasználók  
        elif self.user_type == 'kornyezettudatos':
            eco_keywords = ['vegetáriánus', 'vegán', 'növényi', 'zöldség', 'bab', 
                           'lencse', 'csicseriborsó', 'tofu', 'helyi']
            for keyword in eco_keywords:
                if keyword in title or keyword in ingredients:
                    score += 12
            
            meat_keywords = ['marhahús', 'sertés', 'csirke', 'hal', 'tonhal']
            for keyword in meat_keywords:
                if keyword in title or keyword in ingredients:
                    score -= 15
        
        # Ínyencek
        elif self.user_type == 'izorgia':
            tasty_keywords = ['sajtos', 'tejszínes', 'csokoládés', 'karamell', 
                             'pizza', 'burger', 'pasta', 'rizottó']
            for keyword in tasty_keywords:
                if keyword in title or keyword in ingredients:
                    score += 18
        
        # Kényelmi felhasználók
        elif self.user_type == 'kenyelmi':
            easy_keywords = ['gyors', 'egyszerű', 'mikrohullám', '15 perc', 
                            'instant', 'melegszendvics']
            for keyword in easy_keywords:
                if keyword in title or keyword in ingredients:
                    score += 20
        
        # Újdonságkeresők
        elif self.user_type == 'ujdonsagkereso':
            exotic_keywords = ['thai', 'indiai', 'mexikói', 'marokkói', 'kimcsi', 
                              'curry', 'exotic', 'fűszeres']
            for keyword in exotic_keywords:
                if keyword in title or keyword in ingredients:
                    score += 16
        
        return score
    
    def _calculate_informed_score(self, recipe, hsi, esi, ppi):
        """
        B CSOPORT: Tudatos döntés pontszámok alapján
        Látja a HSI/ESI/PPI értékeket
        """
        # ESI inverz (alacsonyabb = jobb)
        esi_inv = 255 - esi
        
        # Pontszámok alapján számított preferencia
        score = (
            self.preferences['hsi_weight'] * (hsi / 100.0) +
            self.preferences['esi_weight'] * (esi_inv / 255.0) +
            self.preferences['ppi_weight'] * (ppi / 100.0)
        ) * 100
        
        # Erősebb súlyozás a preferált metrikán
        if self.user_type == 'egeszsegtudatos' and hsi > 80:
            score += 10  # Bónusz magas HSI-ért
        elif self.user_type == 'kornyezettudatos' and esi < 100:  # Alacsony ESI
            score += 10  # Bónusz alacsony környezeti hatásért
        elif self.user_type == 'izorgia' and ppi > 70:
            score += 10  # Bónusz magas népszerűségért
        
        return score
    
    def _calculate_explained_score(self, recipe, hsi, esi, ppi):
        """
        C CSOPORT: Magyarázattal támogatott tudatos döntés
        Látja a pontszámokat + MAGYARÁZATOT
        """
        # Alappontszám mint B csoportnál
        score = self._calculate_informed_score(recipe, hsi, esi, ppi)
        
        # Magyarázat hatás szimulálása
        explanation_bonus = 0
        
        if self.user_type == 'egeszsegtudatos':
            if hsi > 85:
                explanation_bonus += 15  # "Ez az étel nagyon egészséges!"
            elif hsi < 40:
                explanation_bonus -= 10  # "Ez az étel kevésbé egészséges"
        
        elif self.user_type == 'kornyezettudatos':
            if esi < 80:  # Alacsony környezeti hatás
                explanation_bonus += 15  # "Ez az étel környezetbarát!"
            elif esi > 180:
                explanation_bonus -= 10  # "Ez az étel nagyobb környezeti hatással bír"
        
        elif self.user_type == 'izorgia':
            if ppi > 80:
                explanation_bonus += 15  # "Ez az étel nagyon népszerű!"
            elif ppi < 30:
                explanation_bonus -= 5   # "Ez az étel kevésbé népszerű"
        
        # Kiegyensúlyozott felhasználók jobban figyelnek minden metrikára
        elif self.user_type == 'kiegyensulyozott':
            composite = (hsi + (255-esi)/2.55 + ppi) / 3
            if composite > 70:
                explanation_bonus += 12  # "Ez az étel összességében kiváló!"
            elif composite < 40:
                explanation_bonus -= 8
        
        score += explanation_bonus
        
        # XAI EFFECT: A magyarázat növeli a bizalmat
        confidence_boost = 5
        score += confidence_boost
        
        return score
    
    def select_recipe(self, recommendations):
        """
        Recept választása CSOPORTONKÉNT ELTÉRŐ LOGIKÁVAL
        """
        if not recommendations:
            return None
        
        logger.info(f"🎯 {self.username} (Csoport {self.group}) választ {len(recommendations)} ajánlás közül...")
        
        # Minden recept pontozása a csoport láthatósága szerint
        scored_recipes = []
        for recipe in recommendations:
            score = self.calculate_preference_score(recipe)
            scored_recipes.append((recipe, score))
            
            # Debug info
            if self.group == 'A':
                logger.info(f"   📋 {recipe['title']}: {score:.1f} pont (intuitív)")
            elif self.group == 'B':
                logger.info(f"   📊 {recipe['title']}: {score:.1f} pont (HSI:{recipe.get('hsi', '?')}, ESI:{recipe.get('esi', '?')}, PPI:{recipe.get('ppi', '?')})")
            elif self.group == 'C':
                logger.info(f"   📈 {recipe['title']}: {score:.1f} pont (pontszámok + magyarázat)")
        
        # Súlyozott véletlenszerű választás
        weights = [max(score, 0.1) for _, score in scored_recipes]
        
        # Softmax-szerű súlyozás (hőmérséklet: csoport függő)
        if self.group == 'A':
            temperature = 25  # Nagyobb bizonytalanság
        elif self.group == 'B':
            temperature = 20  # Közepes bizonytalanság
        elif self.group == 'C':
            temperature = 15  # Kisebb bizonytalanság
        else:
            temperature = 20
        
        exp_weights = [pow(max(w, 0.1)/temperature, 2) for w in weights]
        total_weight = sum(exp_weights)
        probabilities = [w/total_weight for w in exp_weights]
        
        # Választás
        chosen_index = random.choices(range(len(scored_recipes)), weights=probabilities)[0]
        chosen_recipe, chosen_score = scored_recipes[chosen_index]
        
        logger.info(f"✅ {self.username} (Csoport {self.group}) választott: {chosen_recipe['title']} (pontszám: {chosen_score:.1f})")
        
        return chosen_recipe
    
    def submit_choice(self, recipe):
        """Választás elküldése round számmal"""
        try:
            choice_data = {'recipe_id': recipe['id']}
            response = self.session.post(
                f"{self.base_url}/select_recipe",
                json=choice_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"✅ {self.username} választás rögzítve")
                    
                    # Körönkénti választás statisztikák
                    choice_record = {
                        'recipe_id': recipe['id'],
                        'recipe_title': recipe['title'],
                        'hsi': recipe.get('hsi', 0),
                        'esi': recipe.get('esi', 0),
                        'ppi': recipe.get('ppi', 0),
                        'composite_score': recipe.get('composite_score', 0),
                        'round_number': recipe.get('round_number', len(self.choices_made) + 1),
                        'recommendation_type': recipe.get('recommendation_type', 'unknown'),
                        'user_score': self.calculate_preference_score(recipe),
                        'timestamp': datetime.now(),
                        'user_type': self.user_type,
                        'group': self.group
                    }
                    self.choices_made.append(choice_record)
                    self.total_choices += 1
                    
                    return True
            
            logger.warning(f"❌ {self.username} választás rögzítés sikertelen")
            return False
            
        except Exception as e:
            logger.error(f"❌ {self.username} választás rögzítés hiba: {e}")
            return False
    
    def simulate_session(self):
        """Teljes körönkénti szimulációs session"""
        logger.info(f"\n🎭 {self.username} ({self.user_type}) körönkénti szimulációja...")
        self.session_start_time = datetime.now()
        
        # 1. Regisztráció és bejelentkezés
        if not self.register():
            return False, self.get_session_summary()
        
        time.sleep(random.uniform(1, 3))
        
        if not self.login():
            return False, self.get_session_summary()
        
        time.sleep(random.uniform(2, 5))
        
        # ===== KÖRÖNKÉNTI VÁLASZTÁSOK =====
        choices_to_make = random.randint(*self.preferences['choices_per_session'])
        successful_choices = 0
        
        for round_num in range(1, choices_to_make + 1):
            logger.info(f"🔄 {self.username} - {round_num}. kör kezdése")
            
            # Választási valószínűség
            if random.random() > self.preferences['choice_probability']:
                logger.info(f"⏭️ {self.username} kihagyja a {round_num}. kört")
                continue
            
            # Ajánlások kérése (VALÓS API)
            recommendations = self.get_recommendations()
            if not recommendations:
                logger.warning(f"❌ {self.username} - Nincs ajánlás a {round_num}. körben")
                continue
            
            # "Gondolkodási" idő
            thinking_time = random.uniform(3, 8)
            logger.info(f"🤔 {self.username} gondolkodik {thinking_time:.1f} másodpercig...")
            time.sleep(thinking_time)
            
            # Recept választása
            chosen_recipe = self.select_recipe(recommendations)
            if not chosen_recipe:
                continue
            
            time.sleep(random.uniform(1, 3))
            
            # Választás rögzítése
            if self.submit_choice(chosen_recipe):
                successful_choices += 1
                logger.info(f"✅ {self.username} - {round_num}. kör: {chosen_recipe['title']} kiválasztva")
            else:
                logger.warning(f"❌ {self.username} - {round_num}. kör rögzítés sikertelen")
            
            # Várakozás következő körig
            inter_round_delay = random.uniform(2, 6)
            logger.info(f"⏱️ {self.username} vár {inter_round_delay:.1f} másodpercet...")
            time.sleep(inter_round_delay)
        
        success = successful_choices > 0
        session_summary = self.get_session_summary()
        
        logger.info(f"🎉 {self.username} szimulációja befejezve - Csoport: {self.group}, "
                   f"Körök: {successful_choices}/{choices_to_make}")
        
        return success, session_summary
    
    def get_session_summary(self):
        """Session összefoglaló"""
        session_duration = (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0
        
        avg_composite_score = 0
        if self.choices_made:
            avg_composite_score = np.mean([choice['composite_score'] for choice in self.choices_made])
        
        return {
            'username': self.username,
            'user_type': self.user_type,
            'group': self.group,
            'total_choices': self.total_choices,
            'avg_composite_score': avg_composite_score,
            'session_duration': session_duration,
            'choices': self.choices_made.copy()
        }

# ===== PÁRHUZAMOS FELDOLGOZÁS =====
def simulate_user_wrapper(user_data):
    """Wrapper függvény a párhuzamos feldolgozáshoz"""
    user_type, username = user_data
    user = VirtualUser(user_type, username)
    success, summary = user.simulate_session()
    return success, summary

def create_virtual_users(count=200):
    """Virtuális felhasználók létrehozása"""
    user_types = [
        'egeszsegtudatos',
        'kornyezettudatos', 
        'izorgia',
        'kiegyensulyozott',
        'kenyelmi',
        'ujdonsagkereso'
    ]
    
    users = []
    for i in range(count):
        user_type = random.choice(user_types)
        username = f"virtual_{user_type}_{i+1:03d}"
        users.append((user_type, username))
    
    return users

def run_enhanced_simulation(user_count=100, max_workers=4, use_parallel=True):
    """A/B/C csoportonkénti szimuláció futtatása"""
    logger.info(f"🚀 A/B/C CSOPORTONKÉNTI Virtuális felhasználók szimulációja")
    logger.info(f"👥 {user_count} felhasználó, {'párhuzamos' if use_parallel else 'soros'} feldolgozás")
    
    users = create_virtual_users(user_count)
    
    results = {
        'successful': 0,
        'failed': 0,
        'by_type': {},
        'by_group': {'A': 0, 'B': 0, 'C': 0},
        'session_summaries': [],
        'total_choices': 0,
        'avg_composite_scores': {'A': [], 'B': [], 'C': []},
        'group_choice_details': {'A': [], 'B': [], 'C': []}
    }
    
    start_time = datetime.now()
    
    if use_parallel:
        # Párhuzamos feldolgozás
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_user = {
                executor.submit(simulate_user_wrapper, user_data): user_data 
                for user_data in users
            }
            
            completed = 0
            for future in future_to_user:
                try:
                    success, summary = future.result(timeout=120)  # 2 perc timeout
                    
                    if success:
                        results['successful'] += 1
                        results['by_group'][summary['group']] += 1
                        results['total_choices'] += summary['total_choices']
                        
                        if summary['avg_composite_score'] > 0:
                            results['avg_composite_scores'][summary['group']].append(summary['avg_composite_score'])
                        
                        # Részletes választások tárolása csoportonként
                        for choice in summary['choices']:
                            results['group_choice_details'][summary['group']].append(choice)
                        
                        # Típus szerint statisztika
                        if summary['user_type'] not in results['by_type']:
                            results['by_type'][summary['user_type']] = 0
                        results['by_type'][summary['user_type']] += 1
                    else:
                        results['failed'] += 1
                    
                    results['session_summaries'].append(summary)
                    completed += 1
                    
                    if completed % 20 == 0:
                        logger.info(f"📈 Progress: {completed}/{user_count} felhasználó kész")
                        
                except Exception as e:
                    logger.error(f"❌ Felhasználó szimuláció hiba: {e}")
                    results['failed'] += 1
    else:
        # Soros feldolgozás
        for i, (user_type, username) in enumerate(users):
            try:
                user = VirtualUser(user_type, username)
                success, summary = user.simulate_session()
                
                if success:
                    results['successful'] += 1
                    results['by_group'][summary['group']] += 1
                    results['total_choices'] += summary['total_choices']
                    
                    if summary['avg_composite_score'] > 0:
                        results['avg_composite_scores'][summary['group']].append(summary['avg_composite_score'])
                    
                    for choice in summary['choices']:
                        results['group_choice_details'][summary['group']].append(choice)
                    
                    if summary['user_type'] not in results['by_type']:
                        results['by_type'][summary['user_type']] = 0
                    results['by_type'][summary['user_type']] += 1
                else:
                    results['failed'] += 1
                
                results['session_summaries'].append(summary)
                
                if (i + 1) % 15 == 0:
                    logger.info(f"📈 Progress: {i+1}/{user_count} felhasználó kész")
                
                # Rövid szünet a szerver kímélése érdekében
                time.sleep(random.uniform(0.5, 1.5))
                
            except Exception as e:
                logger.error(f"❌ {username} szimulációs hiba: {e}")
                results['failed'] += 1
    
    # ===== A/B/C CSOPORTONKÉNTI EREDMÉNYEK ELEMZÉSE =====
    duration = datetime.now() - start_time
    
    logger.info(f"\n📊 === A/B/C CSOPORTONKÉNTI SZIMULÁCIÓ EREDMÉNYEI ===")
    logger.info(f"⏱️  Futási idő: {duration}")
    logger.info(f"✅ Sikeres: {results['successful']}")
    logger.info(f"❌ Sikertelen: {results['failed']}")
    logger.info(f"📈 Sikerességi arány: {results['successful']/(results['successful']+results['failed'])*100:.1f}%")
    logger.info(f"🎯 Összes választás: {results['total_choices']}")
    
    logger.info(f"\n👥 Csoportonkénti eloszlás és átlagos kompozit pontszámok:")
    group_stats = {}
    for group in ['A', 'B', 'C']:
        count = results['by_group'][group]
        if results['avg_composite_scores'][group]:
            avg_composite = np.mean(results['avg_composite_scores'][group])
            std_composite = np.std(results['avg_composite_scores'][group])
            group_stats[group] = avg_composite
            logger.info(f"  {group} csoport: {count} felhasználó, átlag kompozit: {avg_composite:.1f} (±{std_composite:.1f})")
        else:
            logger.info(f"  {group} csoport: {count} felhasználó, nincs választás")
    
    logger.info(f"\n🎭 Felhasználó típusok eloszlása:")
    for user_type, count in results['by_type'].items():
        logger.info(f"  {user_type}: {count} felhasználó")
    
    # ===== A/B/C HIPOTÉZIS ELLENŐRZÉS =====
    logger.info(f"\n🔬 A/B/C HIPOTÉZIS ELLENŐRZÉS:")
    logger.info(f"Várt sorrend: C > B > A (magyarázat + pontszámok > csak pontszámok > kontroll)")
    
    if len(group_stats) >= 2:
        sorted_groups = sorted(group_stats.items(), key=lambda x: x[1], reverse=True)
        ranking_str = ' > '.join([f'{g}({v:.1f})' for g, v in sorted_groups])
        logger.info(f"  📊 Tényleges rangsor: {ranking_str}")
        
        # Hipotézis validáció
        if len(sorted_groups) >= 3:
            if sorted_groups[0][0] == 'C' and sorted_groups[1][0] == 'B' and sorted_groups[2][0] == 'A':
                logger.info(f"  ✅ HIPOTÉZIS TELJES MÉRTÉKBEN IGAZOLÓDOTT: C > B > A")
                hypothesis_result = "FULLY_CONFIRMED"
            elif sorted_groups[0][0] == 'C':
                logger.info(f"  ✅ HIPOTÉZIS RÉSZBEN IGAZOLÓDOTT: C csoport a legjobb")
                hypothesis_result = "PARTIALLY_CONFIRMED"
            else:
                logger.info(f"  ❌ HIPOTÉZIS NEM IGAZOLÓDOTT")
                hypothesis_result = "NOT_CONFIRMED"
        elif len(sorted_groups) == 2:
            if 'C' in group_stats and 'B' in group_stats and group_stats['C'] > group_stats['B']:
                logger.info(f"  ✅ HIPOTÉZIS RÉSZBEN IGAZOLÓDOTT: C > B")
                hypothesis_result = "PARTIALLY_CONFIRMED"
            elif 'C' in group_stats and 'A' in group_stats and group_stats['C'] > group_stats['A']:
                logger.info(f"  ✅ HIPOTÉZIS RÉSZBEN IGAZOLÓDOTT: C > A")
                hypothesis_result = "PARTIALLY_CONFIRMED"
            else:
                logger.info(f"  ❓ HIPOTÉZIS BIZONYTALAN")
                hypothesis_result = "UNCERTAIN"
        else:
            hypothesis_result = "INSUFFICIENT_DATA"
    else:
        logger.info(f"  ❓ Nincs elegendő adat a hipotézis ellenőrzéséhez")
        hypothesis_result = "INSUFFICIENT_DATA"
    
    # ===== RÉSZLETES CSOPORTONKÉNTI STATISZTIKÁK =====
    logger.info(f"\n📈 RÉSZLETES CSOPORTONKÉNTI ELEMZÉS:")
    
    for group in ['A', 'B', 'C']:
        choices = results['group_choice_details'][group]
        if choices:
            hsi_scores = [choice['hsi'] for choice in choices if choice['hsi'] > 0]
            esi_scores = [choice['esi'] for choice in choices if choice['esi'] > 0]
            ppi_scores = [choice['ppi'] for choice in choices if choice['ppi'] > 0]
            
            logger.info(f"\n  📊 {group} csoport részletes statisztikák:")
            logger.info(f"    Választások száma: {len(choices)}")
            
            if hsi_scores:
                logger.info(f"    Átlag HSI: {np.mean(hsi_scores):.1f}")
            if esi_scores:
                logger.info(f"    Átlag ESI: {np.mean(esi_scores):.1f}")
            if ppi_scores:
                logger.info(f"    Átlag PPI: {np.mean(ppi_scores):.1f}")
            
            # Preferencia típusok eloszlása csoportonként
            user_types_in_group = [choice['user_type'] for choice in choices]
            from collections import Counter
            type_counts = Counter(user_types_in_group)
            logger.info(f"    Felhasználó típusok: {dict(type_counts)}")
    
    # ===== TUDOMÁNYOS METRIKÁK SZÁMÍTÁSA =====
    logger.info(f"\n🔬 TUDOMÁNYOS METRIKÁK:")
    
    # Effect size számítás (Cohen's d)
    if 'A' in group_stats and 'C' in group_stats:
        a_scores = results['avg_composite_scores']['A']
        c_scores = results['avg_composite_scores']['C']
        
        if len(a_scores) > 1 and len(c_scores) > 1:
            pooled_std = np.sqrt(((len(a_scores)-1)*np.var(a_scores) + (len(c_scores)-1)*np.var(c_scores)) / (len(a_scores)+len(c_scores)-2))
            cohens_d = (np.mean(c_scores) - np.mean(a_scores)) / pooled_std
            logger.info(f"  📏 Cohen's d (C vs A): {cohens_d:.3f}")
            
            if abs(cohens_d) < 0.2:
                effect_size = "kicsi"
            elif abs(cohens_d) < 0.5:
                effect_size = "közepes"
            else:
                effect_size = "nagy"
            logger.info(f"  📊 Hatásméret: {effect_size}")
    
    # Statisztikai szignifikancia becslés
    logger.info(f"  📋 Minta nagyságok:")
    for group in ['A', 'B', 'C']:
        if results['avg_composite_scores'][group]:
            logger.info(f"    {group} csoport: n={len(results['avg_composite_scores'][group])}")
    
    results['hypothesis_result'] = hypothesis_result
    results['group_statistics'] = group_stats
    
    return results

def export_enhanced_results(results, filename=None):
    """A/B/C csoportonkénti eredmények exportálása"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"abc_greenrec_simulation_{timestamp}.csv"
    
    # Részletes adatok exportálása
    export_rows = []
    for summary in results['session_summaries']:
        base_row = {
            'username': summary['username'],
            'user_type': summary['user_type'],
            'group': summary['group'],
            'total_choices': summary['total_choices'],
            'avg_composite_score': summary['avg_composite_score'],
            'session_duration': summary['session_duration'],
            'hypothesis_result': results.get('hypothesis_result', 'UNKNOWN')
        }
        
        if summary['choices']:
            for i, choice in enumerate(summary['choices']):
                row = base_row.copy()
                row.update({
                    'choice_number': i + 1,
                    'recipe_id': choice['recipe_id'],
                    'recipe_title': choice['recipe_title'],
                    'hsi': choice['hsi'],
                    'esi': choice['esi'], 
                    'ppi': choice['ppi'],
                    'composite_score': choice['composite_score'],
                    'user_preference_score': choice['user_score'],
                    'round_number': choice.get('round_number', i + 1),
                    'recommendation_type': choice.get('recommendation_type', 'unknown'),
                    'choice_timestamp': choice['timestamp']
                })
                export_rows.append(row)
        else:
            export_rows.append(base_row)
    
    df = pd.DataFrame(export_rows)
    df.to_csv(filename, index=False, encoding='utf-8')
    logger.info(f"📁 A/B/C csoportonkénti eredmények exportálva: {filename}")
    
    # Összesítő statisztikák külön fájlba
    summary_filename = filename.replace('.csv', '_summary.csv')
    summary_data = []
    
    for group in ['A', 'B', 'C']:
        if results['avg_composite_scores'][group]:
            summary_data.append({
                'group': group,
                'user_count': results['by_group'][group],
                'total_choices': len(results['group_choice_details'][group]),
                'avg_composite_score': np.mean(results['avg_composite_scores'][group]),
                'std_composite_score': np.std(results['avg_composite_scores'][group]),
                'hypothesis_result': results.get('hypothesis_result', 'UNKNOWN')
            })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(summary_filename, index=False)
    logger.info(f"📊 Összesítő statisztikák: {summary_filename}")
    
    return filename, summary_filename

if __name__ == "__main__":
    # ===== A/B/C CSOPORTONKÉNTI SZIMULÁCIÓ KONFIGURÁCIÓJA =====
    
    logger.info("🚀 A/B/C CSOPORTONKÉNTI GREENREC SZIMULÁCIÓ INDÍTÁSA")
    logger.info("📋 Hipotézis: C (pontszámok + magyarázat) > B (csak pontszámok) > A (kontroll)")
    
    # KONFIGURÁCIÓS OPCIÓK:
    
    # Kis teszt (fejlesztéshez):
    # results = run_enhanced_simulation(user_count=30, max_workers=3, use_parallel=True)
    
    # Közepes teszt (ajánlott):
    results = run_enhanced_simulation(user_count=75, max_workers=4, use_parallel=True)
    
    # Nagy léptékű teszt (ha gyors a Heroku):
    # results = run_enhanced_simulation(user_count=150, max_workers=6, use_parallel=True)
    
    # Eredmények exportálása
    csv_file, summary_file = export_enhanced_results(results)
    
    logger.info(f"\n🎉 A/B/C CSOPORTONKÉNTI SZIMULÁCIÓ BEFEJEZVE!")
    logger.info(f"📄 Részletes eredmények: {csv_file}")
    logger.info(f"📊 Összesítő statisztikák: {summary_file}")
    
    # Végső hipotézis értékelés
    hypothesis_result = results.get('hypothesis_result', 'UNKNOWN')
    if hypothesis_result == 'FULLY_CONFIRMED':
        logger.info(f"🏆 KIVÁLÓ! A hipotézis teljes mértékben igazolódott!")
        logger.info(f"🎯 A magyarázatok és pontszámok láthatósága jelentősen befolyásolja a döntéseket!")
    elif hypothesis_result == 'PARTIALLY_CONFIRMED':
        logger.info(f"✅ JÓ! A hipotézis részben igazolódott!")
        logger.info(f"🎯 A pontszámok/magyarázatok hatása kimutatható!")
    else:
        logger.info(f"📊 Az eredmények további elemzést igényelnek")
    
    logger.info(f"🔬 Következő lépés: Töltsd fel a CSV fájlokat statisztikai elemzésre!")
    logger.info(f"📈 Ajánlott eszközök: Python pandas, R, SPSS, vagy Excel pivot táblák")
