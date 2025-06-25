# services/analytics_service.py
"""
GreenRec Analytics Service
=========================

Analitikai szolgáltatás, amely felelős:
- A/B/C csoport metrikák számításáért
- Tanulási görbék generálásáért
- Viselkedési tracking-ért
- Statisztikai összehasonlításokért
- Export funkciókért
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import logging
from sklearn.metrics import precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)

@dataclass
class SessionMetrics:
    """Egy munkamenet metrikái"""
    session_id: str
    user_group: str  # 'A', 'B', 'C'
    round_number: int
    timestamp: datetime
    
    # Recommendation metrics
    recommendations_shown: int
    recommendations_rated: int
    avg_rating: float
    relevant_items: int  # rating >= 4
    
    # Quality metrics
    precision_at_k: float
    recall_at_k: float
    f1_score_at_k: float
    
    # Diversity metrics
    category_diversity: float
    ingredient_diversity: float
    intra_list_diversity: float
    
    # Sustainability metrics
    avg_sustainability_score: float
    avg_esi_score: float
    avg_hsi_score: float
    avg_ppi_score: float
    
    # Learning metrics
    learning_improvement: float  # F1 javulás az előző körhöz képest
    satisfaction_score: float

@dataclass
class GroupComparison:
    """Csoportok közötti összehasonlítás"""
    group_a_metrics: Dict[str, float]
    group_b_metrics: Dict[str, float] 
    group_c_metrics: Dict[str, float]
    statistical_significance: Dict[str, bool]
    best_performing_group: str
    improvement_percentages: Dict[str, float]

class AnalyticsService:
    """Központi analitikai szolgáltatás"""
    
    def __init__(self):
        self.session_data: List[SessionMetrics] = []
        self.learning_curves: Dict[str, List[float]] = {
            'A': [], 'B': [], 'C': []
        }
        self.behavioral_logs: List[Dict[str, Any]] = []
        
        logger.info("AnalyticsService inicializálva")
    
    def track_session(self, session_metrics: SessionMetrics) -> None:
        """Munkamenet metrikák rögzítése"""
        try:
            self.session_data.append(session_metrics)
            
            # Tanulási görbe frissítése
            group = session_metrics.user_group
            if group in self.learning_curves:
                self.learning_curves[group].append(session_metrics.f1_score_at_k)
            
            logger.info(f"Session tracked: {session_metrics.session_id}, Group: {group}")
            
        except Exception as e:
            logger.error(f"Session tracking hiba: {e}")
            raise
    
    def track_behavior(self, session_id: str, action: str, 
                      context: Dict[str, Any]) -> None:
        """Felhasználói viselkedés tracking"""
        behavior_log = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'context': context
        }
        self.behavioral_logs.append(behavior_log)
        
        logger.debug(f"Behavior tracked: {action} for session {session_id}")
    
    def calculate_group_metrics(self, group: str, 
                              round_filter: Optional[int] = None) -> Dict[str, float]:
        """Csoport átlagos metrikái"""
        try:
            # Szűrés csoportra és körre
            filtered_data = [
                s for s in self.session_data 
                if s.user_group == group
            ]
            
            if round_filter is not None:
                filtered_data = [
                    s for s in filtered_data 
                    if s.round_number == round_filter
                ]
            
            if not filtered_data:
                return self._empty_metrics()
            
            # Átlagos metrikák számítása
            metrics = {
                'avg_precision': np.mean([s.precision_at_k for s in filtered_data]),
                'avg_recall': np.mean([s.recall_at_k for s in filtered_data]),
                'avg_f1_score': np.mean([s.f1_score_at_k for s in filtered_data]),
                'avg_satisfaction': np.mean([s.satisfaction_score for s in filtered_data]),
                'avg_diversity': np.mean([s.intra_list_diversity for s in filtered_data]),
                'avg_sustainability': np.mean([s.avg_sustainability_score for s in filtered_data]),
                'avg_learning_improvement': np.mean([s.learning_improvement for s in filtered_data]),
                'total_sessions': len(filtered_data),
                'completion_rate': len([s for s in filtered_data if s.recommendations_rated >= 6]) / len(filtered_data) * 100
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Group metrics számítási hiba: {e}")
            return self._empty_metrics()
    
    def compare_groups(self, round_number: Optional[int] = None) -> GroupComparison:
        """A/B/C csoportok összehasonlítása"""
        try:
            group_a_metrics = self.calculate_group_metrics('A', round_number)
            group_b_metrics = self.calculate_group_metrics('B', round_number)
            group_c_metrics = self.calculate_group_metrics('C', round_number)
            
            # Statisztikai szignifikancia (egyszerűsített)
            significance = self._calculate_statistical_significance(
                group_a_metrics, group_b_metrics, group_c_metrics
            )
            
            # Legjobb teljesítményű csoport
            best_group = self._determine_best_group(
                group_a_metrics, group_b_metrics, group_c_metrics
            )
            
            # Javulási százalékok
            improvements = self._calculate_improvements(
                group_a_metrics, group_b_metrics, group_c_metrics
            )
            
            return GroupComparison(
                group_a_metrics=group_a_metrics,
                group_b_metrics=group_b_metrics,
                group_c_metrics=group_c_metrics,
                statistical_significance=significance,
                best_performing_group=best_group,
                improvement_percentages=improvements
            )
            
        except Exception as e:
            logger.error(f"Group comparison hiba: {e}")
            raise
    
    def generate_learning_curves(self) -> Dict[str, Any]:
        """Tanulási görbék generálása"""
        try:
            curves_data = {}
            
            for group in ['A', 'B', 'C']:
                group_sessions = [s for s in self.session_data if s.user_group == group]
                
                if not group_sessions:
                    curves_data[group] = {'rounds': [], 'f1_scores': [], 'satisfaction': []}
                    continue
                
                # Körönkénti átlagos F1 és elégedettség
                rounds_data = {}
                for session in group_sessions:
                    round_num = session.round_number
                    if round_num not in rounds_data:
                        rounds_data[round_num] = {'f1_scores': [], 'satisfaction': []}
                    
                    rounds_data[round_num]['f1_scores'].append(session.f1_score_at_k)
                    rounds_data[round_num]['satisfaction'].append(session.satisfaction_score)
                
                # Rendezés kör szerint
                sorted_rounds = sorted(rounds_data.keys())
                
                curves_data[group] = {
                    'rounds': sorted_rounds,
                    'f1_scores': [np.mean(rounds_data[r]['f1_scores']) for r in sorted_rounds],
                    'satisfaction': [np.mean(rounds_data[r]['satisfaction']) for r in sorted_rounds]
                }
            
            return {
                'learning_curves': curves_data,
                'metadata': {
                    'total_sessions': len(self.session_data),
                    'generated_at': datetime.now().isoformat(),
                    'max_rounds': max([s.round_number for s in self.session_data]) if self.session_data else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Learning curves generálási hiba: {e}")
            return {'learning_curves': {}, 'metadata': {}}
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Dashboard számára optimalizált adatok"""
        try:
            dashboard = {
                'summary': {
                    'total_sessions': len(self.session_data),
                    'active_users': len(set([s.session_id for s in self.session_data])),
                    'avg_completion_rate': self._calculate_overall_completion_rate(),
                    'total_ratings': sum([s.recommendations_rated for s in self.session_data])
                },
                'group_performance': {},
                'recent_activity': self._get_recent_activity(),
                'key_insights': self._generate_key_insights()
            }
            
            # Csoportonkénti teljesítmény
            for group in ['A', 'B', 'C']:
                dashboard['group_performance'][group] = self.calculate_group_metrics(group)
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Dashboard data generálási hiba: {e}")
            return {}
    
    def export_analytics_data(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """Analitikai adatok exportálása"""
        try:
            export_data = {
                'metadata': {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_sessions': len(self.session_data),
                    'total_behaviors': len(self.behavioral_logs)
                },
                'session_metrics': [asdict(session) for session in self.session_data],
                'learning_curves': self.learning_curves,
                'behavioral_logs': self.behavioral_logs,
                'group_comparison': asdict(self.compare_groups()),
                'dashboard_summary': self.get_dashboard_data()
            }
            
            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                logger.info(f"Analytics data exportálva: {filepath}")
            
            return export_data
            
        except Exception as e:
            logger.error(f"Export hiba: {e}")
            raise
    
    # Private helper methods
    
    def _empty_metrics(self) -> Dict[str, float]:
        """Üres metrikák alapértelmezett értékekkel"""
        return {
            'avg_precision': 0.0,
            'avg_recall': 0.0,
            'avg_f1_score': 0.0,
            'avg_satisfaction': 0.0,
            'avg_diversity': 0.0,
            'avg_sustainability': 0.0,
            'avg_learning_improvement': 0.0,
            'total_sessions': 0,
            'completion_rate': 0.0
        }
    
    def _calculate_statistical_significance(self, metrics_a: Dict, 
                                          metrics_b: Dict, 
                                          metrics_c: Dict) -> Dict[str, bool]:
        """Egyszerűsített statisztikai szignifikancia számítás"""
        # Valós implementációban t-teszt vagy Mann-Whitney U teszt kellene
        significance = {}
        
        key_metrics = ['avg_f1_score', 'avg_satisfaction', 'avg_diversity']
        
        for metric in key_metrics:
            a_val = metrics_a.get(metric, 0)
            b_val = metrics_b.get(metric, 0)
            c_val = metrics_c.get(metric, 0)
            
            # Egyszerű küszöb alapú "szignifikancia" (demo célra)
            max_val = max(a_val, b_val, c_val)
            min_val = min(a_val, b_val, c_val)
            
            significance[f'{metric}_significant'] = (max_val - min_val) > 0.05
        
        return significance
    
    def _determine_best_group(self, metrics_a: Dict, 
                            metrics_b: Dict, 
                            metrics_c: Dict) -> str:
        """Legjobb teljesítményű csoport meghatározása"""
        # Kompozit pontszám F1 + elégedettség + diverzitás alapján
        score_a = (metrics_a.get('avg_f1_score', 0) + 
                  metrics_a.get('avg_satisfaction', 0) + 
                  metrics_a.get('avg_diversity', 0)) / 3
        
        score_b = (metrics_b.get('avg_f1_score', 0) + 
                  metrics_b.get('avg_satisfaction', 0) + 
                  metrics_b.get('avg_diversity', 0)) / 3
        
        score_c = (metrics_c.get('avg_f1_score', 0) + 
                  metrics_c.get('avg_satisfaction', 0) + 
                  metrics_c.get('avg_diversity', 0)) / 3
        
        scores = {'A': score_a, 'B': score_b, 'C': score_c}
        return max(scores, key=scores.get)
    
    def _calculate_improvements(self, metrics_a: Dict, 
                              metrics_b: Dict, 
                              metrics_c: Dict) -> Dict[str, float]:
        """Javulási százalékok számítása A csoporthoz képest"""
        baseline = metrics_a.get('avg_f1_score', 0.01)  # Prevent division by zero
        
        return {
            'group_b_improvement': ((metrics_b.get('avg_f1_score', 0) - baseline) / baseline * 100),
            'group_c_improvement': ((metrics_c.get('avg_f1_score', 0) - baseline) / baseline * 100)
        }
    
    def _calculate_overall_completion_rate(self) -> float:
        """Összesített befejezési arány"""
        if not self.session_data:
            return 0.0
        
        completed = len([s for s in self.session_data if s.recommendations_rated >= 6])
        return (completed / len(self.session_data)) * 100
    
    def _get_recent_activity(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Legutóbbi aktivitás (demo adatok)"""
        # Valós implementációban időszűrés kellene
        recent = self.session_data[-10:] if len(self.session_data) > 10 else self.session_data
        
        return [
            {
                'session_id': s.session_id[:8],
                'group': s.user_group,
                'round': s.round_number,
                'f1_score': round(s.f1_score_at_k, 3),
                'satisfaction': round(s.satisfaction_score, 1)
            }
            for s in recent
        ]
    
    def _generate_key_insights(self) -> List[str]:
        """Kulcs insights generálása"""
        insights = []
        
        try:
            if len(self.session_data) > 0:
                # Legjobb csoport
                comparison = self.compare_groups()
                best_group = comparison.best_performing_group
                insights.append(f"🏆 A '{best_group}' csoport teljesít a legjobban")
                
                # Tanulási trend
                if len(self.session_data) > 5:
                    recent_f1 = np.mean([s.f1_score_at_k for s in self.session_data[-5:]])
                    early_f1 = np.mean([s.f1_score_at_k for s in self.session_data[:5]])
                    
                    if recent_f1 > early_f1:
                        improvement = ((recent_f1 - early_f1) / early_f1) * 100
                        insights.append(f"📈 {improvement:.1f}% javulás a tanulási teljesítményben")
                    else:
                        insights.append("📊 Stabil tanulási teljesítmény")
                
                # Befejezési arány
                completion_rate = self._calculate_overall_completion_rate()
                if completion_rate > 80:
                    insights.append(f"✅ Magas befejezési arány: {completion_rate:.1f}%")
                elif completion_rate < 50:
                    insights.append(f"⚠️ Alacsony befejezési arány: {completion_rate:.1f}%")
            
            if not insights:
                insights.append("🔄 Adatgyűjtés folyamatban...")
                
        except Exception as e:
            logger.error(f"Insights generálási hiba: {e}")
            insights.append("❌ Insights generálási hiba")
        
        return insights

# Singleton instance
analytics_service = AnalyticsService()

def get_analytics_service() -> AnalyticsService:
    """Analytics service singleton lekérdezése"""
    return analytics_service
