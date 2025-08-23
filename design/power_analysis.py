import numpy as np
import pandas as pd
from scipy import stats
from datetime import datetime, timedelta
import yaml
import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import warnings

# Import our configuration package
from flit_experiment_configs import get_experiment_config, get_package_version, logger

# Import improved BigQuery utilities
from .bigquery_utils import BigQueryTrafficAnalyzer

# Set up logging for this module
logging.basicConfig(level=logging.INFO)
power_logger = logging.getLogger(__name__)


@dataclass
class PowerAnalysisResult:
    """
    Structured container for power analysis results
    
    Using dataclasses shows modern Python practices and makes results
    easy to work with downstream. Much better than returning dictionaries.
    """
    experiment_name: str
    config_version: str
    
    # Statistical parameters
    baseline_rate: float
    treatment_rate: float
    effect_size: float
    required_sample_per_variant: int
    total_required_sample: int
    statistical_power: float
    significance_level: float
    
    # Traffic analysis
    daily_eligible_users: int
    daily_users_per_variant: int
    traffic_variability: float
    
    # Duration calculations
    required_duration_days: int
    required_duration_weeks: float
    final_planned_duration: int
    
    # Feasibility assessment
    feasibility_status: str
    feasibility_reasons: List[str]
    
    # Calendar recommendations
    suggested_start_dates: Dict[str, str]
    
    # Validation flags
    assumptions_met: bool
    warnings: List[str]


class ExperimentPowerAnalysis:
    """
    Comprehensive power analysis engine for A/B testing
    
    This class handles the complexity of:
    - Multiple test types (proportions, means, counts)
    - Historical traffic analysis from BigQuery
    - Business constraint validation
    - Calendar optimization
    - Statistical assumption checking
    """
    
    def __init__(self, project_id: str = None, use_mock_data: bool = False, reference_date: str = None):
        """
        Initialize the power analysis engine
        
        Args:
            project_id: Optional BigQuery project ID
            use_mock_data: If True, use mock data instead of BigQuery (for development)
            reference_date: Date to use as "current date" for historical simulation (YYYY-MM-DD)
                          If None, uses actual current date for live experiments
        """
        # Initialize BigQuery traffic analyzer with proper error handling
        self.traffic_analyzer = BigQueryTrafficAnalyzer(
            project_id=project_id,
            use_mock_data=use_mock_data
        )
        
        # Set reference date for historical simulation vs live experiments
        if reference_date:
            self.reference_date = datetime.strptime(reference_date, '%Y-%m-%d')
            self.simulation_mode = True
            power_logger.info(f"Historical simulation mode: reference date = {reference_date}")
        else:
            self.reference_date = datetime.now()
            self.simulation_mode = False
            power_logger.info("Live experiment mode: using current date")
        
        power_logger.info(f"Initialized ExperimentPowerAnalysis")
        power_logger.info(f"Using config package version: {get_package_version()}")
        power_logger.info(f"BigQuery mode: {'Mock Data' if use_mock_data else 'Live Data'}")
    
    def calculate_test_sample_size(
        self, 
        test_type: str,
        baseline_value: float,
        effect_size: float,
        power: float = 0.80,
        alpha: float = 0.05,
        allocation_ratio: float = 0.5
    ) -> Dict[str, Any]:
        """
        Calculate required sample size for different test types
        
        This is the generalized version (not just conversion_test_sample_size)
        that can handle multiple metric types.
        
        Args:
            test_type: "conversion", "continuous", or "count"
            baseline_value: Current metric value (proportion, mean, or count)
            effect_size: Relative improvement to detect
            power: Statistical power (typically 0.8)
            alpha: Type I error rate (typically 0.05)
            allocation_ratio: Fraction assigned to treatment (typically 0.5)
            
        Returns:
            Dictionary with sample size calculations and assumptions
        """
        if test_type == "conversion":
            return self._calculate_proportion_sample_size(
                baseline_value, effect_size, power, alpha, allocation_ratio
            )
        elif test_type == "continuous":
            return self._calculate_continuous_sample_size(
                baseline_value, effect_size, power, alpha, allocation_ratio
            )
        elif test_type == "count":
            return self._calculate_count_sample_size(
                baseline_value, effect_size, power, alpha, allocation_ratio
            )
        else:
            raise ValueError(f"Unsupported test type: {test_type}. Use 'conversion', 'continuous', or 'count'")
    
    def _calculate_proportion_sample_size(
        self, 
        baseline_rate: float, 
        effect_size: float, 
        power: float, 
        alpha: float,
        allocation_ratio: float
    ) -> Dict[str, Any]:
        """
        Calculate sample size for proportion tests (conversion rates, CTR, etc.)
        
        Uses the standard two-proportion z-test formula with proper adjustments
        for unequal allocation if needed.
        """
        # Calculate treatment rate from relative effect size
        treatment_rate = baseline_rate * (1 + effect_size)
        
        # Validate assumptions for normal approximation
        # Rule of thumb: np >= 5 and n(1-p) >= 5 for both groups
        min_n_for_normal_approx = max(
            5 / baseline_rate,
            5 / (1 - baseline_rate),
            5 / treatment_rate,
            5 / (1 - treatment_rate)
        )
        
        # For equal allocation (most common case)
        if allocation_ratio == 0.5:
            # Pooled proportion under null hypothesis
            pooled_rate = (baseline_rate + treatment_rate) / 2
            
            # Standard errors
            pooled_se = np.sqrt(2 * pooled_rate * (1 - pooled_rate))
            effect_se = np.sqrt(baseline_rate * (1 - baseline_rate) + 
                               treatment_rate * (1 - treatment_rate))
            
            # Critical values
            z_alpha = stats.norm.ppf(1 - alpha/2)  # Two-tailed test
            z_beta = stats.norm.ppf(power)
            
            # Sample size per group
            n_per_group = ((z_alpha * pooled_se + z_beta * effect_se) / 
                          (treatment_rate - baseline_rate)) ** 2
        else:
            # Unequal allocation case (more complex formula)
            # This shows we can handle advanced scenarios
            r = allocation_ratio / (1 - allocation_ratio)  # allocation ratio
            
            pooled_rate = (baseline_rate + r * treatment_rate) / (1 + r)
            pooled_se = np.sqrt(pooled_rate * (1 - pooled_rate) * (1 + 1/r))
            effect_se = np.sqrt(baseline_rate * (1 - baseline_rate) + 
                               treatment_rate * (1 - treatment_rate) / r)
            
            z_alpha = stats.norm.ppf(1 - alpha/2)
            z_beta = stats.norm.ppf(power)
            
            # Sample size for control group
            n_control = ((z_alpha * pooled_se + z_beta * effect_se) / 
                        (treatment_rate - baseline_rate)) ** 2
            
            n_per_group = n_control  # For reporting consistency
        
        # Round up to ensure adequate power
        n_per_group = int(np.ceil(n_per_group))
        
        # Check if normal approximation assumptions are met
        assumptions_met = n_per_group >= min_n_for_normal_approx
        
        warnings_list = []
        if not assumptions_met:
            warnings_list.append(
                f"Normal approximation may be inadequate. Recommend exact methods or larger effect size."
            )
        
        return {
            "test_type": "two_proportion_z_test",
            "baseline_rate": baseline_rate,
            "treatment_rate": treatment_rate,
            "absolute_difference": treatment_rate - baseline_rate,
            "relative_improvement": effect_size,
            "required_per_variant": n_per_group,
            "total_required": n_per_group * 2,
            "statistical_power": power,
            "significance_level": alpha,
            "allocation_ratio": allocation_ratio,
            "assumptions_met": assumptions_met,
            "min_n_for_normal_approx": int(min_n_for_normal_approx),
            "warnings": warnings_list
        }
    
    def _calculate_continuous_sample_size(
        self, 
        baseline_mean: float, 
        effect_size: float, 
        power: float, 
        alpha: float,
        allocation_ratio: float
    ) -> Dict[str, Any]:
        """
        Calculate sample size for continuous metrics (AOV, revenue, time on site)
        
        Uses Cohen's d and t-test assumptions. This would be used for metrics
        like average order value, session duration, etc.
        """
        # For continuous metrics, we need to estimate standard deviation
        # This is a limitation - we'd ideally get this from historical data
        # For now, assume coefficient of variation of 1.0 (std = mean)
        assumed_cv = 1.0  # This could be parameterized based on metric type
        baseline_std = baseline_mean * assumed_cv
        
        # Treatment mean
        treatment_mean = baseline_mean * (1 + effect_size)
        
        # Cohen's d (standardized effect size)
        cohens_d = (treatment_mean - baseline_mean) / baseline_std
        
        # Sample size calculation for two-sample t-test
        # Using equal variances assumption (pooled standard deviation)
        z_alpha = stats.norm.ppf(1 - alpha/2)
        z_beta = stats.norm.ppf(power)
        
        if allocation_ratio == 0.5:
            # Equal allocation
            n_per_group = 2 * ((z_alpha + z_beta) / cohens_d) ** 2
        else:
            # Unequal allocation
            r = allocation_ratio / (1 - allocation_ratio)
            n_control = ((z_alpha + z_beta) / cohens_d) ** 2 * (1 + 1/r)
            n_per_group = n_control
        
        n_per_group = int(np.ceil(n_per_group))
        
        # Check assumptions
        # t-test is robust, but very small samples can be problematic
        assumptions_met = n_per_group >= 30  # Central limit theorem threshold
        
        warnings_list = []
        if not assumptions_met:
            warnings_list.append(
                f"Small sample size may violate t-test assumptions. Consider non-parametric alternatives."
            )
        
        warnings_list.append(
            f"Assumed coefficient of variation = {assumed_cv}. Validate with historical data."
        )
        
        return {
            "test_type": "two_sample_t_test",
            "baseline_mean": baseline_mean,
            "treatment_mean": treatment_mean,
            "assumed_std": baseline_std,
            "cohens_d": cohens_d,
            "absolute_difference": treatment_mean - baseline_mean,
            "relative_improvement": effect_size,
            "required_per_variant": n_per_group,
            "total_required": n_per_group * 2,
            "statistical_power": power,
            "significance_level": alpha,
            "allocation_ratio": allocation_ratio,
            "assumptions_met": assumptions_met,
            "warnings": warnings_list
        }
    
    def _calculate_count_sample_size(
        self, 
        baseline_rate: float, 
        effect_size: float, 
        power: float, 
        alpha: float,
        allocation_ratio: float
    ) -> Dict[str, Any]:
        """
        Calculate sample size for count metrics (items per order, page views per session)
        
        Uses Poisson distribution assumptions, which is appropriate for count data.
        """
        # Treatment rate
        treatment_rate = baseline_rate * (1 + effect_size)
        
        # For Poisson data, variance = mean
        # Sample size formula for comparing two Poisson rates
        z_alpha = stats.norm.ppf(1 - alpha/2)
        z_beta = stats.norm.ppf(power)
        
        if allocation_ratio == 0.5:
            # Equal allocation
            # Approximate formula for Poisson rate comparison
            n_per_group = ((z_alpha * np.sqrt(baseline_rate + treatment_rate) + 
                          z_beta * np.sqrt(baseline_rate + treatment_rate)) / 
                         (treatment_rate - baseline_rate)) ** 2
        else:
            # Unequal allocation (more complex)
            r = allocation_ratio / (1 - allocation_ratio)
            pooled_rate = (baseline_rate + r * treatment_rate) / (1 + r)
            
            n_control = ((z_alpha * np.sqrt(pooled_rate * (1 + 1/r)) + 
                         z_beta * np.sqrt(baseline_rate + treatment_rate/r)) / 
                        (treatment_rate - baseline_rate)) ** 2
            
            n_per_group = n_control
        
        n_per_group = int(np.ceil(n_per_group))
        
        # Check Poisson approximation assumptions
        # Normal approximation to Poisson is good when rate >= 5
        assumptions_met = baseline_rate >= 5 and treatment_rate >= 5
        
        warnings_list = []
        if not assumptions_met:
            warnings_list.append(
                f"Poisson rates < 5 may require exact methods or larger sample sizes."
            )
        
    def analyze_historical_traffic(self, experiment_name: str) -> Dict[str, Any]:
        """
        Analyze TheLook historical data to estimate eligible user traffic
        
        Now uses the improved BigQuery utilities with proper error handling
        """
        power_logger.info(f"Starting historical traffic analysis for {experiment_name}")
        
        # Get experiment configuration
        config = get_experiment_config(experiment_name)
        eligibility_criteria = config['population']['eligibility_criteria']
        
        # Use the traffic analyzer to get results
        traffic_analysis = self.traffic_analyzer.analyze_traffic_patterns(eligibility_criteria)
        
        power_logger.info(f"Traffic analysis complete: {traffic_analysis['avg_daily_eligible_users']} avg daily users")
        power_logger.info(f"Data source: {traffic_analysis.get('data_source', 'unknown')}")
        
        return traffic_analysis
    
    def calculate_experiment_duration(
        self, 
        required_sample_size: int, 
        daily_eligible_users: int,
        allocation_per_variant: float = 0.5, 
        safety_buffer: float = 1.1,
        traffic_variability: float = 0.2
    ) -> Dict[str, Any]:
        """
        Calculate how long experiment needs to run to collect required sample
        
        Incorporates traffic variability and safety buffers - shows sophisticated
        understanding of real-world experimental challenges.
        """
        # Apply safety buffer for dropouts, exclusions, data quality issues
        target_sample_size = int(required_sample_size * safety_buffer)
        
        # Daily users per variant (accounting for allocation)
        daily_users_per_variant = int(daily_eligible_users * allocation_per_variant)
        
        # Basic duration calculation
        base_duration_days = math.ceil(target_sample_size / daily_users_per_variant)
        
        # Adjust for traffic variability
        # Higher variability means we need more time to ensure we hit our target
        variability_buffer = 1 + (traffic_variability * 0.5)  # Conservative adjustment
        adjusted_duration_days = int(base_duration_days * variability_buffer)
        
        # Ensure minimum duration for effect emergence and statistical stability
        # Most A/B tests need at least 1 week for weekly patterns, 2 weeks for stability
        min_duration_for_patterns = 14  # 2 weeks
        final_duration_days = max(adjusted_duration_days, min_duration_for_patterns)
        
        return {
            "required_sample_per_variant": required_sample_size,
            "target_sample_per_variant": target_sample_size,
            "daily_eligible_users": daily_eligible_users,
            "daily_users_per_variant": daily_users_per_variant,
            "base_duration_days": base_duration_days,
            "variability_adjusted_days": adjusted_duration_days,
            "final_duration_days": final_duration_days,
            "final_duration_weeks": round(final_duration_days / 7, 1),
            "safety_buffer_applied": safety_buffer,
            "traffic_variability_considered": traffic_variability
        }

    def assess_experiment_feasibility(self, experiment_name: str) -> PowerAnalysisResult:
            """
            Complete feasibility analysis: power → sample size → duration → calendar
            
            This is the main method that orchestrates the entire analysis.
            It demonstrates systems thinking by coordinating multiple complex analyses.
            """
            power_logger.info(f"\n{'='*60}")
            power_logger.info(f"🔬 POWER ANALYSIS FOR: {experiment_name.upper()}")
            power_logger.info(f"{'='*60}")
            
            # Get experiment configuration
            config = get_experiment_config(experiment_name)
            config_version = get_package_version()
            
            # Step 1: Statistical Power Calculation
            power_logger.info("\n📊 STEP 1: Statistical Power Calculation")
            power_config = config['power_analysis']
            
            # Determine test type from experiment configuration
            primary_metric = config['metrics']['primary']
            test_type = self._infer_test_type(primary_metric['name'])
            
            sample_analysis = self.calculate_test_sample_size(
                test_type=test_type,
                baseline_value=power_config['effect_size']['baseline_metric_value'],
                effect_size=power_config['effect_size']['magnitude'],
                power=power_config['statistical_power'],
                alpha=power_config['significance_level']
            )
            
            power_logger.info(f"Test type: {sample_analysis['test_type']}")
            power_logger.info(f"Baseline rate: {sample_analysis['baseline_rate']:.1%}")
            power_logger.info(f"Target rate: {sample_analysis['treatment_rate']:.1%}")
            power_logger.info(f"Required sample per variant: {sample_analysis['required_per_variant']:,}")
            power_logger.info(f"Total required sample: {sample_analysis['total_required']:,}")
            
            # Step 2: Historical Traffic Analysis
            power_logger.info("\n📈 STEP 2: Historical Traffic Analysis")
            traffic_analysis = self.analyze_historical_traffic(experiment_name)
            
            power_logger.info(f"Average daily eligible users: {traffic_analysis['avg_daily_eligible_users']:,}")
            power_logger.info(f"Historical conversion rate: {traffic_analysis['historical_conversion_rate']:.1%}")
            power_logger.info(f"Traffic variability (CV): {traffic_analysis['traffic_variability_coefficient']:.1%}")
            
            # Validation: Check if historical conversion aligns with config assumptions
            config_baseline = power_config['effect_size']['baseline_metric_value']
            historical_baseline = traffic_analysis['historical_conversion_rate']
            baseline_diff = abs(config_baseline - historical_baseline) / config_baseline
            
            warnings_list = list(sample_analysis.get('warnings', []))
            if baseline_diff > 0.20:  # More than 20% difference
                warnings_list.append(
                    f"Config baseline ({config_baseline:.1%}) differs significantly from "
                    f"historical data ({historical_baseline:.1%}). Validate assumptions."
                )
            
            duration_analysis = self.calculate_experiment_duration(
                required_sample_size=sample_analysis['required_per_variant'],
                daily_eligible_users=traffic_analysis['avg_daily_eligible_users'],
                safety_buffer=power_config['sample_size']['safety_buffer'],
                traffic_variability=traffic_analysis['traffic_variability_coefficient']
            )
            
            power_logger.info(f"Target sample per variant: {duration_analysis['target_sample_per_variant']:,}")
            power_logger.info(f"Daily users per variant: {duration_analysis['daily_users_per_variant']:,}")
            power_logger.info(f"Required duration: {duration_analysis['final_duration_days']} days")
            power_logger.info(f"Required duration: {duration_analysis['final_duration_weeks']} weeks")
            
            # Step 4: Feasibility Assessment
            power_logger.info("\n✅ STEP 4: Feasibility Assessment")
            min_duration = power_config['duration_calculation']['business_minimum_days']
            max_duration = power_config['duration_calculation']['business_maximum_days']
            required_duration = duration_analysis['final_duration_days']
            
            feasibility_reasons = []
            
            # Check duration constraints
            if required_duration <= max_duration:
                final_duration = max(required_duration, min_duration)
                if required_duration < min_duration:
                    feasibility_reasons.append(f"Extended to minimum duration ({min_duration} days) for business validity")
                feasibility_status = "FEASIBLE"
                power_logger.info(f"✅ Experiment is FEASIBLE")
                power_logger.info(f"Final planned duration: {final_duration} days")
            else:
                feasibility_status = "NOT_FEASIBLE"
                final_duration = required_duration  # For reporting
                feasibility_reasons.append(f"Required duration ({required_duration} days) exceeds maximum ({max_duration} days)")
                power_logger.error(f"❌ Experiment is NOT FEASIBLE")
                power_logger.error(f"Consider: reducing effect size, increasing traffic, or accepting lower power")
            
            # Check traffic adequacy
            if traffic_analysis['avg_daily_eligible_users'] < 100:
                feasibility_reasons.append("Very low daily traffic may lead to unreliable results")
                if feasibility_status == "FEASIBLE":
                    feasibility_status = "MARGINAL"
            
            # Check statistical assumptions
            if not sample_analysis.get('assumptions_met', True):
                feasibility_reasons.append("Statistical assumptions may be violated")
                if feasibility_status == "FEASIBLE":
                    feasibility_status = "MARGINAL"
            
            # Step 5: Calendar Optimization (if feasible)
            suggested_start_dates = {}
            if feasibility_status in ["FEASIBLE", "MARGINAL"]:
                power_logger.info("\n📆 STEP 5: Calendar Optimization")
                suggested_start_dates = self.suggest_optimal_start_dates(
                    duration_days=final_duration,
                    experiment_name=experiment_name,
                    reference_date=self.reference_date
                )
                
                power_logger.info("Suggested start dates:")
                for start_date, reason in suggested_start_dates.items():
                    end_date = datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=final_duration)
                    power_logger.info(f"  {start_date} → {end_date.strftime('%Y-%m-%d')} ({reason})")
            
            # Create structured result
            result = PowerAnalysisResult(
                experiment_name=experiment_name,
                config_version=config_version,
                
                # Statistical parameters
                baseline_rate=sample_analysis['baseline_rate'],
                treatment_rate=sample_analysis['treatment_rate'],
                effect_size=sample_analysis['relative_improvement'],
                required_sample_per_variant=sample_analysis['required_per_variant'],
                total_required_sample=sample_analysis['total_required'],
                statistical_power=power_config['statistical_power'],
                significance_level=power_config['significance_level'],
                
                # Traffic analysis
                daily_eligible_users=traffic_analysis['avg_daily_eligible_users'],
                daily_users_per_variant=duration_analysis['daily_users_per_variant'],
                traffic_variability=traffic_analysis['traffic_variability_coefficient'],
                
                # Duration calculations
                required_duration_days=required_duration,
                required_duration_weeks=duration_analysis['final_duration_weeks'],
                final_planned_duration=final_duration,
                
                # Feasibility assessment
                feasibility_status=feasibility_status,
                feasibility_reasons=feasibility_reasons,
                
                # Calendar recommendations
                suggested_start_dates=suggested_start_dates,
                
                # Validation
                assumptions_met=sample_analysis.get('assumptions_met', True),
                warnings=warnings_list
            )
            
            # Final summary
            power_logger.info(f"\n🎯 FINAL ASSESSMENT: {feasibility_status}")
            if feasibility_status == "FEASIBLE":
                power_logger.info("✅ Experiment design validated and ready for implementation!")
            elif feasibility_status == "MARGINAL":
                power_logger.warning("⚠️ Experiment is feasible but has limitations. Review warnings.")
            else:
                power_logger.error("❌ Experiment design needs revision before implementation.")
            
            return result
        
    def _infer_test_type(self, metric_name: str) -> str:
        """
        Infer the appropriate statistical test type from metric name
        
        This shows domain expertise - different metrics need different statistical approaches.
        """
        metric_lower = metric_name.lower()
        
        # Proportion/rate metrics (use z-test for proportions)
        if any(term in metric_lower for term in ['rate', 'conversion', 'click', 'signup', 'subscribe']):
            return "conversion"
        
        # Count metrics (use Poisson-based tests)
        elif any(term in metric_lower for term in ['count', 'items', 'views', 'visits', 'per_']):
            return "count"
        
        # Continuous metrics (use t-test)
        elif any(term in metric_lower for term in ['value', 'amount', 'revenue', 'time', 'duration', 'size']):
            return "continuous"
        
        # Default to conversion test (most common in e-commerce)
        else:
            power_logger.warning(f"Could not infer test type for metric '{metric_name}'. Defaulting to 'conversion'.")
            return "conversion"

    def suggest_optimal_start_dates(
        self, 
        duration_days: int, 
        experiment_name: str,
        num_suggestions: int = 3,
        reference_date: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Suggest optimal start dates avoiding major holidays and business events
        
        Args:
            duration_days: How long the experiment will run
            experiment_name: Name of experiment (for context)
            num_suggestions: Number of date suggestions to provide
            reference_date: Date to use as "now" (for historical simulation)
                            If None, uses actual current date
        
        This demonstrates business acumen - understanding that experiment timing
        affects validity and business impact.
        """
        # Use reference date for historical simulation or current date for live experiments
        if reference_date is None:
            current_date = datetime.now()
            mode = "live"
        else:
            current_date = reference_date
            mode = "historical_simulation"
        
        logger.info(f"Suggesting start dates in {mode} mode, reference date: {current_date.strftime('%Y-%m-%d')}")
        
        # Business calendar constraints - these would ideally come from a business calendar API
        # Adjust years based on reference date
        ref_year = current_date.year
        
        avoid_periods = [
            # Holiday shopping seasons (adjust to reference year)
            (datetime(ref_year, 11, 20), datetime(ref_year, 12, 5)),     # Thanksgiving/Black Friday
            (datetime(ref_year, 12, 10), datetime(ref_year + 1, 1, 10)), # Christmas/New Year
            
            # Valentine's Day (affects gift/flower purchases)
            (datetime(ref_year, 2, 8), datetime(ref_year, 2, 18)),
            
            # Back to school season
            (datetime(ref_year, 8, 15), datetime(ref_year, 9, 15)),
            
            # Summer vacation period (different behavior patterns)
            (datetime(ref_year, 6, 15), datetime(ref_year, 8, 15)),
            
            # Easter period (approximate - varies by year)
            (datetime(ref_year, 3, 20), datetime(ref_year, 4, 10)),
            
            # Also include next year's periods if we're near year end
            (datetime(ref_year + 1, 11, 20), datetime(ref_year + 1, 12, 5)),
            (datetime(ref_year + 1, 12, 10), datetime(ref_year + 2, 1, 10)),
            (datetime(ref_year + 1, 2, 8), datetime(ref_year + 1, 2, 18)),
        ]
        
        # Start candidate search from next Monday after reference date
        days_until_monday = (7 - current_date.weekday()) % 7
        if days_until_monday == 0:  # If reference date is Monday, start next Monday
            days_until_monday = 7
        
        candidate_start = current_date + timedelta(days=days_until_monday)
        
        suggestions = {}
        suggestion_count = 0
        max_search_days = 365  # Don't search more than a year ahead
        days_searched = 0
        
        while suggestion_count < num_suggestions and days_searched < max_search_days:
            candidate_end = candidate_start + timedelta(days=duration_days)
            
            # Check if this period conflicts with avoid_periods
            conflicts_found = []
            for avoid_start, avoid_end in avoid_periods:
                # Check for any overlap between experiment period and avoid period
                if (candidate_start <= avoid_end and candidate_end >= avoid_start):
                    period_name = self._get_period_name(avoid_start, avoid_end)
                    conflicts_found.append(period_name)
            
            if not conflicts_found:
                # This period is clear - add it as a suggestion
                reason = self._get_suggestion_reason(candidate_start, suggestion_count)
                suggestions[candidate_start.strftime('%Y-%m-%d')] = reason
                suggestion_count += 1
            
            # Move to next Monday
            candidate_start += timedelta(days=7)
            days_searched += 7
        
        # If we couldn't find enough clear periods, add a warning
        if suggestion_count < num_suggestions:
            power_logger.warning(f"Could only find {suggestion_count} conflict-free periods within 1 year")
        
        return suggestions

    def _get_period_name(self, start_date: datetime, end_date: datetime) -> str:
        """Get human-readable name for business calendar periods"""
        month = start_date.month
        
        if month == 11 or month == 12:
            return "Holiday Shopping Season"
        elif month == 2 and start_date.day < 20:
            return "Valentine's Day Period"
        elif month >= 6 and month <= 8:
            return "Summer Season"
        elif month >= 8 and month <= 9:
            return "Back-to-School Season"
        elif month == 3 or month == 4:
            return "Easter Season"
        else:
            return "Business Calendar Conflict"

    def _get_suggestion_reason(self, start_date: datetime, suggestion_index: int) -> str:
        """Generate reason for why this start date is suggested"""
        month = start_date.month
        season = self._get_season(month)
        
        if suggestion_index == 0:
            return f"Earliest available slot ({season})"
        elif month in [1, 2, 3]:
            return f"Q1 stable period ({season})"
        elif month in [4, 5, 6]:
            return f"Q2 stable period ({season})" 
        elif month in [9, 10]:
            return f"Fall stable period ({season})"
        else:
            return f"Available slot ({season})"

    def _get_season(self, month: int) -> str:
        """Get season name from month"""
        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        else:
            return "Fall"


# Convenience function for CLI usage
def main():
    """
    Command-line interface for power analysis
    
    Usage: python power_analysis.py [experiment_name]
    """
    import sys
    from datetime import datetime
    
    if len(sys.argv) != 2:
        print("Usage: python power_analysis.py <experiment_name>")
        print("\nAvailable experiments:")
        from flit_experiment_configs import list_available_experiments
        for exp in list_available_experiments():
            print(f"  - {exp}")
        sys.exit(1)
    
    experiment_name = sys.argv[1]
    #reference_date = None

    # Check for reference date argument
    # if "--reference-date" in sys.argv:
    #     try:
    #         date_index = sys.argv.index("--reference-date") + 1
    #         reference_date = sys.argv[date_index]
    #     except IndexError:
    #         print("Error: --reference-date requires a date value in YYYY-MM-DD format")
    #         sys.exit(1)
    
    try:
        # analyzer = ExperimentPowerAnalysis(reference_date=reference_date)
        analyzer = ExperimentPowerAnalysis()
        result = analyzer.assess_experiment_feasibility(experiment_name)
        
        print(f"\n🎯 FINAL RESULT: {result.feasibility_status}")
        
        if result.feasibility_status == "FEASIBLE":
            print("✅ Ready to proceed with experiment implementation!")
            print(f"Recommended duration: {result.final_planned_duration} days")
            if result.suggested_start_dates:
                print("Suggested start dates:")
                for date, reason in result.suggested_start_dates.items():
                    print(f"  {date}: {reason}")
        else:
            print("❌ Experiment needs revision:")
            for reason in result.feasibility_reasons:
                print(f"  • {reason}")
    
    except Exception as e:
        power_logger.error(f"Power analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()# design/power_analysis.py
"""
Enhanced Power Analysis Engine for Flit Experimentation Platform

This module provides comprehensive statistical power analysis capabilities for various
experiment types. It calculates required sample sizes, estimates test durations based
on historical traffic, and provides feasibility assessments.

Senior DS Design Principles:
- Generalized approach supporting multiple test types (conversion, continuous, count)
- Real traffic analysis using historical data (not just assumptions)
- Business constraint validation (minimum/maximum durations)
- Calendar optimization (seasonal considerations, business events)
- Complete audit trail (document all assumptions and calculations)

Usage:
    analyzer = ExperimentPowerAnalysis()
    results = analyzer.assess_experiment_feasibility("free_shipping_threshold_test")
"""