# tests/test_power_analysis.py
"""
Comprehensive tests for power analysis functionality

These tests ensure statistical correctness, configuration reliability,
and integration robustness. Critical for production deployment.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add the project root to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from design.power_analysis import ExperimentPowerAnalysis, PowerAnalysisResult
from flit_experiment_configs import get_experiment_config


class TestStatisticalCalculations:
    """Test the core statistical formulas for correctness"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = ExperimentPowerAnalysis()
    
    def test_proportion_sample_size_known_values(self):
        """Test proportion sample size calculation against known values"""
        # Known case: 5% baseline, 8% relative improvement, 80% power, 5% alpha
        # Expected result: approximately 12,500 per variant
        
        result = self.analyzer.calculate_test_sample_size(
            test_type="conversion",
            baseline_value=0.05,
            effect_size=0.08,
            power=0.80,
            alpha=0.05
        )
        
        # Validate statistical parameters
        assert result['baseline_rate'] == 0.05
        assert result['treatment_rate'] == pytest.approx(0.054, rel=0.001)  # 5% * 1.08
        assert result['relative_improvement'] == 0.08
        
        # Validate sample size is in reasonable range
        # Exact value depends on formula precision, but should be ~12,000-13,000
        assert 10000 <= result['required_per_variant'] <= 15000
        assert result['total_required'] == result['required_per_variant'] * 2
    
    def test_proportion_sample_size_edge_cases(self):
        """Test edge cases that could break the calculation"""
        
        # Very small baseline rate
        result = self.analyzer.calculate_test_sample_size(
            test_type="conversion",
            baseline_value=0.001,  # 0.1% baseline
            effect_size=0.50,      # 50% improvement (to 0.15%)
            power=0.80,
            alpha=0.05
        )
        
        assert result['baseline_rate'] == 0.001
        assert result['required_per_variant'] > 100000  # Should require large sample
        assert len(result['warnings']) > 0  # Should warn about normal approximation
    
    def test_continuous_metric_sample_size(self):
        """Test sample size calculation for continuous metrics (AOV, etc.)"""
        
        result = self.analyzer.calculate_test_sample_size(
            test_type="continuous",
            baseline_value=50.0,   # $50 AOV
            effect_size=0.10,      # 10% improvement
            power=0.80,
            alpha=0.05
        )
        
        assert result['baseline_mean'] == 50.0
        assert result['treatment_mean'] == 55.0  # 50 * 1.10
        assert result['test_type'] == 'two_sample_t_test'
        assert result['required_per_variant'] > 0
        
        # Should warn about coefficient of variation assumption
        warning_messages = ' '.join(result['warnings'])
        assert 'coefficient of variation' in warning_messages.lower()
    
    def test_count_metric_sample_size(self):
        """Test sample size calculation for count metrics (items per order)"""
        
        result = self.analyzer.calculate_test_sample_size(
            test_type="count",
            baseline_value=2.5,    # 2.5 items per order
            effect_size=0.15,      # 15% improvement
            power=0.80,
            alpha=0.05
        )
        
        assert result['baseline_rate'] == 2.5
        assert result['treatment_rate'] == pytest.approx(2.875)  # 2.5 * 1.15
        assert result['test_type'] == 'two_poisson_rate_test'
        assert result['required_per_variant'] > 0
    
    def test_unequal_allocation(self):
        """Test that unequal allocation (70/30 split) works correctly"""
        
        result = self.analyzer.calculate_test_sample_size(
            test_type="conversion",
            baseline_value=0.05,
            effect_size=0.08,
            power=0.80,
            alpha=0.05,
            allocation_ratio=0.3  # 30% in treatment
        )
        
        assert result['allocation_ratio'] == 0.3
        # Unequal allocation typically requires larger samples
        # Should be larger than equal allocation case
        assert result['required_per_variant'] > 12000
    
    def test_invalid_inputs(self):
        """Test that invalid inputs raise appropriate errors"""
        
        with pytest.raises(ValueError, match="Unsupported test type"):
            self.analyzer.calculate_test_sample_size(
                test_type="invalid_type",
                baseline_value=0.05,
                effect_size=0.08
            )
        
        # Test negative baseline rate
        with pytest.raises((ValueError, AssertionError)):
            self.analyzer.calculate_test_sample_size(
                test_type="conversion",
                baseline_value=-0.01,  # Invalid negative rate
                effect_size=0.08
            )


class TestTrafficAnalysis:
    """Test traffic analysis with mocked BigQuery responses"""
    
    def setup_method(self):
        """Set up test fixtures with mocked BigQuery client"""
        with patch('design.power_analysis.bigquery.Client'):
            self.analyzer = ExperimentPowerAnalysis()
    
    @patch('design.power_analysis.get_experiment_config')
    def test_traffic_analysis_with_mock_data(self, mock_get_config):
        """Test traffic analysis with realistic mock BigQuery response"""
        
        # Mock experiment config
        mock_get_config.return_value = {
            'population': {
                'eligibility_criteria': {
                    'include': {
                        'customer_types': ['new', 'returning'],
                        'countries': ['US', 'CA', 'UK'],
                        'min_cart_value': 20.0
                    },
                    'exclude': {
                        'vip_customers': True,
                        'employee_accounts': True
                    }
                }
            }
        }
        
        # Mock BigQuery response
        mock_df = pd.DataFrame({
            'avg_daily_eligible_users': [1500],
            'stddev_daily_eligible_users': [200],
            'min_daily_eligible_users': [1000],
            'max_daily_eligible_users': [2000],
            'avg_conversion_rate': [0.045],
            'stddev_conversion_rate': [0.008],
            'overall_avg_order_value': [52.30],
            'days_analyzed': [90],
            'analysis_start_date': [datetime(2024, 1, 1)],
            'analysis_end_date': [datetime(2024, 3, 30)],
            'day_of_week_patterns': [[]]  # Simplified for test
        })
        
        self.analyzer.client.query.return_value.to_dataframe.return_value = mock_df
        
        # Run traffic analysis
        result = self.analyzer.analyze_historical_traffic('test_experiment')
        
        # Validate results
        assert result['avg_daily_eligible_users'] == 1500
        assert result['stddev_daily_eligible_users'] == 200
        assert result['historical_conversion_rate'] == 0.045
        assert result['traffic_variability_coefficient'] == pytest.approx(200/1500, rel=0.01)
        assert result['days_analyzed'] == 90
    
    def test_traffic_analysis_no_data(self):
        """Test handling when no eligible users are found"""
        
        # Mock empty BigQuery response
        mock_df = pd.DataFrame()  # Empty dataframe
        self.analyzer.client.query.return_value.to_dataframe.return_value = mock_df
        
        with pytest.raises(ValueError, match="No eligible users found"):
            self.analyzer.analyze_historical_traffic('test_experiment')
    
    def test_build_include_conditions(self):
        """Test SQL condition building from eligibility criteria"""
        
        include_criteria = {
            'customer_types': ['new', 'returning'],
            'countries': ['US', 'CA'],
            'min_cart_value': 25.0
        }
        
        conditions = self.analyzer._build_include_conditions(include_criteria)
        
        # Should generate appropriate SQL conditions
        assert len(conditions) >= 2  # At least country and value conditions
        
        # Check that countries are included
        country_condition = next((c for c in conditions if 'country' in c.lower()), None)
        assert country_condition is not None
        assert 'US' in country_condition and 'CA' in country_condition
    
    def test_build_exclude_conditions(self):
        """Test SQL exclusion condition building"""
        
        exclude_criteria = {
            'vip_customers': True,
            'employee_accounts': True,
            'test_accounts': True
        }
        
        conditions = self.analyzer._build_exclude_conditions(exclude_criteria)
        
        # Should generate exclusion conditions
        assert len(conditions) > 0
        
        # Check for VIP exclusion (based on LTV)
        vip_condition = next((c for c in conditions if '1000' in c), None)
        assert vip_condition is not None
        
        # Check for employee email exclusion
        employee_condition = next((c for c in conditions if 'employee' in c.lower()), None)
        assert employee_condition is not None


class TestDurationCalculation:
    """Test experiment duration calculations"""
    
    def setup_method(self):
        with patch('design.power_analysis.bigquery.Client'):
            self.analyzer = ExperimentPowerAnalysis()
    
    def test_duration_calculation_basic(self):
        """Test basic duration calculation logic"""
        
        result = self.analyzer.calculate_experiment_duration(
            required_sample_size=12500,
            daily_eligible_users=1000,
            allocation_per_variant=0.5,
            safety_buffer=1.1,
            traffic_variability=0.15
        )
        
        # Expected: 12500 * 1.1 / (1000 * 0.5) = 27.5 days base
        # With variability adjustment and minimum duration
        assert result['target_sample_per_variant'] == 13750  # 12500 * 1.1
        assert result['daily_users_per_variant'] == 500      # 1000 * 0.5
        assert result['base_duration_days'] == 28            # ceil(13750 / 500)
        assert result['final_duration_days'] >= 14           # Minimum duration enforced
        
        # Should apply safety buffer and variability adjustments
        assert result['safety_buffer_applied'] == 1.1
        assert result['traffic_variability_considered'] == 0.15
    
    def test_minimum_duration_enforcement(self):
        """Test that minimum duration is enforced even for large traffic"""
        
        result = self.analyzer.calculate_experiment_duration(
            required_sample_size=1000,   # Small sample
            daily_eligible_users=10000,  # Large traffic
            allocation_per_variant=0.5
        )
        
        # Even though we could collect sample in 1 day, enforce 14-day minimum
        assert result['final_duration_days'] >= 14


class TestCalendarOptimization:
    """Test calendar optimization and business logic"""
    
    def setup_method(self):
        with patch('design.power_analysis.bigquery.Client'):
            self.analyzer = ExperimentPowerAnalysis()
    
    def test_suggest_optimal_start_dates(self):
        """Test that optimal start dates avoid business conflicts"""
        
        # Test suggesting dates for a 28-day experiment
        suggestions = self.analyzer.suggest_optimal_start_dates(
            duration_days=28,
            experiment_name='test_experiment',
            num_suggestions=3
        )
        
        # Should return suggestions
        assert len(suggestions) > 0
        assert len(suggestions) <= 3
        
        # Each suggestion should have date and reason
        for date_str, reason in suggestions.items():
            # Validate date format
            datetime.strptime(date_str, '%Y-%m-%d')  # Should not raise error
            assert len(reason) > 0
            assert isinstance(reason, str)
    
    def test_avoid_holiday_periods(self):
        """Test that holiday periods are properly avoided"""
        
        # This is hard to test deterministically since it depends on current date
        # But we can test the helper methods
        
        # Test period name detection
        christmas_start = datetime(2024, 12, 20)
        christmas_end = datetime(2024, 12, 30)
        period_name = self.analyzer._get_period_name(christmas_start, christmas_end)
        
        assert 'holiday' in period_name.lower() or 'christmas' in period_name.lower()
    
    def test_get_season_detection(self):
        """Test season detection from month"""
        
        assert self.analyzer._get_season(1) == "Winter"
        assert self.analyzer._get_season(4) == "Spring"
        assert self.analyzer._get_season(7) == "Summer"
        assert self.analyzer._get_season(10) == "Fall"


class TestFullFeasibilityAnalysis:
    """Integration tests for complete feasibility analysis"""
    
    def setup_method(self):
        with patch('design.power_analysis.bigquery.Client'):
            self.analyzer = ExperimentPowerAnalysis()
    
    @patch('design.power_analysis.get_experiment_config')
    @patch('design.power_analysis.get_package_version')
    def test_feasible_experiment_end_to_end(self, mock_version, mock_config):
        """Test a complete feasible experiment analysis"""
        
        # Mock configuration
        mock_config.return_value = {
            'metrics': {
                'primary': {'name': 'conversion_rate'}
            },
            'power_analysis': {
                'effect_size': {
                    'baseline_metric_value': 0.045,
                    'magnitude': 0.08
                },
                'statistical_power': 0.80,
                'significance_level': 0.05,
                'sample_size': {'safety_buffer': 1.1},
                'duration_calculation': {
                    'business_minimum_days': 14,
                    'business_maximum_days': 56
                }
            },
            'population': {
                'eligibility_criteria': {
                    'include': {'countries': ['US']},
                    'exclude': {}
                }
            }
        }
        
        mock_version.return_value = "1.0.0"
        
        # Mock traffic analysis result
        mock_traffic_df = pd.DataFrame({
            'avg_daily_eligible_users': [1500],
            'stddev_daily_eligible_users': [150],
            'min_daily_eligible_users': [1200],
            'max_daily_eligible_users': [1800],
            'avg_conversion_rate': [0.045],
            'stddev_conversion_rate': [0.005],
            'overall_avg_order_value': [52.0],
            'days_analyzed': [90],
            'analysis_start_date': [datetime(2024, 1, 1)],
            'analysis_end_date': [datetime(2024, 3, 30)],
            'day_of_week_patterns': [[]]
        })
        
        self.analyzer.client.query.return_value.to_dataframe.return_value = mock_traffic_df
        
        # Run full analysis
        result = self.analyzer.assess_experiment_feasibility('test_experiment')
        
        # Validate result structure
        assert isinstance(result, PowerAnalysisResult)
        assert result.experiment_name == 'test_experiment'
        assert result.config_version == "1.0.0"
        
        # Should be feasible with good traffic and reasonable effect size
        assert result.feasibility_status in ['FEASIBLE', 'MARGINAL']
        
        # Validate statistical parameters
        assert result.baseline_rate == 0.045
        assert result.effect_size == 0.08
        assert result.required_sample_per_variant > 0
        
        # Validate traffic analysis
        assert result.daily_eligible_users == 1500
        assert result.traffic_variability > 0
        
        # Should have duration calculations
        assert result.required_duration_days > 0
        assert result.final_planned_duration >= result.required_duration_days
    
    @patch('design.power_analysis.get_experiment_config')
    @patch('design.power_analysis.get_package_version')
    def test_infeasible_experiment(self, mock_version, mock_config):
        """Test an infeasible experiment (too little traffic)"""
        
        # Mock configuration with very small effect size (hard to detect)
        mock_config.return_value = {
            'metrics': {'primary': {'name': 'conversion_rate'}},
            'power_analysis': {
                'effect_size': {
                    'baseline_metric_value': 0.045,
                    'magnitude': 0.01  # Only 1% improvement - very small
                },
                'statistical_power': 0.80,
                'significance_level': 0.05,
                'sample_size': {'safety_buffer': 1.1},
                'duration_calculation': {
                    'business_minimum_days': 14,
                    'business_maximum_days': 28  # Short maximum duration
                }
            },
            'population': {
                'eligibility_criteria': {'include': {'countries': ['US']}, 'exclude': {}}
            }
        }
        
        mock_version.return_value = "1.0.0"
        
        # Mock very low traffic
        mock_traffic_df = pd.DataFrame({
            'avg_daily_eligible_users': [50],  # Very low traffic
            'stddev_daily_eligible_users': [10],
            'min_daily_eligible_users': [30],
            'max_daily_eligible_users': [70],
            'avg_conversion_rate': [0.045],
            'stddev_conversion_rate': [0.005],
            'overall_avg_order_value': [52.0],
            'days_analyzed': [90],
            'analysis_start_date': [datetime(2024, 1, 1)],
            'analysis_end_date': [datetime(2024, 3, 30)],
            'day_of_week_patterns': [[]]
        })
        
        self.analyzer.client.query.return_value.to_dataframe.return_value = mock_traffic_df
        
        # Run analysis
        result = self.analyzer.assess_experiment_feasibility('test_experiment')
        
        # Should be not feasible due to low traffic + small effect size
        assert result.feasibility_status in ['NOT_FEASIBLE', 'MARGINAL']
        assert len(result.feasibility_reasons) > 0


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def setup_method(self):
        with patch('design.power_analysis.bigquery.Client'):
            self.analyzer = ExperimentPowerAnalysis()
    
    def test_bigquery_connection_failure(self):
        """Test handling of BigQuery connection failures"""
        
        # Mock BigQuery failure
        self.analyzer.client.query.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception):
            self.analyzer.analyze_historical_traffic('test_experiment')
    
    @patch('design.power_analysis.get_experiment_config')
    def test_invalid_experiment_config(self, mock_config):
        """Test handling of invalid experiment configurations"""
        
        # Mock invalid config (missing required fields)
        mock_config.return_value = {
            'metrics': {},  # Missing primary metric
            'power_analysis': {}  # Missing required fields
        }
        
        with pytest.raises((KeyError, ValueError)):
            self.analyzer.assess_experiment_feasibility('invalid_experiment')


# Test fixtures and utilities
@pytest.fixture
def sample_power_result():
    """Create a sample PowerAnalysisResult for testing"""
    return PowerAnalysisResult(
        experiment_name="test_experiment",
        config_version="1.0.0",
        baseline_rate=0.045,
        treatment_rate=0.0486,
        effect_size=0.08,
        required_sample_per_variant=12500,
        total_required_sample=25000,
        statistical_power=0.80,
        significance_level=0.05,
        daily_eligible_users=1000,
        daily_users_per_variant=500,
        traffic_variability=0.15,
        required_duration_days=28,
        required_duration_weeks=4.0,
        final_planned_duration=28,
        feasibility_status="FEASIBLE",
        feasibility_reasons=[],
        suggested_start_dates={"2024-02-01": "Optimal timing"},
        assumptions_met=True,
        warnings=[]
    )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])