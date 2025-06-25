# utils/metrics.py
"""
GreenRec Metrics Calculation
============================

Metrika számítási függvények a GreenRec ajánlórendszerhez.
Tartalmazza a precision, recall, F1, diverzitás és egyéb performance metrikákat.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Set, Tuple, Any, Optional, Union
from collections import Counter, defaultdict
from dataclasses import dataclass
from sklearn.metrics.pairwise import cosine_similarity
from scipy import stats
import logging
import math

logger = logging.getLogger(__name__)

# =====================================
# Data Classes for Metrics
# =====================================

@dataclass
class RecommendationMetrics:
    """Ajánlási metrikák összesítő osztálya"""
    # Basic metrics
    precision_at_k: Dict[int, float]
    recall_at_k: Dict[int, float]
    f1_score_at_k: Dict[int, float]
    
    # Diversity metrics
    intra_list_diversity: float
    category_diversity: float
    ingredient_diversity: float
    
    # Coverage metrics
    catalog_coverage: float
    user_coverage: float
    
    # Novelty metrics
    avg_popularity: float
    novelty_score: float
    
    # Sustainability metrics
    avg_sustainability_score: float
    sustainability_improvement: float
    
    # User satisfaction
    avg_rating: float
    rating_distribution: Dict[int, int]

@dataclass
class LearningCurvePoint:
    """Tanulási görbe egy pontja"""
    round_number: int
    user_group: str
    precision: float
    recall: float
    f1_score: float
    diversity: float
    satisfaction: float
    sustainability: float
    timestamp: str

@dataclass
class ABTestResults:
    """A/B/C teszt eredmények"""
    group_a_metrics: Dict[str, float]
    group_b_metrics: Dict[str, float]
    group_c_metrics: Dict[str, float]
    statistical_significance: Dict[str, bool]
    effect_sizes: Dict[str, float]
    confidence_intervals: Dict[str, Tuple[float, float]]
    winner_group: str
    improvement_percentage: float

# =====================================
# Precision, Recall, F1 Calculations
# =====================================

def calculate_precision_at_k(recommendations: List[str], 
                            relevant_items: List[str], 
                            k: int) -> float:
    """
    Precision@K számítása
    
    Args:
        recommendations: Ajánlott elemek listája (sorrendben)
        relevant_items: Releváns elemek listája
        k: Top-K érték
        
    Returns:
        Precision@K érték (0.0 - 1.0)
    """
    if not recommendations or k <= 0:
        return 0.0
    
    # Top-K ajánlások
    top_k_recommendations = recommendations[:k]
    relevant_set = set(relevant_items)
    
    # Releváns elemek száma a top-K-ban
    relevant_in_top_k = sum(1 for item in top_k_recommendations if item in relevant_set)
    
    precision = relevant_in_top_k / min(k, len(top_k_recommendations))
    
    logger.debug(f"Precision@{k}: {relevant_in_top_k}/{min(k, len(top_k_recommendations))} = {precision:.3f}")
    
    return precision

def calculate_recall_at_k(recommendations: List[str], 
                         relevant_items: List[str], 
                         k: int) -> float:
    """
    Recall@K számítása
    
    Args:
        recommendations: Ajánlott elemek listája (sorrendben)
        relevant_items: Releváns elemek listája
        k: Top-K érték
        
    Returns:
        Recall@K érték (0.0 - 1.0)
    """
    if not relevant_items:
        return 0.0
    
    if not recommendations or k <= 0:
        return 0.0
    
    # Top-K ajánlások
    top_k_recommendations = recommendations[:k]
    relevant_set = set(relevant_items)
    
    # Releváns elemek száma a top-K-ban
    relevant_in_top_k = sum(1 for item in top_k_recommendations if item in relevant_set)
    
    recall = relevant_in_top_k / len(relevant_items)
    
    logger.debug(f"Recall@{k}: {relevant_in_top_k}/{len(relevant_items)} = {recall:.3f}")
    
    return recall

def calculate_f1_score_at_k(recommendations: List[str], 
                           relevant_items: List[str], 
                           k: int) -> float:
    """
    F1-Score@K számítása
    
    Args:
        recommendations: Ajánlott elemek listája (sorrendben)
        relevant_items: Releváns elemek listája
        k: Top-K érték
        
    Returns:
        F1-Score@K érték (0.0 - 1.0)
    """
    precision = calculate_precision_at_k(recommendations, relevant_items, k)
    recall = calculate_recall_at_k(recommendations, relevant_items, k)
    
    if precision + recall == 0:
        return 0.0
    
    f1_score = 2 * (precision * recall) / (precision + recall)
    
    logger.debug(f"F1@{k}: 2*({precision:.3f}*{recall:.3f})/({precision:.3f}+{recall:.3f}) = {f1_score:.3f}")
    
    return f1_score

def calculate_multiple_k_metrics(recommendations: List[str], 
                                relevant_items: List[str], 
                                k_values: List[int] = None) -> Dict[str, Dict[int, float]]:
    """
    Több K értékre metrikák számítása egyszerre
    
    Args:
        recommendations: Ajánlott elemek listája
        relevant_items: Releváns elemek listája
        k_values: K értékek listája (default: [5, 10, 20])
        
    Returns:
        Metrikák dictionary K értékek szerint
    """
    if k_values is None:
        k_values = [5, 10, 20]
    
    metrics = {
        'precision': {},
        'recall': {},
        'f1_score': {}
    }
    
    for k in k_values:
        metrics['precision'][k] = calculate_precision_at_k(recommendations, relevant_items, k)
        metrics['recall'][k] = calculate_recall_at_k(recommendations, relevant_items, k)
        metrics['f1_score'][k] = calculate_f1_score_at_k(recommendations, relevant_items, k)
    
    return metrics

# =====================================
# Diversity Metrics
# =====================================

def calculate_intra_list_diversity(recommendations: List[Dict[str, Any]], 
                                  similarity_threshold: float = 0.8) -> float:
    """
    Intra-list diverzitás számítása hasonlóság alapján
    
    Args:
        recommendations: Ajánlások metaadatokkal
        similarity_threshold: Hasonlósági küszöb
        
    Returns:
        Diverzitás érték (0.0 - 1.0, magasabb = diverzebb)
    """
    if len(recommendations) <= 1:
        return 1.0
    
    # Szöveges tartalom összeállítása minden ajánláshoz
    texts = []
    for rec in recommendations:
        # Kombináljuk a különböző szöveges mezőket
        text_parts = []
        
        # Név és leírás
        if 'name' in rec:
            text_parts.append(str(rec['name']))
        if 'description' in rec:
            text_parts.append(str(rec['description']))
        
        # Összetevők
        if 'ingredients' in rec:
            if isinstance(rec['ingredients'], list):
                text_parts.extend(rec['ingredients'])
            else:
                text_parts.append(str(rec['ingredients']))
        
        # Kategóriák
        if 'categories' in rec:
            if isinstance(rec['categories'], list):
                text_parts.extend(rec['categories'])
            else:
                text_parts.append(str(rec['categories']))
        
        texts.append(' '.join(text_parts))
    
    # TF-IDF hasonlóság számítása
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        
        if len(set(texts)) <= 1:  # Ha minden szöveg ugyanaz
            return 0.0
        
        vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            stop_words='english'  # Alapvető stop words
        )
        
        tfidf_matrix = vectorizer.fit_transform(texts)
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        # Átlagos pairwise hasonlóság
        n = len(recommendations)
        total_similarity = 0
        pair_count = 0
        
        for i in range(n):
            for j in range(i + 1, n):
                total_similarity += similarity_matrix[i][j]
                pair_count += 1
        
        if pair_count == 0:
            return 1.0
        
        avg_similarity = total_similarity / pair_count
        diversity = 1.0 - avg_similarity  # Diverzitás = 1 - hasonlóság
        
        return max(0.0, min(1.0, diversity))
        
    except Exception as e:
        logger.warning(f"Intra-list diversity calculation failed: {e}")
        # Fallback: egyszerű kategória alapú diverzitás
        return calculate_category_diversity_simple(recommendations)

def calculate_category_diversity(recommendations: List[Dict[str, Any]]) -> float:
    """
    Kategória diverzitás számítása
    
    Args:
        recommendations: Ajánlások kategória információkkal
        
    Returns:
        Kategória diverzitás érték (0.0 - 1.0)
    """
    if not recommendations:
        return 0.0
    
    categories = set()
    
    for rec in recommendations:
        if 'categories' in rec:
            if isinstance(rec['categories'], list):
                categories.update(rec['categories'])
            elif isinstance(rec['categories'], str):
                # Vessző alapú felosztás
                cat_list = [cat.strip() for cat in str(rec['categories']).split(',')]
                categories.update(cat_list)
    
    # Shannon entropy alapú diverzitás
    category_counts = Counter()
    
    for rec in recommendations:
        rec_categories = []
        if 'categories' in rec:
            if isinstance(rec['categories'], list):
                rec_categories = rec['categories']
            elif isinstance(rec['categories'], str):
                rec_categories = [cat.strip() for cat in str(rec['categories']).split(',')]
        
        for cat in rec_categories:
            category_counts[cat] += 1
    
    if not category_counts:
        return 0.0
    
    # Shannon entropy
    total_items = len(recommendations)
    entropy = 0.0
    
    for count in category_counts.values():
        if count > 0:
            prob = count / total_items
            entropy -= prob * math.log2(prob)
    
    # Normalizálás a maximum entrópiával
    max_entropy = math.log2(len(category_counts)) if len(category_counts) > 1 else 1
    
    return entropy / max_entropy if max_entropy > 0 else 0.0

def calculate_category_diversity_simple(recommendations: List[Dict[str, Any]]) -> float:
    """
    Egyszerű kategória diverzitás (egyedi kategóriák aránya)
    
    Args:
        recommendations: Ajánlások
        
    Returns:
        Diverzitás érték
    """
    if not recommendations:
        return 0.0
    
    unique_categories = set()
    total_categories = 0
    
    for rec in recommendations:
        if 'categories' in rec:
            if isinstance(rec['categories'], list):
                unique_categories.update(rec['categories'])
                total_categories += len(rec['categories'])
            elif isinstance(rec['categories'], str):
                cat_list = [cat.strip() for cat in str(rec['categories']).split(',')]
                unique_categories.update(cat_list)
                total_categories += len(cat_list)
    
    if total_categories == 0:
        return 0.0
    
    return len(unique_categories) / max(total_categories, len(recommendations))

def calculate_ingredient_diversity(recommendations: List[Dict[str, Any]]) -> float:
    """
    Összetevő diverzitás számítása
    
    Args:
        recommendations: Ajánlások összetevő információkkal
        
    Returns:
        Összetevő diverzitás érték (0.0 - 1.0)
    """
    if not recommendations:
        return 0.0
    
    all_ingredients = []
    
    for rec in recommendations:
        if 'ingredients' in rec:
            if isinstance(rec['ingredients'], list):
                all_ingredients.extend([ing.lower().strip() for ing in rec['ingredients']])
            elif isinstance(rec['ingredients'], str):
                # Vessző alapú felosztás
                ing_list = [ing.lower().strip() for ing in str(rec['ingredients']).split(',')]
                all_ingredients.extend(ing_list)
    
    if not all_ingredients:
        return 0.0
    
    # Jaccard diverzitás számítása
    unique_ingredients = set(all_ingredients)
    total_ingredients = len(all_ingredients)
    
    # Egyedi összetevők aránya
    diversity = len(unique_ingredients) / total_ingredients
    
    return min(1.0, diversity)

# =====================================
# Coverage and Novelty Metrics
# =====================================

def calculate_catalog_coverage(recommendations: List[str], 
                              total_catalog: List[str]) -> float:
    """
    Katalógus lefedettség számítása
    
    Args:
        recommendations: Ajánlott elemek
        total_catalog: Teljes elérhető katalógus
        
    Returns:
        Lefedettség arány (0.0 - 1.0)
    """
    if not total_catalog:
        return 0.0
    
    recommended_set = set(recommendations)
    catalog_set = set(total_catalog)
    
    covered_items = recommended_set.intersection(catalog_set)
    coverage = len(covered_items) / len(catalog_set)
    
    return coverage

def calculate_novelty_score(recommendations: List[Dict[str, Any]], 
                          popularity_scores: Dict[str, float]) -> float:
    """
    Újdonság (novelty) pontszám számítása népszerűség alapján
    
    Args:
        recommendations: Ajánlások
        popularity_scores: Elemek népszerűségi pontszámai
        
    Returns:
        Novelty score (magasabb = újabb/kevésbé népszerű elemek)
    """
    if not recommendations:
        return 0.0
    
    novelty_scores = []
    
    for rec in recommendations:
        item_id = rec.get('id', rec.get('name', ''))
        
        if item_id in popularity_scores:
            # Novelty = 1 - normalizált népszerűség
            popularity = popularity_scores[item_id]
            novelty = 1.0 - popularity
            novelty_scores.append(novelty)
    
    return np.mean(novelty_scores) if novelty_scores else 0.0

# =====================================
# Sustainability Metrics
# =====================================

def calculate_sustainability_metrics(recommendations: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Fenntarthatósági metrikák számítása
    
    Args:
        recommendations: Ajánlások ESI, HSI, PPI értékekkel
        
    Returns:
        Fenntarthatósági metrikák dictionary
    """
    if not recommendations:
        return {
            'avg_esi': 0.0,
            'avg_hsi': 0.0, 
            'avg_ppi': 0.0,
            'avg_composite': 0.0,
            'sustainability_distribution': {},
            'high_sustainability_ratio': 0.0
        }
    
    esi_scores = []
    hsi_scores = []
    ppi_scores = []
    composite_scores = []
    
    for rec in recommendations:
        # ESI (Environment Score Index) - inverz normalizált
        esi = rec.get('ESI_final', rec.get('esi', 0))
        esi_scores.append(float(esi) if esi is not None else 0.0)
        
        # HSI (Health Score Index)
        hsi = rec.get('HSI', rec.get('hsi', 0))
        hsi_scores.append(float(hsi) if hsi is not None else 0.0)
        
        # PPI (Popularity Index)
        ppi = rec.get('PPI', rec.get('ppi', 0))
        ppi_scores.append(float(ppi) if ppi is not None else 0.0)
        
        # Kompozit pontszám
        composite = rec.get('composite_score', 0)
        composite_scores.append(float(composite) if composite is not None else 0.0)
    
    # Magas fenntarthatóságú elemek aránya (kompozit > 70)
    high_sustainability_count = sum(1 for score in composite_scores if score > 70)
    high_sustainability_ratio = high_sustainability_count / len(recommendations)
    
    # Fenntarthatósági eloszlás
    sustainability_distribution = {
        'low': sum(1 for score in composite_scores if score < 40),
        'medium': sum(1 for score in composite_scores if 40 <= score < 70),
        'high': sum(1 for score in composite_scores if score >= 70)
    }
    
    return {
        'avg_esi': np.mean(esi_scores) if esi_scores else 0.0,
        'avg_hsi': np.mean(hsi_scores) if hsi_scores else 0.0,
        'avg_ppi': np.mean(ppi_scores) if ppi_scores else 0.0,
        'avg_composite': np.mean(composite_scores) if composite_scores else 0.0,
        'sustainability_distribution': sustainability_distribution,
        'high_sustainability_ratio': high_sustainability_ratio
    }

def calculate_sustainability_improvement(current_recommendations: List[Dict[str, Any]], 
                                       previous_recommendations: List[Dict[str, Any]]) -> float:
    """
    Fenntarthatóság javulásának mérése az előző körrel összehasonlítva
    
    Args:
        current_recommendations: Jelenlegi ajánlások
        previous_recommendations: Előző kör ajánlásai
        
    Returns:
        Javulás százaléka (-100 - +100)
    """
    current_metrics = calculate_sustainability_metrics(current_recommendations)
    previous_metrics = calculate_sustainability_metrics(previous_recommendations)
    
    current_avg = current_metrics['avg_composite']
    previous_avg = previous_metrics['avg_composite']
    
    if previous_avg == 0:
        return 0.0
    
    improvement = ((current_avg - previous_avg) / previous_avg) * 100
    return improvement

# =====================================
# Learning Curve Analysis
# =====================================

def track_learning_curve(user_group: str, round_number: int, 
                        recommendations: List[str], relevant_items: List[str],
                        recommendation_data: List[Dict[str, Any]],
                        ratings: List[int]) -> LearningCurvePoint:
    """
    Tanulási görbe pont létrehozása
    
    Args:
        user_group: Felhasználói csoport ('A', 'B', 'C')
        round_number: Tanulási kör száma
        recommendations: Ajánlott elemek
        relevant_items: Releváns elemek
        recommendation_data: Ajánlások részletes adatai
        ratings: Felhasználói értékelések
        
    Returns:
        LearningCurvePoint objektum
    """
    # Basic metrics
    precision = calculate_precision_at_k(recommendations, relevant_items, 10)
    recall = calculate_recall_at_k(recommendations, relevant_items, 10)
    f1_score = calculate_f1_score_at_k(recommendations, relevant_items, 10)
    
    # Diversity
    diversity = calculate_intra_list_diversity(recommendation_data)
    
    # Satisfaction
    satisfaction = np.mean(ratings) / 5.0 if ratings else 0.0  # Normalizálás 0-1-re
    
    # Sustainability
    sustainability_metrics = calculate_sustainability_metrics(recommendation_data)
    sustainability = sustainability_metrics['avg_composite'] / 100.0
    
    return LearningCurvePoint(
        round_number=round_number,
        user_group=user_group,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        diversity=diversity,
        satisfaction=satisfaction,
        sustainability=sustainability,
        timestamp=pd.Timestamp.now().isoformat()
    )

def analyze_learning_progression(curve_points: List[LearningCurvePoint]) -> Dict[str, Any]:
    """
    Tanulási progresszió elemzése
    
    Args:
        curve_points: Tanulási görbe pontok
        
    Returns:
        Progresszió analízis
    """
    if not curve_points:
        return {}
    
    # Sorrendbe rendezés kör szerint
    sorted_points = sorted(curve_points, key=lambda x: x.round_number)
    
    # Trendek számítása
    rounds = [p.round_number for p in sorted_points]
    f1_scores = [p.f1_score for p in sorted_points]
    satisfaction_scores = [p.satisfaction for p in sorted_points]
    
    # Lineáris trend számítása
    f1_trend = 0.0
    satisfaction_trend = 0.0
    
    if len(rounds) > 1:
        f1_slope, _, _, _, _ = stats.linregress(rounds, f1_scores)
        satisfaction_slope, _, _, _, _ = stats.linregress(rounds, satisfaction_scores)
        
        f1_trend = f1_slope
        satisfaction_trend = satisfaction_slope
    
    # Végső vs kezdeti teljesítmény
    initial_f1 = sorted_points[0].f1_score
    final_f1 = sorted_points[-1].f1_score
    
    total_improvement = final_f1 - initial_f1
    
    return {
        'total_rounds': len(sorted_points),
        'f1_trend': f1_trend,
        'satisfaction_trend': satisfaction_trend,
        'total_f1_improvement': total_improvement,
        'learning_rate': total_improvement / len(sorted_points) if len(sorted_points) > 0 else 0,
        'final_performance': {
            'f1_score': final_f1,
            'satisfaction': sorted_points[-1].satisfaction,
            'diversity': sorted_points[-1].diversity
        }
    }

# =====================================
# A/B/C Test Statistical Analysis
# =====================================

def compare_groups_statistically(group_a_data: List[float], 
                                group_b_data: List[float],
                                group_c_data: List[float],
                                alpha: float = 0.05) -> ABTestResults:
    """
    A/B/C csoportok statisztikai összehasonlítása
    
    Args:
        group_a_data: A csoport metrika értékei
        group_b_data: B csoport metrika értékei  
        group_c_data: C csoport metrika értékei
        alpha: Szignifikancia szint
        
    Returns:
        ABTestResults objektum
    """
    # Alapstatisztikák
    group_a_metrics = {
        'mean': np.mean(group_a_data) if group_a_data else 0,
        'std': np.std(group_a_data) if group_a_data else 0,
        'count': len(group_a_data)
    }
    
    group_b_metrics = {
        'mean': np.mean(group_b_data) if group_b_data else 0,
        'std': np.std(group_b_data) if group_b_data else 0,
        'count': len(group_b_data)
    }
    
    group_c_metrics = {
        'mean': np.mean(group_c_data) if group_c_data else 0,
        'std': np.std(group_c_data) if group_c_data else 0,
        'count': len(group_c_data)
    }
    
    # Statisztikai tesztek
    statistical_significance = {}
    effect_sizes = {}
    confidence_intervals = {}
    
    # A vs B összehasonlítás
    if len(group_a_data) > 1 and len(group_b_data) > 1:
        t_stat_ab, p_value_ab = stats.ttest_ind(group_a_data, group_b_data)
        statistical_significance['a_vs_b'] = p_value_ab < alpha
        
        # Cohen's d effect size
        pooled_std = np.sqrt(((len(group_a_data) - 1) * group_a_metrics['std']**2 + 
                             (len(group_b_data) - 1) * group_b_metrics['std']**2) / 
                             (len(group_a_data) + len(group_b_data) - 2))
        
        if pooled_std > 0:
            cohens_d_ab = (group_b_metrics['mean'] - group_a_metrics['mean']) / pooled_std
            effect_sizes['a_vs_b'] = cohens_d_ab
    
    # A vs C összehasonlítás
    if len(group_a_data) > 1 and len(group_c_data) > 1:
        t_stat_ac, p_value_ac = stats.ttest_ind(group_a_data, group_c_data)
        statistical_significance['a_vs_c'] = p_value_ac < alpha
        
        pooled_std = np.sqrt(((len(group_a_data) - 1) * group_a_metrics['std']**2 + 
                             (len(group_c_data) - 1) * group_c_metrics['std']**2) / 
                             (len(group_a_data) + len(group_c_data) - 2))
        
        if pooled_std > 0:
            cohens_d_ac = (group_c_metrics['mean'] - group_a_metrics['mean']) / pooled_std
            effect_sizes['a_vs_c'] = cohens_d_ac
    
    # B vs C összehasonlítás
    if len(group_b_data) > 1 and len(group_c_data) > 1:
        t_stat_bc, p_value_bc = stats.ttest_ind(group_b_data, group_c_data)
        statistical_significance['b_vs_c'] = p_value_bc < alpha
        
        pooled_std = np.sqrt(((len(group_b_data) - 1) * group_b_metrics['std']**2 + 
                             (len(group_c_data) - 1) * group_c_metrics['std']**2) / 
                             (len(group_b_data) + len(group_c_data) - 2))
        
        if pooled_std > 0:
            cohens_d_bc = (group_c_metrics['mean'] - group_b_metrics['mean']) / pooled_std
            effect_sizes['b_vs_c'] = cohens_d_bc
    
    # Legjobb csoport meghatározása
    group_means = {
        'A': group_a_metrics['mean'],
        'B': group_b_metrics['mean'], 
        'C': group_c_metrics['mean']
    }
    
    winner_group = max(group_means, key=group_means.get)
    baseline_mean = group_a_metrics['mean']
    winner_mean = group_means[winner_group]
    
    improvement_percentage = 0.0
    if baseline_mean > 0:
        improvement_percentage = ((winner_mean - baseline_mean) / baseline_mean) * 100
    
    # Konfidencia intervallumok (egyszerűsített)
    for group_name, data, metrics in [('A', group_a_data, group_a_metrics),
                                      ('B', group_b_data, group_b_metrics),
                                      ('C', group_c_data, group_c_metrics)]:
        if len(data) > 1:
            margin_of_error = stats.t.ppf(1 - alpha/2, len(data) - 1) * (metrics['std'] / np.sqrt(len(data)))
            ci_lower = metrics['mean'] - margin_of_error
            ci_upper = metrics['mean'] + margin_of_error
            confidence_intervals[f'group_{group_name.lower()}'] = (ci_lower, ci_upper)
    
    return ABTestResults(
        group_a_metrics=group_a_metrics,
        group_b_metrics=group_b_metrics,
        group_c_metrics=group_c_metrics,
        statistical_significance=statistical_significance,
        effect_sizes=effect_sizes,
        confidence_intervals=confidence_intervals,
        winner_group=winner_group,
        improvement_percentage=improvement_percentage
    )

# =====================================
# Comprehensive Metrics Calculation
# =====================================

def calculate_comprehensive_metrics(recommendations: List[str],
                                  recommendation_data: List[Dict[str, Any]],
                                  relevant_items: List[str],
                                  ratings: List[int],
                                  total_catalog: List[str] = None,
                                  popularity_scores: Dict[str, float] = None) -> RecommendationMetrics:
    """
    Komplex metrikák számítása minden aspektusra
    
    Args:
        recommendations: Ajánlott elemek ID listája
        recommendation_data: Ajánlások részletes adatai
        relevant_items: Releváns elemek (rating >= 4)
        ratings: Felhasználói értékelések
        total_catalog: Teljes elérhető katalógus (opciónal)
        popularity_scores: Népszerűségi pontszámok (opciónal)
        
    Returns:
        RecommendationMetrics objektum minden metrikával
    """
    
    # Basic metrics (Precision, Recall, F1) multiple K values
    k_values = [5, 10, 20]
    basic_metrics = calculate_multiple_k_metrics(recommendations, relevant_items, k_values)
    
    # Diversity metrics
    intra_list_diversity = calculate_intra_list_diversity(recommendation_data)
    category_diversity = calculate_category_diversity(recommendation_data)
    ingredient_diversity = calculate_ingredient_diversity(recommendation_data)
    
    # Coverage metrics
    catalog_coverage = 0.0
    if total_catalog:
        catalog_coverage = calculate_catalog_coverage(recommendations, total_catalog)
    
    user_coverage = len(set(recommendations)) / len(recommendations) if recommendations else 0.0
    
    # Novelty metrics
    avg_popularity = 0.0
    novelty_score = 0.0
    if popularity_scores:
        popularities = [popularity_scores.get(rec_id, 0.5) for rec_id in recommendations]
        avg_popularity = np.mean(popularities) if popularities else 0.0
        novelty_score = calculate_novelty_score(recommendation_data, popularity_scores)
    
    # Sustainability metrics
    sustainability_metrics = calculate_sustainability_metrics(recommendation_data)
    avg_sustainability_score = sustainability_metrics['avg_composite']
    
    # User satisfaction
    avg_rating = np.mean(ratings) if ratings else 0.0
    rating_distribution = Counter(ratings) if ratings else {}
    
    return RecommendationMetrics(
        precision_at_k=basic_metrics['precision'],
        recall_at_k=basic_metrics['recall'],
        f1_score_at_k=basic_metrics['f1_score'],
        intra_list_diversity=intra_list_diversity,
        category_diversity=category_diversity,
        ingredient_diversity=ingredient_diversity,
        catalog_coverage=catalog_coverage,
        user_coverage=user_coverage,
        avg_popularity=avg_popularity,
        novelty_score=novelty_score,
        avg_sustainability_score=avg_sustainability_score,
        sustainability_improvement=0.0,  # Ezt külön kell számítani
        avg_rating=avg_rating,
        rating_distribution=dict(rating_distribution)
    )

# =====================================
# Utility Functions for Metrics
# =====================================

def convert_ratings_to_relevance(ratings: List[int], threshold: int = 4) -> List[str]:
    """
    Értékelések konvertálása releváns elemek listájává
    
    Args:
        ratings: Értékelések listája
        threshold: Relevancia küszöb (>= threshold = releváns)
        
    Returns:
        Releváns elemek ID listája
    """
    relevant_items = []
    
    for i, rating in enumerate(ratings):
        if rating >= threshold:
            relevant_items.append(str(i))  # Index-et használjuk ID-ként
    
    return relevant_items

def normalize_metrics_dict(metrics_dict: Dict[str, float], 
                          max_values: Dict[str, float] = None) -> Dict[str, float]:
    """
    Metrikák normalizálása 0-1 tartományra
    
    Args:
        metrics_dict: Metrikák dictionary
        max_values: Maximum értékek (opciónal)
        
    Returns:
        Normalizált metrikák
    """
    if max_values is None:
        max_values = {key: 1.0 for key in metrics_dict.keys()}
    
    normalized = {}
    
    for key, value in metrics_dict.items():
        max_val = max_values.get(key, 1.0)
        if max_val > 0:
            normalized[key] = min(1.0, max(0.0, value / max_val))
        else:
            normalized[key] = 0.0
    
    return normalized

def calculate_weighted_score(metrics: Dict[str, float], 
                           weights: Dict[str, float]) -> float:
    """
    Súlyozott összpontszám számítása
    
    Args:
        metrics: Metrikák dictionary
        weights: Súlyok dictionary
        
    Returns:
        Súlyozott összpontszám
    """
    total_score = 0.0
    total_weight = 0.0
    
    for metric, value in metrics.items():
        if metric in weights:
            weight = weights[metric]
            total_score += value * weight
            total_weight += weight
    
    return total_score / total_weight if total_weight > 0 else 0.0

def metrics_to_dashboard_format(metrics: RecommendationMetrics) -> Dict[str, Any]:
    """
    Metrikák konvertálása dashboard formátumra
    
    Args:
        metrics: RecommendationMetrics objektum
        
    Returns:
        Dashboard-kompatibilis dictionary
    """
    return {
        'key_metrics': {
            'Precision@10': {
                'value': metrics.precision_at_k.get(10, 0.0),
                'format': 'percentage',
                'description': 'Pontosság az első 10 ajánlásban'
            },
            'F1-Score@10': {
                'value': metrics.f1_score_at_k.get(10, 0.0),
                'format': 'percentage', 
                'description': 'F1 pontszám az első 10 ajánlásban'
            },
            'Diverzitás': {
                'value': metrics.intra_list_diversity,
                'format': 'percentage',
                'description': 'Ajánlások változatossága'
            },
            'Fenntarthatóság': {
                'value': metrics.avg_sustainability_score / 100.0,
                'format': 'percentage',
                'description': 'Átlagos fenntarthatósági pontszám'
            },
            'Elégedettség': {
                'value': metrics.avg_rating / 5.0,
                'format': 'percentage',
                'description': 'Felhasználói elégedettség'
            }
        },
        'detailed_metrics': {
            'precision_scores': metrics.precision_at_k,
            'recall_scores': metrics.recall_at_k,
            'f1_scores': metrics.f1_score_at_k,
            'diversity_scores': {
                'intra_list': metrics.intra_list_diversity,
                'category': metrics.category_diversity,
                'ingredient': metrics.ingredient_diversity
            },
            'sustainability_score': metrics.avg_sustainability_score,
            'rating_distribution': metrics.rating_distribution
        },
        'summary_stats': {
            'total_recommendations': len(metrics.rating_distribution),
            'avg_rating': metrics.avg_rating,
            'coverage': metrics.catalog_coverage,
            'novelty': metrics.novelty_score
        }
    }

def generate_metrics_report(metrics_history: List[RecommendationMetrics],
                          group_name: str = 'Unknown') -> Dict[str, Any]:
    """
    Metrikák alapján jelentés generálása
    
    Args:
        metrics_history: Metrikák időbeli listája
        group_name: Csoport neve
        
    Returns:
        Részletes jelentés dictionary
    """
    if not metrics_history:
        return {'error': 'No metrics data available'}
    
    # Trendek számítása
    f1_scores = [m.f1_score_at_k.get(10, 0.0) for m in metrics_history]
    diversity_scores = [m.intra_list_diversity for m in metrics_history]
    satisfaction_scores = [m.avg_rating / 5.0 for m in metrics_history]
    
    # Statistikák
    def calculate_trend(values):
        if len(values) < 2:
            return 0.0
        return (values[-1] - values[0]) / len(values)
    
    report = {
        'group': group_name,
        'total_sessions': len(metrics_history),
        'performance_trends': {
            'f1_score_trend': calculate_trend(f1_scores),
            'diversity_trend': calculate_trend(diversity_scores),
            'satisfaction_trend': calculate_trend(satisfaction_scores)
        },
        'current_performance': {
            'f1_score': f1_scores[-1] if f1_scores else 0.0,
            'diversity': diversity_scores[-1] if diversity_scores else 0.0,
            'satisfaction': satisfaction_scores[-1] if satisfaction_scores else 0.0,
            'sustainability': metrics_history[-1].avg_sustainability_score / 100.0
        },
        'improvement_analysis': {
            'total_f1_improvement': f1_scores[-1] - f1_scores[0] if len(f1_scores) > 1 else 0.0,
            'total_diversity_improvement': diversity_scores[-1] - diversity_scores[0] if len(diversity_scores) > 1 else 0.0,
            'total_satisfaction_improvement': satisfaction_scores[-1] - satisfaction_scores[0] if len(satisfaction_scores) > 1 else 0.0
        },
        'recommendations': []
    }
    
    # Ajánlások generálása
    current_f1 = f1_scores[-1] if f1_scores else 0.0
    current_diversity = diversity_scores[-1] if diversity_scores else 0.0
    
    if current_f1 < 0.3:
        report['recommendations'].append("F1 pontszám alacsony - javasolt a tanulási algoritmus finomhangolása")
    
    if current_diversity < 0.5:
        report['recommendations'].append("Alacsony diverzitás - több kategóriából ajánljon")
    
    if len(f1_scores) > 1 and calculate_trend(f1_scores) < 0:
        report['recommendations'].append("Csökkenő F1 trend - ellenőrizze a tanulási parametereket")
    
    return report

# =====================================
# Advanced Metrics for Research
# =====================================

def calculate_serendipity_score(recommendations: List[Dict[str, Any]], 
                               user_profile: Dict[str, Any]) -> float:
    """
    Szerencsés felfedezés (serendipity) pontszám számítása
    
    Args:
        recommendations: Ajánlások
        user_profile: Felhasználói profil (preferenciák)
        
    Returns:
        Serendipity score (0.0 - 1.0)
    """
    if not recommendations or not user_profile:
        return 0.0
    
    # Egyszerűsített serendipity: mennyire távol vannak az ajánlások a megszokott preferenciáktól
    user_categories = set(user_profile.get('preferred_categories', []))
    user_ingredients = set(user_profile.get('preferred_ingredients', []))
    
    serendipity_scores = []
    
    for rec in recommendations:
        rec_categories = set(rec.get('categories', []))
        rec_ingredients = set(rec.get('ingredients', []))
        
        # Kategória újdonság
        category_overlap = len(rec_categories.intersection(user_categories))
        category_novelty = 1.0 - (category_overlap / max(len(rec_categories), 1))
        
        # Összetevő újdonság
        ingredient_overlap = len(rec_ingredients.intersection(user_ingredients))
        ingredient_novelty = 1.0 - (ingredient_overlap / max(len(rec_ingredients), 1))
        
        # Kombinált serendipity
        item_serendipity = (category_novelty + ingredient_novelty) / 2
        serendipity_scores.append(item_serendipity)
    
    return np.mean(serendipity_scores) if serendipity_scores else 0.0

def calculate_fairness_metrics(recommendations_by_group: Dict[str, List[Dict[str, Any]]]) -> Dict[str, float]:
    """
    Méltányossági metrikák számítása csoportok között
    
    Args:
        recommendations_by_group: Ajánlások csoportonként
        
    Returns:
        Fairness metrikák
    """
    if not recommendations_by_group:
        return {}
    
    # Átlagos pontszámok csoportonként
    group_scores = {}
    
    for group, recommendations in recommendations_by_group.items():
        if recommendations:
            sustainability_scores = [rec.get('composite_score', 0) for rec in recommendations]
            group_scores[group] = np.mean(sustainability_scores)
    
    if len(group_scores) < 2:
        return {'fairness_score': 1.0}
    
    # Fairness = 1 - (max_difference / max_possible_difference)
    scores = list(group_scores.values())
    max_diff = max(scores) - min(scores)
    max_possible_diff = 100.0  # Assuming 0-100 scale
    
    fairness_score = 1.0 - (max_diff / max_possible_diff)
    
    return {
        'fairness_score': fairness_score,
        'group_scores': group_scores,
        'max_difference': max_diff
    }

# =====================================
# Export and Utility Functions
# =====================================

def export_metrics_to_csv(metrics_list: List[RecommendationMetrics], 
                         filename: str) -> bool:
    """
    Metrikák exportálása CSV fájlba
    
    Args:
        metrics_list: Metrikák listája
        filename: Kimeneti fájl neve
        
    Returns:
        True ha sikeres
    """
    try:
        # Flatten metrics for CSV
        flattened_data = []
        
        for i, metrics in enumerate(metrics_list):
            row = {
                'session_id': i,
                'precision_at_5': metrics.precision_at_k.get(5, 0.0),
                'precision_at_10': metrics.precision_at_k.get(10, 0.0),
                'precision_at_20': metrics.precision_at_k.get(20, 0.0),
                'recall_at_5': metrics.recall_at_k.get(5, 0.0),
                'recall_at_10': metrics.recall_at_k.get(10, 0.0),
                'recall_at_20': metrics.recall_at_k.get(20, 0.0),
                'f1_score_at_5': metrics.f1_score_at_k.get(5, 0.0),
                'f1_score_at_10': metrics.f1_score_at_k.get(10, 0.0),
                'f1_score_at_20': metrics.f1_score_at_k.get(20, 0.0),
                'intra_list_diversity': metrics.intra_list_diversity,
                'category_diversity': metrics.category_diversity,
                'ingredient_diversity': metrics.ingredient_diversity,
                'catalog_coverage': metrics.catalog_coverage,
                'novelty_score': metrics.novelty_score,
                'avg_sustainability_score': metrics.avg_sustainability_score,
                'avg_rating': metrics.avg_rating
            }
            flattened_data.append(row)
        
        df = pd.DataFrame(flattened_data)
        df.to_csv(filename, index=False)
        
        logger.info(f"Metrics exported to {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to export metrics to CSV: {e}")
        return False

# =====================================
# Main Export List
# =====================================

__all__ = [
    # Data classes
    'RecommendationMetrics', 'LearningCurvePoint', 'ABTestResults',
    
    # Basic metrics
    'calculate_precision_at_k', 'calculate_recall_at_k', 'calculate_f1_score_at_k',
    'calculate_multiple_k_metrics',
    
    # Diversity metrics
    'calculate_intra_list_diversity', 'calculate_category_diversity', 'calculate_ingredient_diversity',
    
    # Coverage and novelty
    'calculate_catalog_coverage', 'calculate_novelty_score',
    
    # Sustainability
    'calculate_sustainability_metrics', 'calculate_sustainability_improvement',
    
    # Learning curve analysis
    'track_learning_curve', 'analyze_learning_progression',
    
    # Statistical analysis
    'compare_groups_statistically',
    
    # Comprehensive analysis
    'calculate_comprehensive_metrics',
    
    # Utility functions
    'convert_ratings_to_relevance', 'normalize_metrics_dict', 'calculate_weighted_score',
    'metrics_to_dashboard_format', 'generate_metrics_report',
    
    # Advanced metrics
    'calculate_serendipity_score', 'calculate_fairness_metrics',
    
    # Export functions
    'export_metrics_to_csv'
]
