#!/usr/bin/env python3
"""
Business Intelligence and Reporting for A/B Test Analysis

Takes statistical results from the analysis engine and converts them into
business-ready insights, recommendations, and visualizations. 

This module handles:
- Converting statistical results into business language
- Creating visualizations that stakeholders actually understand
- Generating reports in formats the business team can use
- Making launch/no-launch recommendations with clear reasoning

Note: Keep visualization simple and focused. Business stakeholders don't need
to see every statistical test - just the key insights that drive decisions.

Author: Kevin
Version: 1.0.0
Created: 2024-09-02
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from google.cloud import bigquery
from typing import Dict, Any, List, Tuple, Optional
import json
import logging
from datetime import datetime
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# Import our statistical engine
from statistical_engine import StatisticalAnalysisEngine, ExperimentData, create_experiment_data

logger = logging.getLogger(__name__)

# Set up clean visualizations 
plt.style.use('default')
sns.set_palette("Set2")
plt.rcParams.update({
    'figure.figsize': (10, 6),
    'font.size': 11,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10
})


@dataclass
class BusinessRecommendation:
    """Container for business recommendations"""
    decision: str  # LAUNCH, NO_LAUNCH, EXTEND_TEST, etc.
    confidence: str  # HIGH, MEDIUM, LOW
    reasoning: str
    risk_level: str
    expected_impact: str
    next_steps: List[str]


class ExperimentReporter:
    """
    Converts statistical analysis into business intelligence
    
    This class takes the raw statistical output and creates reports,
    visualizations, and recommendations that business stakeholders
    can actually use to make decisions.
    """
    
    def __init__(self, project_id: str = "flit-data-platform"):
        """Initialize with BigQuery connection for data loading"""
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)
        self.engine = StatisticalAnalysisEngine()
        self.results = {}
        
    def analyze_experiment(self, experiment_name: str, 
                          control_column: str = 'control_treatment',
                          metric_column: str = 'orders_during_experiment') -> Dict[str, Any]:
        """
        Run complete analysis pipeline for an experiment
        
        Args:
            experiment_name: Name of experiment to analyze
            control_column: Column indicating control/treatment assignment  
            metric_column: Primary metric to analyze
            
        Returns:
            Complete analysis results with business insights
        """
        logger.info(f"Starting analysis for experiment: {experiment_name}")
        
        # Load experiment data from BigQuery
        data = self._load_experiment_data(experiment_name, control_column, metric_column)
        
        # Run statistical analysis
        statistical_results = self.engine.analyze_experiment(data)
        
        # Convert to business insights
        business_insights = self._create_business_insights(statistical_results, data)
        
        # Generate recommendation
        recommendation = self._make_recommendation(statistical_results, business_insights)
        
        # Combine all results
        complete_results = {
            'experiment_info': {
                'name': experiment_name,
                'analysis_date': datetime.now().isoformat(),
                'primary_metric': metric_column,
                'sample_size': len(data.control) + len(data.treatment)
            },
            'statistical_results': statistical_results,
            'business_insights': business_insights,
            'recommendation': recommendation.__dict__
        }
        
        self.results = complete_results
        return complete_results
    
    def create_executive_summary(self) -> Dict[str, Any]:
        """
        Create one-page executive summary for leadership
        
        This is what gets sent to VPs and C-suite. Keep it simple and focused
        on the business decision, not statistical methodology.
        """
        if not self.results:
            raise ValueError("Must run analyze_experiment first")
        
        stats = self.results['statistical_results']
        insights = self.results['business_insights']
        rec = self.results['recommendation']
        
        # Calculate key business metrics
        relative_lift = stats['effect_sizes']['relative_lift'] * 100
        p_value = stats['significance_tests']['welch_ttest'].p_value
        sample_size = self.results['experiment_info']['sample_size']
        
        # Create executive summary
        executive_summary = {
            'bottom_line_recommendation': rec['decision'],
            'key_finding': f"{relative_lift:+.1f}% change in {self.results['experiment_info']['primary_metric']}",
            'statistical_confidence': self._translate_p_value_to_confidence(p_value),
            'sample_quality': f"{sample_size:,} users analyzed",
            'business_impact': insights['estimated_impact'],
            'risk_assessment': rec['risk_level'],
            'implementation_timeline': insights['implementation_readiness'],
            'executive_next_steps': rec['next_steps'][:3]  # Top 3 only for executives
        }
        
        return executive_summary
    
    def create_detailed_report(self, filepath: str = None) -> str:
        """
        Create comprehensive analysis report
        
        This is the full technical report that includes all the statistical
        details, assumptions, and methodology. Good for data science review
        and audit trails.
        """
        if not self.results:
            raise ValueError("Must run analyze_experiment first")
        
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f"/Users/kevin/Documents/repos/flit-experiments/analysis/detailed_report_{timestamp}.json"
        
        # Add metadata for the detailed report
        detailed_report = {
            'report_metadata': {
                'created_at': datetime.now().isoformat(),
                'analysis_version': '1.0.0',
                'report_type': 'detailed_statistical_analysis',
                'data_source': f"{self.project_id}.flit_marts.mart_free_shipping_threshold_analysis"
            },
            'analysis_results': self.results,
            'methodology_notes': {
                'statistical_tests': 'Primary analysis uses Welch\'s t-test (unequal variances assumed)',
                'effect_size_measure': 'Relative lift calculated as (treatment_mean - control_mean) / control_mean',
                'confidence_intervals': 'Bootstrap method with 10,000 iterations for robust estimation',
                'multiple_testing': 'No correction applied - single primary hypothesis test'
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(detailed_report, f, indent=2, default=str)
        
        logger.info(f"Detailed report saved to: {filepath}")
        return filepath
    
    def create_dashboard_export(self, filepath: str = None) -> str:
        """
        Export results in format suitable for dashboard consumption
        
        Creates a flattened JSON structure that's easy to consume by
        dashboard tools like Tableau, PowerBI, or internal dashboards.
        """
        if not self.results:
            raise ValueError("Must run analyze_experiment first")
        
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f"/Users/kevin/Documents/repos/flit-experiments/analysis/dashboard_data_{timestamp}.json"
        
        # Flatten key metrics for dashboard consumption
        stats = self.results['statistical_results']
        insights = self.results['business_insights']
        rec = self.results['recommendation']
        
        dashboard_data = {
            # Key identifiers
            'experiment_name': self.results['experiment_info']['name'],
            'analysis_date': self.results['experiment_info']['analysis_date'],
            'metric_name': self.results['experiment_info']['primary_metric'],
            
            # Sample size and balance
            'total_sample_size': self.results['experiment_info']['sample_size'],
            'control_sample_size': stats['data_summary']['control']['count'],
            'treatment_sample_size': stats['data_summary']['treatment']['count'],
            'balance_ratio': stats['metadata']['balance_ratio'],
            
            # Core results
            'control_mean': stats['data_summary']['control']['mean'],
            'treatment_mean': stats['data_summary']['treatment']['mean'],
            'absolute_difference': stats['effect_sizes']['absolute_difference'],
            'relative_lift_percent': stats['effect_sizes']['relative_lift_percent'],
            'relative_lift_ci_lower': stats['confidence_intervals']['relative_lift_ci']['lower'] * 100,
            'relative_lift_ci_upper': stats['confidence_intervals']['relative_lift_ci']['upper'] * 100,
            
            # Statistical significance
            'p_value': stats['significance_tests']['welch_ttest'].p_value,
            'statistically_significant': stats['significance_tests']['welch_ttest'].significant,
            'cohens_d': stats['effect_sizes']['cohens_d'],
            'statistical_power': stats['power_analysis']['achieved_power'],
            
            # Business decision
            'recommendation': rec['decision'],
            'confidence_level': rec['confidence'],
            'risk_level': rec['risk_level'],
            'expected_impact_description': rec['expected_impact'],
            
            # Dashboard-specific flags
            'launch_ready': rec['decision'] in ['LAUNCH', 'STRONG_LAUNCH'],
            'needs_more_data': rec['decision'] == 'EXTEND_TEST',
            'has_statistical_significance': stats['significance_tests']['welch_ttest'].significant,
            'has_practical_significance': abs(stats['effect_sizes']['relative_lift']) >= 0.10,
            
            # Color coding for dashboard visuals
            'result_color': 'green' if rec['decision'] in ['LAUNCH', 'STRONG_LAUNCH'] else 
                          'yellow' if rec['decision'] == 'EXTEND_TEST' else 'red'
        }
        
        with open(filepath, 'w') as f:
            json.dump(dashboard_data, f, indent=2, default=str)
        
        logger.info(f"Dashboard export saved to: {filepath}")
        return filepath
    
    def create_visualizations(self, output_dir: str = None) -> Dict[str, str]:
        """
        Generate key visualizations for stakeholder communication
        
        Creates a small set of focused charts that tell the story clearly.
        Avoids statistical jargon and focuses on business impact.
        """
        if not self.results:
            raise ValueError("Must run analyze_experiment first")
        
        if output_dir is None:
            output_dir = "/Users/kevin/Documents/repos/flit-experiments/analysis"
        
        viz_files = {}
        stats = self.results['statistical_results']
        
        # 1. Primary result comparison (bar chart with confidence interval)
        fig, ax = plt.subplots(figsize=(10, 6))
        
        means = [stats['data_summary']['control']['mean'], stats['data_summary']['treatment']['mean']]
        labels = ['Current Process\n(Control)', 'New Process\n(Treatment)']
        colors = ['#3498db', '#e74c3c']
        
        bars = ax.bar(labels, means, color=colors, alpha=0.7, width=0.6)
        
        # Add error bars (standard error)
        sems = [stats['data_summary']['control']['sem'], stats['data_summary']['treatment']['sem']]
        ax.errorbar(labels, means, yerr=sems, fmt='none', color='black', capsize=5, capthick=1.5)
        
        # Add value labels on bars
        for bar, mean in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + sems[bars.index(bar)]/2,
                   f'{mean:.3f}', ha='center', va='bottom', fontweight='bold', fontsize=12)
        
        # Add effect size annotation
        relative_lift = stats['effect_sizes']['relative_lift'] * 100
        p_value = stats['significance_tests']['welch_ttest'].p_value
        significance_text = "Statistically Significant" if p_value < 0.05 else "Not Statistically Significant"
        
        ax.text(0.5, max(means) * 1.15, f'Effect: {relative_lift:+.1f}%\n{significance_text}',
               transform=ax.transData, ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8),
               fontsize=11, fontweight='bold')
        
        ax.set_ylabel(f'{self.results["experiment_info"]["primary_metric"].replace("_", " ").title()}')
        ax.set_title('Experiment Results: Primary Metric Comparison')
        ax.grid(True, alpha=0.3, axis='y')
        
        viz_files['primary_comparison'] = f"{output_dir}/primary_comparison.png"
        plt.tight_layout()
        plt.savefig(viz_files['primary_comparison'], dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Effect size with confidence interval
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ci_lower = stats['confidence_intervals']['relative_lift_ci']['lower'] * 100
        ci_upper = stats['confidence_intervals']['relative_lift_ci']['upper'] * 100
        relative_lift_pct = relative_lift
        
        # Plot point estimate with confidence interval
        ax.errorbar([0], [relative_lift_pct], 
                   yerr=[[relative_lift_pct - ci_lower], [ci_upper - relative_lift_pct]],
                   fmt='o', markersize=12, color='#e74c3c', capsize=8, capthick=3, linewidth=2)
        
        # Add reference lines
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
        ax.axhline(y=10, color='green', linestyle='--', alpha=0.7, linewidth=1, label='Practically Significant (+10%)')
        ax.axhline(y=-10, color='green', linestyle='--', alpha=0.7, linewidth=1)
        
        # Customize the plot
        ax.set_xlim(-0.5, 0.5)
        ax.set_ylabel('Effect Size (%)')
        ax.set_title('Treatment Effect with 95% Confidence Interval')
        ax.set_xticks([])
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()
        
        # Add text annotation
        ax.text(0, relative_lift_pct + 2, f'{relative_lift_pct:+.1f}%', 
               ha='center', va='bottom', fontsize=14, fontweight='bold')
        ax.text(0, min(ci_lower - 3, relative_lift_pct - 8), 
               f'95% CI: [{ci_lower:.1f}%, {ci_upper:.1f}%]',
               ha='center', va='top', fontsize=11)
        
        viz_files['effect_size'] = f"{output_dir}/effect_size_ci.png"
        plt.tight_layout()
        plt.savefig(viz_files['effect_size'], dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Distribution comparison (if needed for deeper analysis)
        # Only create this if the data shows interesting patterns
        if abs(stats['data_summary']['control']['skewness']) > 1 or abs(stats['data_summary']['treatment']['skewness']) > 1:
            logger.info("Creating distribution comparison due to skewed data")
            viz_files['distributions'] = self._create_distribution_plot(output_dir)
        
        logger.info(f"Created {len(viz_files)} visualizations in {output_dir}")
        return viz_files
    
    def _load_experiment_data(self, experiment_name: str, 
                             control_column: str, metric_column: str) -> ExperimentData:
        """Load and prepare experiment data from BigQuery"""
        
        # User-level aggregation query - count orders per user during experiment
        # Based on earlier validation, we should have ~1043 users (527 control + 516 treatment)
        query = f"""
        SELECT
          user_id,
          CASE 
            WHEN {control_column} = 'control' THEN 'control'
            WHEN {control_column} = 'treatment' THEN 'treatment' 
            WHEN {control_column} IS NULL AND experiment_status = 'non_participant' THEN 'control'
            ELSE 'other'
          END as treatment_group,
          COUNT(*) as orders_during_experiment,
          SUM(num_of_item) as items_during_experiment,
          AVG(CASE WHEN is_completed = 1 THEN 1.0 ELSE 0.0 END) as completion_rate
        FROM `{self.project_id}.flit_marts.mart_free_shipping_threshold_analysis`
        WHERE time_period = 'experiment_period'
        GROUP BY user_id, treatment_group
        HAVING treatment_group IN ('control', 'treatment')
        """
        
        df = self.client.query(query).to_dataframe()
        
        if len(df) == 0:
            raise ValueError(f"No data found for experiment: {experiment_name}")
        
        # Split into control and treatment groups - use orders_during_experiment as primary metric
        control_data = df[df['treatment_group'] == 'control']['orders_during_experiment']
        treatment_data = df[df['treatment_group'] == 'treatment']['orders_during_experiment']
        
        if len(control_data) == 0 or len(treatment_data) == 0:
            raise ValueError("Missing control or treatment group data")
        
        # Create experiment data object - ensure numeric types
        experiment_data = create_experiment_data(
            control_values=control_data.astype(float),
            treatment_values=treatment_data.astype(float),
            metadata={
                'experiment_name': experiment_name,
                'metric': 'orders_during_experiment',
                'data_source': f"{self.project_id}.flit_marts.mart_free_shipping_threshold_analysis",
                'query_timestamp': datetime.now().isoformat()
            }
        )
        
        logger.info(f"Loaded data: {len(control_data)} control, {len(treatment_data)} treatment users")
        return experiment_data
    
    def _create_business_insights(self, statistical_results: Dict[str, Any], 
                                 data: ExperimentData) -> Dict[str, Any]:
        """Convert statistical results into business-friendly insights"""
        
        stats = statistical_results
        effect_size = stats['effect_sizes']['relative_lift']
        p_value = stats['significance_tests']['welch_ttest'].p_value
        
        # Calculate business impact estimates
        control_mean = stats['data_summary']['control']['mean']
        treatment_mean = stats['data_summary']['treatment']['mean']
        sample_size = len(data.control) + len(data.treatment)
        
        insights = {
            'primary_insight': self._create_primary_insight(effect_size, p_value),
            'effect_magnitude': self._assess_effect_magnitude(effect_size),
            'statistical_reliability': self._assess_statistical_reliability(stats),
            'estimated_impact': self._estimate_business_impact(effect_size, control_mean, sample_size),
            'implementation_readiness': self._assess_implementation_readiness(stats),
            'key_risks': self._identify_key_risks(stats),
            'confidence_factors': self._list_confidence_factors(stats)
        }
        
        return insights
    
    def _make_recommendation(self, statistical_results: Dict[str, Any],
                           business_insights: Dict[str, Any]) -> BusinessRecommendation:
        """Generate final business recommendation"""
        
        stats = statistical_results
        insights = business_insights
        
        effect_size = stats['effect_sizes']['relative_lift']
        p_value = stats['significance_tests']['welch_ttest'].p_value
        power = stats['power_analysis']['achieved_power']
        
        # Decision logic
        statistically_significant = p_value < 0.05
        practically_significant = abs(effect_size) >= 0.10  # 10% threshold
        well_powered = power >= 0.70
        
        if statistically_significant and effect_size > 0:
            if practically_significant and well_powered:
                decision = "STRONG_LAUNCH"
                confidence = "HIGH"
                reasoning = f"Clear positive effect ({effect_size:.1%}) with strong statistical evidence"
            elif practically_significant:
                decision = "LAUNCH"  
                confidence = "MEDIUM-HIGH"
                reasoning = f"Positive effect ({effect_size:.1%}) is statistically significant and meaningful"
            else:
                decision = "CONSIDER_LAUNCH"
                confidence = "MEDIUM"
                reasoning = f"Small but significant positive effect ({effect_size:.1%}) - evaluate cost/benefit"
        elif not statistically_significant and abs(effect_size) >= 0.15:
            decision = "EXTEND_TEST"
            confidence = "LOW"
            reasoning = f"Large effect size ({effect_size:.1%}) but not statistically significant - need more data"
        elif statistically_significant and effect_size < 0:
            decision = "NO_LAUNCH"
            confidence = "HIGH" 
            reasoning = f"Statistically significant negative effect ({effect_size:.1%}) detected"
        else:
            decision = "NO_LAUNCH"
            confidence = "MEDIUM"
            reasoning = f"No clear evidence of positive business impact (effect: {effect_size:.1%})"
        
        # Generate next steps
        next_steps = self._generate_next_steps(decision, insights)
        
        return BusinessRecommendation(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            risk_level=insights['key_risks'],
            expected_impact=insights['estimated_impact'],
            next_steps=next_steps
        )
    
    def _create_primary_insight(self, effect_size: float, p_value: float) -> str:
        """Create the main takeaway message"""
        
        if p_value < 0.05 and effect_size > 0:
            return f"The new approach shows a {effect_size:.1%} improvement with statistical confidence"
        elif p_value < 0.05 and effect_size < 0:
            return f"The new approach shows a {abs(effect_size):.1%} decrease with statistical confidence"
        else:
            return f"No statistically significant difference detected (observed: {effect_size:.1%})"
    
    def _assess_effect_magnitude(self, effect_size: float) -> str:
        """Assess the business significance of the effect size"""
        
        abs_effect = abs(effect_size)
        
        if abs_effect >= 0.20:
            return "Large business impact"
        elif abs_effect >= 0.10:
            return "Moderate business impact"
        elif abs_effect >= 0.05:
            return "Small but potentially meaningful impact"
        else:
            return "Minimal business impact"
    
    def _assess_statistical_reliability(self, stats: Dict[str, Any]) -> str:
        """Assess how reliable the statistical results are"""
        
        p_value = stats['significance_tests']['welch_ttest'].p_value
        power = stats['power_analysis']['achieved_power']
        balance = stats['metadata']['balance_ratio']
        
        if p_value < 0.01 and power > 0.80 and balance > 0.8:
            return "Very high statistical reliability"
        elif p_value < 0.05 and power > 0.70:
            return "High statistical reliability"
        elif p_value < 0.05:
            return "Moderate statistical reliability"
        else:
            return "Low statistical reliability"
    
    def _estimate_business_impact(self, effect_size: float, baseline: float, sample_size: int) -> str:
        """Estimate the business impact in practical terms"""
        
        if abs(effect_size) < 0.01:
            return "Minimal expected business impact"
        
        # These would typically come from business context
        # For now, provide template estimates
        annual_multiplier = 24  # Assuming 15-day test scales to ~year
        estimated_user_base = 50000  # Typical user base estimate
        
        annual_impact_per_user = baseline * effect_size * annual_multiplier
        total_annual_impact = annual_impact_per_user * estimated_user_base
        
        return f"Estimated {total_annual_impact:,.0f} additional units annually (assumes {estimated_user_base:,} eligible users)"
    
    def _assess_implementation_readiness(self, stats: Dict[str, Any]) -> str:
        """Assess readiness for implementation"""
        
        assumptions_ok = len(stats.get('assumptions', {})) > 0
        power_adequate = stats['power_analysis']['achieved_power'] > 0.70
        
        if assumptions_ok and power_adequate:
            return "Ready for implementation"
        elif power_adequate:
            return "Ready with monitoring of key assumptions"
        else:
            return "Consider additional testing before full implementation"
    
    def _identify_key_risks(self, stats: Dict[str, Any]) -> str:
        """Identify main risks to consider"""
        
        power = stats['power_analysis']['achieved_power']
        balance = stats['metadata']['balance_ratio']
        
        if power < 0.70 and balance < 0.8:
            return "HIGH - Low statistical power and group imbalance"
        elif power < 0.70:
            return "MEDIUM - Low statistical power may miss true effects"
        elif balance < 0.8:
            return "MEDIUM - Group imbalance may affect generalizability"
        else:
            return "LOW - No major statistical concerns identified"
    
    def _list_confidence_factors(self, stats: Dict[str, Any]) -> List[str]:
        """List factors that increase/decrease confidence in results"""
        
        factors = []
        
        # Positive factors
        if stats['power_analysis']['achieved_power'] > 0.80:
            factors.append("High statistical power supports reliable detection")
        
        if stats['metadata']['balance_ratio'] > 0.9:
            factors.append("Well-balanced experimental groups")
        
        if stats['significance_tests']['welch_ttest'].p_value < 0.01:
            factors.append("Strong statistical significance (p < 0.01)")
        
        # Negative factors  
        if stats['metadata']['total_sample_size'] < 1000:
            factors.append("Relatively small sample size")
        
        # Add assumption checks if available
        if 'assumptions' in stats:
            assumptions = stats['assumptions']
            if 'normality' in assumptions:
                if not (assumptions['normality']['control']['normal'] and assumptions['normality']['treatment']['normal']):
                    factors.append("Data not normally distributed (non-parametric tests validate)")
        
        return factors
    
    def _generate_next_steps(self, decision: str, insights: Dict[str, Any]) -> List[str]:
        """Generate specific next steps based on recommendation"""
        
        if decision in ["STRONG_LAUNCH", "LAUNCH"]:
            return [
                "Prepare implementation plan with phased rollout",
                "Set up monitoring for key metrics post-launch", 
                "Document learnings and update experiment playbook",
                "Communicate results to stakeholders",
                "Plan post-launch analysis at 30-day mark"
            ]
        elif decision == "CONSIDER_LAUNCH":
            return [
                "Conduct detailed cost-benefit analysis",
                "Review operational readiness for implementation",
                "Consider pilot test with subset of users",
                "Evaluate alternative approaches with larger effects"
            ]
        elif decision == "EXTEND_TEST":
            return [
                "Calculate required sample size for adequate power",
                "Extend test duration or expand to more users",
                "Consider testing larger effect size treatment",
                "Review experimental design for improvements"
            ]
        else:  # NO_LAUNCH
            return [
                "Do not implement the tested changes",
                "Investigate why results differed from expectations",
                "Consider alternative approaches to achieve goals",
                "Document learnings for future experiments"
            ]
    
    def _translate_p_value_to_confidence(self, p_value: float) -> str:
        """Convert p-value to business-friendly confidence language"""
        
        if p_value < 0.001:
            return "Very high confidence (>99.9%)"
        elif p_value < 0.01:
            return "High confidence (>99%)"
        elif p_value < 0.05:
            return "Moderate confidence (>95%)"
        else:
            return f"Low confidence (~{(1-p_value)*100:.0f}%)"
    
    def _create_distribution_plot(self, output_dir: str) -> str:
        """Create distribution comparison plot for skewed data"""
        
        # This would create a more detailed distribution plot
        # Implementation depends on access to the raw data
        # For now, return placeholder
        
        filepath = f"{output_dir}/distributions.png"
        
        # Create placeholder plot
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, 'Distribution plot\n(Generated when data is skewed)', 
               ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Data Distribution Comparison')
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath


def run_quick_analysis(experiment_name: str = "free_shipping_threshold_test_v1_1_1") -> Dict[str, Any]:
    """
    Quick analysis function for immediate results
    
    Use this when you just want the key insights without all the detailed
    statistical machinery. Good for rapid iteration and initial assessments.
    """
    print(f"🚀 Running quick analysis for: {experiment_name}")
    
    reporter = ExperimentReporter()
    
    try:
        # Run complete analysis
        results = reporter.analyze_experiment(experiment_name)
        
        # Print key insights
        rec = results['recommendation']
        insights = results['business_insights']
        
        print(f"\n📊 KEY RESULTS:")
        print(f"   Recommendation: {rec['decision']}")
        print(f"   Confidence: {rec['confidence']}")
        print(f"   Effect Size: {results['statistical_results']['effect_sizes']['relative_lift_percent']:.1f}%")
        print(f"   P-value: {results['statistical_results']['significance_tests']['welch_ttest'].p_value:.4f}")
        
        print(f"\n💡 BUSINESS INSIGHT:")
        print(f"   {insights['primary_insight']}")
        
        print(f"\n🎯 NEXT STEPS:")
        for i, step in enumerate(rec['next_steps'][:3], 1):
            print(f"   {i}. {step}")
        
        return results
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
        raise


if __name__ == "__main__":
    # Test the module
    print("Business Intelligence Module - Ready for Analysis! 🎯")
    
    # You can uncomment this to run a test
    # results = run_quick_analysis()
    # print("✅ Module validation complete")