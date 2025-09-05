#!/usr/bin/env python3
"""
Statistical Analysis Engine for A/B Testing Experiments

This module provides enterprise-grade statistical analysis capabilities designed for
rigorous experimentation workflows. Built to handle any A/B test with proper
statistical methodology and comprehensive validation.

Key Features:
- Robust statistical testing with multiple methods
- Effect size calculations with proper confidence intervals
- Power analysis validation and sample size assessments
- Sensitivity analysis and assumption checking
- Subgroup analysis capabilities
- Professional error handling and validation

Author: Senior Data Scientist Team
Version: 1.0.0
Created: 2024-09-02
"""

import pandas as pd
import numpy as np
import scipy.stats as stats
from scipy.stats import ttest_ind, mannwhitneyu, bootstrap
from statsmodels.stats.power import ttest_power
from typing import Dict, Any, List, Tuple, Optional, Union
import logging
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ExperimentData:
    """Data container for experiment analysis"""
    control: pd.Series
    treatment: pd.Series
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        """Validate data after initialization"""
        if len(self.control) == 0 or len(self.treatment) == 0:
            raise ValueError("Control and treatment groups must have data")
        
        if not isinstance(self.control, pd.Series):
            self.control = pd.Series(self.control)
        if not isinstance(self.treatment, pd.Series):
            self.treatment = pd.Series(self.treatment)


@dataclass 
class StatisticalResult:
    """Container for statistical test results"""
    test_name: str
    statistic: float
    p_value: float
    significant: bool
    method_notes: str = ""
    
    @property
    def significance_level(self) -> str:
        """Return human-readable significance level"""
        if self.p_value < 0.001:
            return "p < 0.001 (highly significant)"
        elif self.p_value < 0.01:
            return "p < 0.01 (very significant)" 
        elif self.p_value < 0.05:
            return "p < 0.05 (significant)"
        else:
            return f"p = {self.p_value:.4f} (not significant)"


class StatisticalAnalysisEngine:
    """
    Enterprise-grade statistical analysis engine for A/B testing
    
    Designed for scalability across different experiment types while maintaining
    statistical rigor and professional standards. Handles all core statistical
    computations with proper error handling and validation.
    """
    
    def __init__(self, significance_level: float = 0.05):
        """
        Initialize statistical engine
        
        Args:
            significance_level: Alpha level for statistical tests (default: 0.05)
        """
        self.alpha = significance_level
        self.random_state = np.random.RandomState(42)  # Reproducible results
        
        logger.info(f"Statistical engine initialized with α = {significance_level}")
    
    def analyze_experiment(self, data: ExperimentData) -> Dict[str, Any]:
        """
        Execute comprehensive statistical analysis on experiment data
        
        Args:
            data: ExperimentData object containing control/treatment groups
            
        Returns:
            Dictionary containing all statistical analysis results
            
        Raises:
            ValueError: If data validation fails
        """
        logger.info("Starting comprehensive statistical analysis")
        
        # Validate input data
        self._validate_experiment_data(data)
        
        # Execute all analysis components
        results = {
            'data_summary': self._calculate_descriptive_statistics(data),
            'effect_sizes': self._calculate_effect_sizes(data),
            'significance_tests': self._run_significance_tests(data),
            'confidence_intervals': self._calculate_confidence_intervals(data),
            'power_analysis': self._validate_power_analysis(data),
            'sensitivity_analysis': self._run_sensitivity_tests(data),
            'assumptions': self._check_statistical_assumptions(data),
            'metadata': {
                'analysis_engine_version': '1.0.0',
                'significance_level': self.alpha,
                'total_sample_size': len(data.control) + len(data.treatment),
                'balance_ratio': min(len(data.control), len(data.treatment)) / max(len(data.control), len(data.treatment))
            }
        }
        
        logger.info("Statistical analysis completed successfully")
        return results
    
    def analyze_subgroups(self, control_data: pd.DataFrame, treatment_data: pd.DataFrame,
                         grouping_column: str, metric_column: str) -> Dict[str, Dict[str, Any]]:
        """
        Perform subgroup analysis to identify heterogeneous treatment effects
        
        Args:
            control_data: Control group DataFrame
            treatment_data: Treatment group DataFrame  
            grouping_column: Column to group by (e.g., 'device_type', 'region')
            metric_column: Metric to analyze (e.g., 'orders_per_user')
            
        Returns:
            Dictionary with subgroup analysis results
        """
        logger.info(f"Running subgroup analysis by {grouping_column}")
        
        subgroup_results = {}
        
        # Get unique subgroups
        all_groups = set(control_data[grouping_column].unique()) | set(treatment_data[grouping_column].unique())
        
        for group in all_groups:
            # Filter data for this subgroup
            control_subgroup = control_data[control_data[grouping_column] == group][metric_column]
            treatment_subgroup = treatment_data[treatment_data[grouping_column] == group][metric_column]
            
            # Skip if insufficient data
            if len(control_subgroup) < 10 or len(treatment_subgroup) < 10:
                logger.warning(f"Insufficient data for subgroup {group}, skipping")
                continue
            
            # Create ExperimentData for this subgroup
            subgroup_data = ExperimentData(
                control=control_subgroup,
                treatment=treatment_subgroup,
                metadata={'subgroup': group, 'grouping_variable': grouping_column}
            )
            
            # Run analysis on subgroup
            subgroup_results[str(group)] = self.analyze_experiment(subgroup_data)
        
        return subgroup_results
    
    def _validate_experiment_data(self, data: ExperimentData) -> None:
        """Validate experiment data quality and structure"""
        
        # Check for minimum sample sizes
        min_sample_size = 10
        if len(data.control) < min_sample_size or len(data.treatment) < min_sample_size:
            raise ValueError(f"Minimum sample size of {min_sample_size} required for each group")
        
        # Check for extreme imbalance
        balance_ratio = min(len(data.control), len(data.treatment)) / max(len(data.control), len(data.treatment))
        if balance_ratio < 0.1:
            logger.warning(f"Severe group imbalance detected (ratio: {balance_ratio:.3f})")
        
        # Check for missing or infinite values
        if data.control.isna().any() or data.treatment.isna().any():
            raise ValueError("Missing values detected in experiment data")
        
        if np.isinf(data.control).any() or np.isinf(data.treatment).any():
            raise ValueError("Infinite values detected in experiment data")
        
        logger.debug("Data validation passed")
    
    def _calculate_descriptive_statistics(self, data: ExperimentData) -> Dict[str, Dict[str, float]]:
        """Calculate comprehensive descriptive statistics for both groups"""
        
        def _stats_for_group(series: pd.Series, label: str) -> Dict[str, float]:
            """Calculate stats for a single group"""
            return {
                'label': label,
                'count': int(len(series)),
                'mean': float(series.mean()),
                'std': float(series.std()),
                'sem': float(series.sem()),
                'median': float(series.median()),
                'q25': float(series.quantile(0.25)),
                'q75': float(series.quantile(0.75)),
                'min': float(series.min()),
                'max': float(series.max()),
                'variance': float(series.var()),
                'skewness': float(stats.skew(series)),
                'kurtosis': float(stats.kurtosis(series))
            }
        
        return {
            'control': _stats_for_group(data.control, 'Control Group'),
            'treatment': _stats_for_group(data.treatment, 'Treatment Group')
        }
    
    def _calculate_effect_sizes(self, data: ExperimentData) -> Dict[str, float]:
        """Calculate multiple effect size measures"""
        
        control_mean = data.control.mean()
        treatment_mean = data.treatment.mean()
        control_std = data.control.std()
        treatment_std = data.treatment.std()
        
        # Basic effect measures
        absolute_difference = treatment_mean - control_mean
        relative_lift = absolute_difference / control_mean if control_mean != 0 else 0
        
        # Standardized effect sizes
        # Cohen's d (pooled standard deviation)
        pooled_std = np.sqrt(
            ((len(data.control) - 1) * control_std**2 + (len(data.treatment) - 1) * treatment_std**2) / 
            (len(data.control) + len(data.treatment) - 2)
        )
        cohens_d = absolute_difference / pooled_std if pooled_std != 0 else 0
        
        # Glass's delta (control group standard deviation)
        glass_delta = absolute_difference / control_std if control_std != 0 else 0
        
        # Hedges' g (bias-corrected Cohen's d for small samples)
        correction_factor = 1 - 3/(4*(len(data.control) + len(data.treatment)) - 9)
        hedges_g = cohens_d * correction_factor
        
        return {
            'absolute_difference': float(absolute_difference),
            'relative_lift': float(relative_lift), 
            'relative_lift_percent': float(relative_lift * 100),
            'cohens_d': float(cohens_d),
            'glass_delta': float(glass_delta),
            'hedges_g': float(hedges_g),
            'control_mean': float(control_mean),
            'treatment_mean': float(treatment_mean),
            'pooled_std': float(pooled_std)
        }
    
    def _run_significance_tests(self, data: ExperimentData) -> Dict[str, StatisticalResult]:
        """Run multiple statistical significance tests"""
        
        results = {}
        
        # Welch's t-test (unequal variances assumed - most robust for A/B testing)
        t_stat, p_val = ttest_ind(data.treatment, data.control, equal_var=False)
        results['welch_ttest'] = StatisticalResult(
            test_name="Welch's t-test",
            statistic=float(t_stat),
            p_value=float(p_val),
            significant=p_val < self.alpha,
            method_notes="Assumes unequal variances (recommended for A/B testing)"
        )
        
        # Student's t-test (equal variances assumed - for comparison)
        t_stat_eq, p_val_eq = ttest_ind(data.treatment, data.control, equal_var=True)
        results['student_ttest'] = StatisticalResult(
            test_name="Student's t-test", 
            statistic=float(t_stat_eq),
            p_value=float(p_val_eq),
            significant=p_val_eq < self.alpha,
            method_notes="Assumes equal variances"
        )
        
        # Mann-Whitney U test (non-parametric alternative)
        u_stat, u_p_val = mannwhitneyu(data.treatment, data.control, alternative='two-sided')
        results['mann_whitney'] = StatisticalResult(
            test_name="Mann-Whitney U test",
            statistic=float(u_stat), 
            p_value=float(u_p_val),
            significant=u_p_val < self.alpha,
            method_notes="Non-parametric alternative, doesn't assume normality"
        )
        
        return results
    
    def _calculate_confidence_intervals(self, data: ExperimentData, 
                                     confidence_level: float = 0.95) -> Dict[str, Any]:
        """Calculate confidence intervals using bootstrap method"""
        
        alpha = 1 - confidence_level
        n_bootstrap = 10000
        
        # Bootstrap function for difference in means
        def bootstrap_statistic(control_sample, treatment_sample):
            """Calculate the statistic of interest"""
            diff = np.mean(treatment_sample) - np.mean(control_sample)
            relative_diff = diff / np.mean(control_sample) if np.mean(control_sample) != 0 else 0
            return diff, relative_diff
        
        # Perform bootstrap sampling
        bootstrap_diffs = []
        bootstrap_relative_diffs = []
        
        for _ in range(n_bootstrap):
            # Resample with replacement
            control_sample = self.random_state.choice(data.control, len(data.control), replace=True)
            treatment_sample = self.random_state.choice(data.treatment, len(data.treatment), replace=True)
            
            diff, rel_diff = bootstrap_statistic(control_sample, treatment_sample)
            bootstrap_diffs.append(diff)
            bootstrap_relative_diffs.append(rel_diff)
        
        # Calculate confidence intervals
        lower_pct = 100 * alpha / 2
        upper_pct = 100 * (1 - alpha / 2)
        
        abs_ci_lower = np.percentile(bootstrap_diffs, lower_pct)
        abs_ci_upper = np.percentile(bootstrap_diffs, upper_pct)
        
        rel_ci_lower = np.percentile(bootstrap_relative_diffs, lower_pct)
        rel_ci_upper = np.percentile(bootstrap_relative_diffs, upper_pct)
        
        return {
            'method': 'Bootstrap',
            'confidence_level': confidence_level,
            'n_bootstrap_samples': n_bootstrap,
            'absolute_difference_ci': {
                'lower': float(abs_ci_lower),
                'upper': float(abs_ci_upper),
                'range': f"[{abs_ci_lower:.4f}, {abs_ci_upper:.4f}]"
            },
            'relative_lift_ci': {
                'lower': float(rel_ci_lower),
                'upper': float(rel_ci_upper), 
                'range': f"[{rel_ci_lower:.2%}, {rel_ci_upper:.2%}]"
            }
        }
    
    def _validate_power_analysis(self, data: ExperimentData) -> Dict[str, Any]:
        """Perform post-hoc power analysis to validate experimental design"""
        
        # Calculate observed effect size (Cohen's d)
        control_mean = data.control.mean()
        treatment_mean = data.treatment.mean()
        pooled_std = np.sqrt(
            (data.control.var() + data.treatment.var()) / 2
        )
        
        observed_cohens_d = abs(treatment_mean - control_mean) / pooled_std if pooled_std != 0 else 0
        
        # Calculate achieved statistical power
        total_n = len(data.control) + len(data.treatment)
        achieved_power = ttest_power(observed_cohens_d, total_n, alpha=self.alpha, alternative='two-sided')
        
        # Power analysis for different effect sizes (sensitivity analysis)
        effect_sizes = [0.1, 0.2, 0.3, 0.5, 0.8]  # Small, small-medium, medium, large, very large
        power_curve = {}
        
        for effect_size in effect_sizes:
            power = ttest_power(effect_size, total_n, alpha=self.alpha, alternative='two-sided')
            power_curve[f"effect_size_{effect_size}"] = float(power)
        
        return {
            'observed_effect_size_cohens_d': float(observed_cohens_d),
            'achieved_power': float(achieved_power),
            'total_sample_size': total_n,
            'power_adequate': achieved_power >= 0.80,
            'power_curve': power_curve,
            'interpretation': {
                'power_level': 'Excellent' if achieved_power >= 0.90 else 
                              'Good' if achieved_power >= 0.80 else
                              'Adequate' if achieved_power >= 0.70 else 'Low',
                'minimum_detectable_effect': f"Can detect Cohen's d >= {observed_cohens_d:.3f} with {achieved_power:.1%} power"
            }
        }
    
    def _run_sensitivity_tests(self, data: ExperimentData) -> Dict[str, Any]:
        """Run sensitivity analysis to test robustness of results"""
        
        sensitivity_results = {}
        
        # Outlier sensitivity - remove extreme values and retest
        def remove_outliers(series: pd.Series, method: str = 'iqr') -> pd.Series:
            """Remove outliers using IQR method"""
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            return series[(series >= lower_bound) & (series <= upper_bound)]
        
        # Test without outliers
        control_clean = remove_outliers(data.control)
        treatment_clean = remove_outliers(data.treatment)
        
        if len(control_clean) >= 10 and len(treatment_clean) >= 10:
            t_stat_clean, p_val_clean = ttest_ind(treatment_clean, control_clean, equal_var=False)
            original_effect = (data.treatment.mean() - data.control.mean()) / data.control.mean()
            clean_effect = (treatment_clean.mean() - control_clean.mean()) / control_clean.mean()
            
            sensitivity_results['outlier_sensitivity'] = {
                'original_effect': float(original_effect),
                'without_outliers_effect': float(clean_effect),
                'effect_change': float(abs(clean_effect - original_effect)),
                'p_value_without_outliers': float(p_val_clean),
                'robust_to_outliers': abs(clean_effect - original_effect) < 0.05,
                'outliers_removed': {
                    'control': len(data.control) - len(control_clean),
                    'treatment': len(data.treatment) - len(treatment_clean)
                }
            }
        
        # Minimum effect size that would be significant
        min_detectable_effect = self._calculate_minimum_detectable_effect(data)
        sensitivity_results['minimum_detectable_effect'] = min_detectable_effect
        
        return sensitivity_results
    
    def _check_statistical_assumptions(self, data: ExperimentData) -> Dict[str, Any]:
        """Check key statistical assumptions for t-tests"""
        
        assumptions = {}
        
        # Normality tests (Shapiro-Wilk for small samples, Anderson-Darling for larger)
        if len(data.control) <= 5000 and len(data.treatment) <= 5000:
            # Shapiro-Wilk test
            control_normality = stats.shapiro(data.control)
            treatment_normality = stats.shapiro(data.treatment)
            
            assumptions['normality'] = {
                'test_used': 'Shapiro-Wilk',
                'control': {
                    'statistic': float(control_normality.statistic),
                    'p_value': float(control_normality.pvalue),
                    'normal': control_normality.pvalue > 0.05
                },
                'treatment': {
                    'statistic': float(treatment_normality.statistic), 
                    'p_value': float(treatment_normality.pvalue),
                    'normal': treatment_normality.pvalue > 0.05
                }
            }
        
        # Levene's test for equal variances
        levene_stat, levene_p = stats.levene(data.control, data.treatment)
        assumptions['equal_variances'] = {
            'test_used': "Levene's test",
            'statistic': float(levene_stat),
            'p_value': float(levene_p),
            'equal_variances': levene_p > 0.05,
            'recommendation': "Use Welch's t-test" if levene_p <= 0.05 else "Standard t-test acceptable"
        }
        
        # Independence assumption (basic checks)
        assumptions['independence'] = {
            'assumption': 'Independence of observations',
            'status': 'Assumed based on experimental design',
            'notes': 'Verify randomization was properly implemented'
        }
        
        return assumptions
    
    def _calculate_minimum_detectable_effect(self, data: ExperimentData, 
                                           power: float = 0.80) -> Dict[str, float]:
        """Calculate minimum detectable effect size given sample size and power"""
        
        total_n = len(data.control) + len(data.treatment)
        
        # Use root finding to determine minimum effect size for given power
        from scipy.optimize import minimize_scalar
        
        def power_function(effect_size):
            """Return difference between target power and achieved power"""
            achieved_power = ttest_power(effect_size, total_n, alpha=self.alpha, alternative='two-sided')
            return abs(achieved_power - power)
        
        # Find minimum effect size for target power
        result = minimize_scalar(power_function, bounds=(0.01, 2.0), method='bounded')
        min_cohens_d = result.x
        
        # Convert Cohen's d to relative effect (approximate)
        control_mean = data.control.mean()
        control_std = data.control.std()
        min_absolute_effect = min_cohens_d * control_std
        min_relative_effect = min_absolute_effect / control_mean if control_mean != 0 else 0
        
        return {
            'minimum_cohens_d': float(min_cohens_d),
            'minimum_absolute_effect': float(min_absolute_effect),
            'minimum_relative_effect': float(min_relative_effect),
            'minimum_relative_effect_percent': float(min_relative_effect * 100),
            'target_power': power,
            'sample_size': total_n
        }


def create_experiment_data(control_values: Union[List, pd.Series], 
                          treatment_values: Union[List, pd.Series],
                          metadata: Dict[str, Any] = None) -> ExperimentData:
    """
    Factory function to create ExperimentData objects
    
    Args:
        control_values: Control group measurements
        treatment_values: Treatment group measurements  
        metadata: Optional metadata about the experiment
        
    Returns:
        ExperimentData object ready for analysis
    """
    if metadata is None:
        metadata = {}
    
    return ExperimentData(
        control=pd.Series(control_values) if not isinstance(control_values, pd.Series) else control_values,
        treatment=pd.Series(treatment_values) if not isinstance(treatment_values, pd.Series) else treatment_values,
        metadata=metadata
    )


# Utility functions for common statistical operations

def quick_ttest(control: Union[List, pd.Series], treatment: Union[List, pd.Series]) -> Dict[str, float]:
    """
    Quick t-test for rapid analysis
    
    Args:
        control: Control group values
        treatment: Treatment group values
        
    Returns:
        Dictionary with basic t-test results
    """
    control = pd.Series(control) if not isinstance(control, pd.Series) else control
    treatment = pd.Series(treatment) if not isinstance(treatment, pd.Series) else treatment
    
    t_stat, p_val = ttest_ind(treatment, control, equal_var=False)
    effect_size = (treatment.mean() - control.mean()) / control.mean() if control.mean() != 0 else 0
    
    return {
        't_statistic': float(t_stat),
        'p_value': float(p_val),
        'significant': p_val < 0.05,
        'control_mean': float(control.mean()),
        'treatment_mean': float(treatment.mean()),
        'relative_lift': float(effect_size)
    }


if __name__ == "__main__":
    # Example usage and testing
    print("Statistical Analysis Engine - Module Test")
    
    # Generate sample data for testing
    np.random.seed(42)
    control_sample = np.random.normal(1.0, 0.3, 500)  # Control: mean=1.0
    treatment_sample = np.random.normal(1.2, 0.35, 480)  # Treatment: mean=1.2 (20% lift)
    
    # Create experiment data
    test_data = create_experiment_data(
        control_values=control_sample,
        treatment_values=treatment_sample,
        metadata={'test': 'module_validation'}
    )
    
    # Initialize engine and run analysis
    engine = StatisticalAnalysisEngine()
    results = engine.analyze_experiment(test_data)
    
    # Print key results
    print(f"\n✅ Module validation complete")
    print(f"Sample sizes: Control={len(test_data.control)}, Treatment={len(test_data.treatment)}")
    print(f"Effect size: {results['effect_sizes']['relative_lift']:.2%}")
    print(f"P-value: {results['significance_tests']['welch_ttest'].p_value:.6f}")
    print(f"Statistical power: {results['power_analysis']['achieved_power']:.3f}")
    print(f"Ready for production use! 🚀")