"""
visualizations.py - GreenRec Ajánlórendszer Vizualizációs Modul
Matplotlib, Seaborn és Scipy alapú grafikonok és statisztikai elemzések
"""

import io
import base64
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for web
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import chi2_contingency, kruskal
import logging

logger = logging.getLogger(__name__)

# Seaborn stílus beállítás
sns.set_style("whitegrid")
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 10

class GreenRecVisualizer:
    """
    Vizualizációs osztály a GreenRec ajánlórendszer eredményeinek
    megjelenítéséhez matplotlib, seaborn és scipy használatával
    """
    
    def __init__(self):
        self.colors = {
            'A': '#ff6b6b',  # Piros - Kontroll csoport
            'B': '#4ecdc4',  # Türkiz - Pontszámos csoport  
            'C': '#45b7d1'   # Kék - Magyarázatos csoport
        }
        
    def _fig_to_base64(self, fig):
        """Matplotlib figure konvertálása base64 string-gé webes megjelenítéshez"""
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close(fig)
        return f"data:image/png;base64,{img_str}"
    
    def group_distribution_chart(self, group_stats):
        """
        A/B/C csoportok felhasználószám eloszlásának vizualizációja
        matplotlib + seaborn használatával
        """
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
            
            # Adatok előkészítése
            groups = [stat['group'] for stat in group_stats]
            user_counts = [stat['user_count'] for stat in group_stats]
            colors = [self.colors.get(group, '#gray') for group in groups]
            
            # 1. Oszlopdiagram - Felhasználók száma csoportonként
            bars = ax1.bar(groups, user_counts, color=colors, alpha=0.8, edgecolor='black')
            ax1.set_title('👥 Felhasználók száma A/B/C csoportonként', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Tesztcsoport')
            ax1.set_ylabel('Felhasználók száma')
            ax1.grid(True, alpha=0.3)
            
            # Értékek megjelenítése az oszlopok tetején
            for bar, count in zip(bars, user_counts):
                ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                        str(count), ha='center', va='bottom', fontweight='bold')
            
            # 2. Kördiagram - Arányok
            ax2.pie(user_counts, labels=[f'{g} csoport\n({c} fő)' for g, c in zip(groups, user_counts)],
                   colors=colors, autopct='%1.1f%%', startangle=90)
            ax2.set_title('📊 Csoportok aránya', fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"❌ Group distribution chart hiba: {e}")
            return None
    
    def composite_score_analysis(self, choice_data):
        """
        Kompozit pontszámok elemzése csoportonként
        scipy statisztikai tesztekkel
        """
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # DataFrame készítése
            df = pd.DataFrame(choice_data)
            
            # 1. Boxplot - Kompozit pontszámok eloszlása csoportonként
            sns.boxplot(data=df, x='group', y='composite_score', ax=ax1, palette=self.colors)
            ax1.set_title('📈 Kompozit pontszámok eloszlása csoportonként', fontweight='bold')
            ax1.set_xlabel('Tesztcsoport')
            ax1.set_ylabel('Kompozit pontszám')
            
            # 2. Violin plot - Részletesebb eloszlás
            sns.violinplot(data=df, x='group', y='composite_score', ax=ax2, palette=self.colors)
            ax2.set_title('🎻 Pontszám-eloszlás részletesen', fontweight='bold')
            ax2.set_xlabel('Tesztcsoport')
            ax2.set_ylabel('Kompozit pontszám')
            
            # 3. Hisztogram - Összehasonlítás
            for group in df['group'].unique():
                group_data = df[df['group'] == group]['composite_score']
                ax3.hist(group_data, alpha=0.7, label=f'{group} csoport', 
                        color=self.colors.get(group), bins=15)
            ax3.set_title('📊 Kompozit pontszámok gyakorisága', fontweight='bold')
            ax3.set_xlabel('Kompozit pontszám')
            ax3.set_ylabel('Gyakoriság')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # 4. Statisztikai összehasonlítás
            group_scores = [df[df['group'] == g]['composite_score'].values for g in ['A', 'B', 'C']]
            
            # Kruskal-Wallis teszt (nem parametrikus ANOVA)
            try:
                kruskal_stat, kruskal_p = kruskal(*[scores for scores in group_scores if len(scores) > 0])
                
                # Átlagok és szórások számítása
                stats_text = "📊 Statisztikai összefoglaló:\n\n"
                for group in ['A', 'B', 'C']:
                    group_data = df[df['group'] == group]['composite_score']
                    if len(group_data) > 0:
                        stats_text += f"{group} csoport:\n"
                        stats_text += f"  Átlag: {group_data.mean():.2f}\n"
                        stats_text += f"  Szórás: {group_data.std():.2f}\n"
                        stats_text += f"  Elemszám: {len(group_data)}\n\n"
                
                stats_text += f"Kruskal-Wallis teszt:\n"
                stats_text += f"H = {kruskal_stat:.3f}\n"
                stats_text += f"p-érték = {kruskal_p:.3f}\n"
                
                if kruskal_p < 0.05:
                    stats_text += "✅ Szignifikáns különbség!"
                else:
                    stats_text += "❌ Nincs szignifikáns különbség"
                    
            except Exception as e:
                stats_text = f"Statisztikai teszt hiba: {e}"
            
            ax4.text(0.1, 0.5, stats_text, transform=ax4.transAxes, 
                    fontsize=11, verticalalignment='center', 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
            ax4.set_title('📈 Statisztikai teszt eredményei', fontweight='bold')
            ax4.axis('off')
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"❌ Composite score analysis hiba: {e}")
            return None
    
    def hsi_esi_ppi_breakdown(self, choice_data):
        """
        HSI, ESI, PPI pontszámok részletes elemzése
        """
        try:
            fig, axes = plt.subplots(2, 3, figsize=(18, 10))
            df = pd.DataFrame(choice_data)
            
            metrics = ['hsi', 'esi', 'ppi']
            metric_names = ['HSI (Egészség)', 'ESI (Környezet)', 'PPI (Népszerűség)']
            
            # Felső sor: Boxplotok
            for i, (metric, name) in enumerate(zip(metrics, metric_names)):
                sns.boxplot(data=df, x='group', y=metric, ax=axes[0, i], palette=self.colors)
                axes[0, i].set_title(f'{name} - Csoportonként', fontweight='bold')
                axes[0, i].set_xlabel('Tesztcsoport')
                axes[0, i].set_ylabel('Pontszám')
            
            # Alsó sor: Heatmap - Korrelációs mátrix
            correlation_data = []
            for group in ['A', 'B', 'C']:
                group_df = df[df['group'] == group]
                if len(group_df) > 1:
                    corr_matrix = group_df[['hsi', 'esi', 'ppi', 'composite_score']].corr()
                    correlation_data.append(corr_matrix)
            
            if correlation_data:
                # Átlagos korreláció számítása
                avg_corr = sum(correlation_data) / len(correlation_data)
                
                sns.heatmap(avg_corr, annot=True, cmap='coolwarm', center=0,
                           ax=axes[1, 0], cbar_kws={'shrink': 0.8})
                axes[1, 0].set_title('🔥 Pontszámok korrelációja', fontweight='bold')
            
            # Átlagok összehasonlítása
            group_means = df.groupby('group')[metrics].mean()
            
            x_pos = np.arange(len(metrics))
            width = 0.25
            
            for i, group in enumerate(['A', 'B', 'C']):
                if group in group_means.index:
                    values = group_means.loc[group].values
                    axes[1, 1].bar(x_pos + i * width, values, width, 
                                  label=f'{group} csoport', color=self.colors[group], alpha=0.8)
            
            axes[1, 1].set_title('📊 Átlagos pontszámok összehasonlítása', fontweight='bold')
            axes[1, 1].set_xlabel('Metrikák')
            axes[1, 1].set_ylabel('Átlagos pontszám')
            axes[1, 1].set_xticks(x_pos + width)
            axes[1, 1].set_xticklabels(metric_names, rotation=45)
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
            
            # Összesített statisztikák
            stats_summary = "📈 HSI/ESI/PPI Összefoglaló:\n\n"
            for group in ['A', 'B', 'C']:
                group_data = df[df['group'] == group]
                if len(group_data) > 0:
                    stats_summary += f"{group} csoport ({len(group_data)} választás):\n"
                    stats_summary += f"  HSI átlag: {group_data['hsi'].mean():.1f}\n"
                    stats_summary += f"  ESI átlag: {group_data['esi'].mean():.1f}\n"
                    stats_summary += f"  PPI átlag: {group_data['ppi'].mean():.1f}\n\n"
            
            axes[1, 2].text(0.1, 0.5, stats_summary, transform=axes[1, 2].transAxes,
                           fontsize=10, verticalalignment='center',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
            axes[1, 2].set_title('📋 Statisztikai összefoglaló', fontweight='bold')
            axes[1, 2].axis('off')
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"❌ HSI/ESI/PPI breakdown hiba: {e}")
            return None
    
    def choice_timeline_analysis(self, choice_data):
        """
        Választási idővonal elemzése - időbeli trendek
        """
        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
            
            df = pd.DataFrame(choice_data)
            df['chosen_at'] = pd.to_datetime(df['chosen_at'])
            df['hour'] = df['chosen_at'].dt.hour
            df['day_of_week'] = df['chosen_at'].dt.day_name()
            
            # 1. Választások órában
            hourly_data = df.groupby(['hour', 'group']).size().reset_index(name='count')
            
            for group in ['A', 'B', 'C']:
                group_data = hourly_data[hourly_data['group'] == group]
                if not group_data.empty:
                    ax1.plot(group_data['hour'], group_data['count'], 
                           marker='o', label=f'{group} csoport', 
                           color=self.colors[group], linewidth=2)
            
            ax1.set_title('⏰ Választások időbeli eloszlása (óránként)', fontweight='bold')
            ax1.set_xlabel('Nap órája')
            ax1.set_ylabel('Választások száma')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.set_xticks(range(0, 24, 2))
            
            # 2. Kompozit pontszámok időbeli változása
            df_sorted = df.sort_values('chosen_at')
            df_sorted['choice_order'] = range(len(df_sorted))
            
            # Mozgóátlag számítása (rolling average)
            window_size = max(5, len(df_sorted) // 20)  # Adaptív ablakméret
            
            for group in ['A', 'B', 'C']:
                group_data = df_sorted[df_sorted['group'] == group]
                if len(group_data) >= window_size:
                    rolling_avg = group_data['composite_score'].rolling(window=window_size, min_periods=1).mean()
                    ax2.plot(group_data['choice_order'], rolling_avg,
                           label=f'{group} csoport (mozgóátlag)', 
                           color=self.colors[group], linewidth=2)
            
            ax2.set_title('📈 Kompozit pontszámok trendje időben', fontweight='bold')
            ax2.set_xlabel('Választási sorrend')
            ax2.set_ylabel('Kompozit pontszám (mozgóátlag)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"❌ Choice timeline analysis hiba: {e}")
            return None
    
    def export_statistical_report(self, choice_data, group_stats):
        """
        Részletes statisztikai jelentés generálása scipy használatával
        """
        try:
            report = {
                'timestamp': pd.Timestamp.now().isoformat(),
                'total_choices': len(choice_data),
                'groups_analyzed': len(group_stats)
            }
            
            df = pd.DataFrame(choice_data)
            
            # Alapvető leíró statisztikák
            report['descriptive_stats'] = {}
            for group in ['A', 'B', 'C']:
                group_data = df[df['group'] == group]['composite_score']
                if len(group_data) > 0:
                    report['descriptive_stats'][group] = {
                        'count': len(group_data),
                        'mean': float(group_data.mean()),
                        'std': float(group_data.std()),
                        'median': float(group_data.median()),
                        'min': float(group_data.min()),
                        'max': float(group_data.max()),
                        'q25': float(group_data.quantile(0.25)),
                        'q75': float(group_data.quantile(0.75))
                    }
            
            # Statisztikai tesztek
            group_scores = [df[df['group'] == g]['composite_score'].values for g in ['A', 'B', 'C']]
            valid_groups = [scores for scores in group_scores if len(scores) > 0]
            
            if len(valid_groups) >= 2:
                try:
                    # Kruskal-Wallis teszt
                    kruskal_stat, kruskal_p = kruskal(*valid_groups)
                    report['kruskal_wallis'] = {
                        'statistic': float(kruskal_stat),
                        'p_value': float(kruskal_p),
                        'significant': kruskal_p < 0.05
                    }
                    
                    # Páronkénti t-tesztek
                    report['pairwise_tests'] = {}
                    groups = ['A', 'B', 'C']
                    for i in range(len(groups)):
                        for j in range(i+1, len(groups)):
                            g1, g2 = groups[i], groups[j]
                            data1 = df[df['group'] == g1]['composite_score']
                            data2 = df[df['group'] == g2]['composite_score']
                            
                            if len(data1) > 0 and len(data2) > 0:
                                t_stat, t_p = stats.ttest_ind(data1, data2)
                                report['pairwise_tests'][f'{g1}_vs_{g2}'] = {
                                    'statistic': float(t_stat),
                                    'p_value': float(t_p),
                                    'significant': t_p < 0.05
                                }
                
                except Exception as e:
                    report['statistical_tests_error'] = str(e)
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Statistical report export hiba: {e}")
            return {'error': str(e)}

# Globális visualizer instance
visualizer = GreenRecVisualizer()
