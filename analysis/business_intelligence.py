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

# Import our statistical engine and experiment configs
from statistical_engine import StatisticalAnalysisEngine, ExperimentData, create_experiment_data
import flit_experiment_configs

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
                          metric_column: str = None,
                          write_to_warehouse: bool = False,
                          use_legacy_schema: bool = False) -> Dict[str, Any]:
        """
        Run complete analysis pipeline for an experiment
        
        Args:
            experiment_name: Name of experiment to analyze
            control_column: Column indicating control/treatment assignment  
            metric_column: Primary metric to analyze
            write_to_warehouse: Whether to write results to BigQuery warehouse
            use_legacy_schema: If True, use old single-table schema. If False (default), use normalized schema
            
        Returns:
            Complete analysis results with business insights
        """
        logger.info(f"Starting analysis for experiment: {experiment_name}")
        
        # Load experiment configuration to get metric definitions
        experiment_config = flit_experiment_configs.get_experiment_config(experiment_name)
        
        # Get primary metric name from config if not provided
        if metric_column is None:
            primary_metric_config = experiment_config.get('metrics', {}).get('primary', {})
            metric_column = primary_metric_config.get('name', 'orders_per_eligible_user')
        
        logger.info(f"Using primary metric from config: {metric_column}")
        
        # Load experiment data from BigQuery
        data = self._load_experiment_data(experiment_name, control_column, metric_column)
        
        # Run statistical analysis on primary metric (unchanged)
        statistical_results = self.engine.analyze_experiment(data)
        
        # Run secondary metrics guardrail analysis (new, additive)
        secondary_results = self._analyze_secondary_metrics()
        
        # Convert to business insights (unchanged)
        business_insights = self._create_business_insights(statistical_results, data)
        
        # Generate recommendation (now considers secondary metrics and uses config thresholds)
        recommendation = self._make_recommendation(statistical_results, business_insights, secondary_results, experiment_config)
        
        # Combine all results (extended with secondary metrics)
        complete_results = {
            'experiment_info': {
                'name': experiment_name,
                'analysis_date': datetime.now().isoformat(),
                'primary_metric': metric_column,
                'secondary_metrics': getattr(self, '_secondary_metrics', []),
                'sample_size': len(data.control) + len(data.treatment)
            },
            'statistical_results': statistical_results,
            'secondary_metrics_analysis': secondary_results,
            'business_insights': business_insights,
            'recommendation': recommendation.__dict__
        }
        
        self.results = complete_results
        
        # Write to warehouse if requested (normalized schema by default)
        if write_to_warehouse:
            if use_legacy_schema:
                warehouse_status = self.write_results_to_bigquery()
                logger.info(f"Legacy warehouse write status: {warehouse_status}")
            else:
                warehouse_status = self.write_results_to_bigquery_normalized()
                logger.info(f"Normalized warehouse write status: {warehouse_status}")
            complete_results['warehouse_write_status'] = warehouse_status
        
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
            filepath = f"/Users/kevin/Documents/repos/flit-experiments/analysis/outputs/reports/detailed_report_{timestamp}.json"
        
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
            filepath = f"/Users/kevin/Documents/repos/flit-experiments/analysis/outputs/dashboards/dashboard_data_{timestamp}.json"
        
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
            'imbalance_factor': stats['metadata']['imbalance_factor'],
            
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
    
    def write_results_to_bigquery_normalized(self) -> str:
        """
        Write analysis results to normalized BigQuery schema
        
        Creates two tables:
        1. int_experiment_results_primary - One row per experiment (primary metrics + summary)
        2. int_experiment_results_secondary - One row per secondary metric test
        
        Returns:
            String indicating success/failure with table paths
        """
        if not self.results:
            raise ValueError("No analysis results available. Run analyze_experiment first.")
        
        logger.info("Writing analysis results to normalized BigQuery schema...")
        
        try:
            # Write primary metrics table
            primary_status = self._write_primary_metrics_table()
            logger.info(f"Primary table status: {primary_status}")
            
            # Write secondary metrics table
            secondary_status = self._write_secondary_metrics_table()
            logger.info(f"Secondary table status: {secondary_status}")
            
            if "ERROR" in primary_status or "ERROR" in secondary_status:
                return f"PARTIAL_FAILURE: Primary={primary_status}, Secondary={secondary_status}"
            else:
                return f"SUCCESS: Primary={primary_status}, Secondary={secondary_status}"
                
        except Exception as e:
            logger.error(f"Failed to write to BigQuery: {e}")
            return f"ERROR: {str(e)}"
    
    def write_results_to_bigquery(self) -> str:
        """
        Write analysis results to BigQuery for BI dashboard consumption
        
        Logic:
        - If table exists: append the new row
        - If table doesn't exist: create table with the new row (overwrite mode)
        
        Flattens self.results into a single row and uploads to:
        flit-data-platform.flit_intermediate.int_experiment_results
        
        Returns:
            String indicating success/failure with table path
        """
        if not self.results:
            raise ValueError("No analysis results available. Run analyze_experiment first.")
        
        logger.info("Writing analysis results to BigQuery...")
        
        # Flatten results into BigQuery-ready row
        flattened_row = self._flatten_results_for_bigquery()
        
        # Define target table
        table_id = f"{self.project_id}.flit_intermediate.int_experiment_results"
        dataset_id = "flit_intermediate"
        table_name = "int_experiment_results"
        
        try:
            # Check if table exists
            try:
                table = self.client.get_table(table_id)
                table_exists = True
                logger.info(f"Table {table_id} exists - will append new row")
            except Exception:
                table_exists = False
                logger.info(f"Table {table_id} does not exist - will create new table")
            
            # Always use dataframe method (handles type conversion automatically)
            df = pd.DataFrame([flattened_row])
            
            if table_exists:
                # Table exists: append the row
                job_config = bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                    create_disposition=bigquery.CreateDisposition.CREATE_NEVER  # Fail if table missing
                )
                operation_type = "APPENDED to"
            else:
                # Table doesn't exist: create new table with this row
                job_config = bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Overwrite if exists
                    create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED  # Create if doesn't exist
                )
                operation_type = "CREATED"
            
            # Upload to BigQuery
            job = self.client.load_table_from_dataframe(df, table_id, job_config=job_config)
            job.result()  # Wait for job to complete
            
            logger.info(f"Successfully {operation_type.lower()} {table_id}")
            return f"SUCCESS: {operation_type} {table_id}"
                
        except Exception as e:
            logger.error(f"Failed to write to BigQuery: {e}")
            return f"ERROR: {str(e)}"
    
    def _write_primary_metrics_table(self) -> str:
        """Write primary metrics to int_experiment_results_primary table"""
        
        table_id = f"{self.project_id}.flit_intermediate.int_experiment_results_primary"
        primary_row = self._create_primary_metrics_row()
        
        return self._write_table_with_fallback(table_id, primary_row, "PRIMARY")
    
    def _write_secondary_metrics_table(self) -> str:
        """Write secondary metrics to int_experiment_results_secondary table (one row per metric)"""
        
        table_id = f"{self.project_id}.flit_intermediate.int_experiment_results_secondary"
        secondary_rows = self._create_secondary_metrics_rows()
        
        if not secondary_rows:
            logger.info("No secondary metrics to write")
            return "SUCCESS: No secondary metrics"
        
        return self._write_table_with_fallback(table_id, secondary_rows, "SECONDARY")
    
    def _write_table_with_fallback(self, table_id: str, data, table_type: str) -> str:
        """Generic method to write table with create/append logic"""
        
        # Ensure data is a list for DataFrame creation
        if isinstance(data, dict):
            data = [data]
        
        try:
            # Check if table exists
            try:
                table = self.client.get_table(table_id)
                table_exists = True
                logger.info(f"{table_type} table {table_id} exists - will append")
            except Exception:
                table_exists = False
                logger.info(f"{table_type} table {table_id} does not exist - will create")
            
            # Create DataFrame and write to BigQuery
            df = pd.DataFrame(data)
            
            if table_exists:
                job_config = bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                    create_disposition=bigquery.CreateDisposition.CREATE_NEVER
                )
                operation_type = "APPENDED to"
            else:
                job_config = bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                    create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED
                )
                operation_type = "CREATED"
            
            job = self.client.load_table_from_dataframe(df, table_id, job_config=job_config)
            job.result()  # Wait for completion
            
            logger.info(f"Successfully {operation_type.lower()} {table_id}")
            return f"SUCCESS: {operation_type} {table_id}"
            
        except Exception as e:
            logger.error(f"Failed to write {table_type} table: {e}")
            return f"ERROR: {str(e)}"
    
    def _create_primary_metrics_row(self) -> Dict[str, Any]:
        """Create primary metrics row for normalized schema"""
        
        results = self.results
        stats = results.get('statistical_results', {})
        secondary = results.get('secondary_metrics_analysis', {})
        recommendation = results.get('recommendation', {})
        experiment_info = results.get('experiment_info', {})
        
        # Generate unique analysis ID for linking tables
        analysis_id = f"{experiment_info.get('name', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        row = {
            # Primary identifiers
            'analysis_id': analysis_id,
            'experiment_name': experiment_info.get('name'),
            'analysis_date': datetime.now(),
            'analysis_version': '1.0.0',
            
            # Primary metric results
            'primary_metric_name': experiment_info.get('primary_metric'),
            'total_sample_size': experiment_info.get('sample_size'),
            'control_sample_size': stats.get('data_summary', {}).get('control', {}).get('count'),
            'treatment_sample_size': stats.get('data_summary', {}).get('treatment', {}).get('count'),
            'balance_ratio': stats.get('metadata', {}).get('balance_ratio'),
            
            # Effect measurements
            'control_mean': stats.get('data_summary', {}).get('control', {}).get('mean'),
            'treatment_mean': stats.get('data_summary', {}).get('treatment', {}).get('mean'),
            'absolute_difference': stats.get('effect_sizes', {}).get('absolute_difference'),
            'relative_lift_percent': stats.get('effect_sizes', {}).get('relative_lift_percent'),
            'cohens_d': stats.get('effect_sizes', {}).get('cohens_d'),
            
            # Statistical significance
            'p_value': stats.get('significance_tests', {}).get('welch_ttest', {}).p_value if stats.get('significance_tests', {}).get('welch_ttest') else None,
            'statistically_significant': stats.get('significance_tests', {}).get('welch_ttest', {}).significant if stats.get('significance_tests', {}).get('welch_ttest') else None,
            'statistical_test_used': 'welch_ttest',
            'statistical_power': stats.get('power_analysis', {}).get('achieved_power'),
            'power_adequate': stats.get('power_analysis', {}).get('power_adequate'),
            
            # Confidence intervals
            'relative_lift_ci_lower': stats.get('confidence_intervals', {}).get('relative_lift_ci', {}).get('lower', 0) * 100,
            'relative_lift_ci_upper': stats.get('confidence_intervals', {}).get('relative_lift_ci', {}).get('upper', 0) * 100,
            
            # Note: Secondary metrics details moved to separate secondary table for normalized schema
            
            # Final business decision
            'final_decision': recommendation.get('decision'),
            'confidence_level': recommendation.get('confidence'),
            'risk_level': recommendation.get('risk_level'),
            'launch_ready': recommendation.get('decision') in ['LAUNCH', 'STRONG_LAUNCH', 'CAUTIOUS_LAUNCH'],
            'needs_more_data': recommendation.get('decision') == 'EXTEND_TEST',
            
            # Audit trail
            'framework_version': '1.0.0'
        }
        
        # Store analysis_id for secondary metrics linking
        self._current_analysis_id = analysis_id
        
        return {k: v for k, v in row.items() if v is not None}
    
    def _create_secondary_metrics_rows(self) -> List[Dict[str, Any]]:
        """Create secondary metrics rows (one row per metric)"""
        
        results = self.results
        secondary = results.get('secondary_metrics_analysis', {})
        guardrails = secondary.get('guardrail_results', {})
        experiment_info = results.get('experiment_info', {})
        
        rows = []
        analysis_id = getattr(self, '_current_analysis_id', f"{experiment_info.get('name', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # Create one row per secondary metric
        for metric_name, metric_result in guardrails.items():
            if metric_name == '_overall':  # Skip overall summary
                continue
                
            if not isinstance(metric_result, dict):
                continue
                
            row = {
                # Linking identifiers
                'analysis_id': analysis_id,
                'experiment_name': experiment_info.get('name'),
                'analysis_date': datetime.now(),
                
                # Secondary metric details
                'secondary_metric_name': metric_name,
                'secondary_metric_effect_percent': metric_result.get('relative_effect_percent'),
                'secondary_metric_status': metric_result.get('status'),
                'secondary_metric_interpretation': metric_result.get('interpretation'),
                'guardrail_threshold_used': metric_result.get('threshold_used'),
                
                # Statistical details (if available)
                'control_mean': metric_result.get('control_mean'),
                'treatment_mean': metric_result.get('treatment_mean'),
                'absolute_difference': metric_result.get('absolute_difference'),
                
                # Metadata
                'analysis_version': '1.0.0'
            }
            
            rows.append({k: v for k, v in row.items() if v is not None})
        
        return rows
    
    def _flatten_results_for_bigquery(self) -> Dict[str, Any]:
        """
        Flatten analysis results into single BigQuery row with no JSON columns
        
        Returns:
            Dictionary representing one row for the int_experiment_results table
        """
        results = self.results
        stats = results.get('statistical_results', {})
        secondary = results.get('secondary_metrics_analysis', {})
        recommendation = results.get('recommendation', {})
        experiment_info = results.get('experiment_info', {})
        
        # Build flattened row
        row = {
            # Primary identifiers
            'experiment_name': experiment_info.get('name'),
            'analysis_date': datetime.now(),
            'analysis_version': '1.0.0',
            
            # Experiment metadata
            'primary_metric_name': experiment_info.get('primary_metric'),
            'secondary_metrics_analyzed': ','.join(experiment_info.get('secondary_metrics', [])),
            'total_sample_size': experiment_info.get('sample_size'),
            
            # Sample composition
            'control_sample_size': stats.get('data_summary', {}).get('control', {}).get('count'),
            'treatment_sample_size': stats.get('data_summary', {}).get('treatment', {}).get('count'),
            'balance_ratio': stats.get('metadata', {}).get('balance_ratio'),
            
            # Primary metric results
            'control_mean': stats.get('data_summary', {}).get('control', {}).get('mean'),
            'treatment_mean': stats.get('data_summary', {}).get('treatment', {}).get('mean'),
            'absolute_difference': stats.get('effect_sizes', {}).get('absolute_difference'),
            'relative_lift_percent': stats.get('effect_sizes', {}).get('relative_lift_percent'),
            'cohens_d': stats.get('effect_sizes', {}).get('cohens_d'),
            
            # Statistical significance
            'p_value': stats.get('significance_tests', {}).get('welch_ttest', {}).p_value if stats.get('significance_tests', {}).get('welch_ttest') else None,
            'statistically_significant': stats.get('significance_tests', {}).get('welch_ttest', {}).significant if stats.get('significance_tests', {}).get('welch_ttest') else None,
            'statistical_test_used': 'welch_ttest',
            
            # Confidence intervals
            'relative_lift_ci_lower': stats.get('confidence_intervals', {}).get('relative_lift_ci', {}).get('lower', 0) * 100,
            'relative_lift_ci_upper': stats.get('confidence_intervals', {}).get('relative_lift_ci', {}).get('upper', 0) * 100,
            'absolute_diff_ci_lower': stats.get('confidence_intervals', {}).get('absolute_difference_ci', {}).get('lower'),
            'absolute_diff_ci_upper': stats.get('confidence_intervals', {}).get('absolute_difference_ci', {}).get('upper'),
            
            # Power analysis
            'statistical_power': stats.get('power_analysis', {}).get('achieved_power'),
            'power_adequate': stats.get('power_analysis', {}).get('power_adequate'),
            
            # Secondary metrics summary
            'secondary_metrics_status': secondary.get('guardrail_results', {}).get('_overall', {}).get('status'),
            'secondary_alerts_count': secondary.get('guardrail_results', {}).get('_overall', {}).get('alerts_count', 0),
            'secondary_warnings_count': secondary.get('guardrail_results', {}).get('_overall', {}).get('warnings_count', 0),
            'secondary_passed_count': secondary.get('guardrail_results', {}).get('_overall', {}).get('passed_count', 0),
            
            # Business recommendation
            'final_decision': recommendation.get('decision'),
            'confidence_level': recommendation.get('confidence'),
            'risk_level': recommendation.get('risk_level'),
            'launch_ready': recommendation.get('decision') in ['LAUNCH', 'STRONG_LAUNCH', 'CAUTIOUS_LAUNCH'],
            'needs_more_data': recommendation.get('decision') == 'EXTEND_TEST',
            
            # Dashboard helpers
            'result_color': 'green' if recommendation.get('decision') in ['LAUNCH', 'STRONG_LAUNCH'] else 
                           'yellow' if recommendation.get('decision') in ['CONSIDER_LAUNCH', 'CAUTIOUS_LAUNCH', 'EXTEND_TEST'] else 'red',
            'effect_magnitude_category': self._categorize_effect_magnitude(stats.get('effect_sizes', {}).get('relative_lift', 0)),
            
            # Audit trail
            'analysis_duration_seconds': None,  # Could add timing if needed
            'framework_version': '1.0.0'
        }
        
        # Add individual secondary metrics if available
        if 'guardrail_results' in secondary:
            guardrails = secondary['guardrail_results']
            for metric_name, metric_result in guardrails.items():
                if metric_name != '_overall' and isinstance(metric_result, dict):
                    # Add individual secondary metric columns
                    row[f"{metric_name}_effect"] = metric_result.get('relative_effect_percent')
                    row[f"{metric_name}_status"] = metric_result.get('status')
        
        # Remove None values for cleaner data
        return {k: v for k, v in row.items() if v is not None}
    
    def _categorize_effect_magnitude(self, relative_lift: float) -> str:
        """Categorize effect size for dashboard display"""
        abs_effect = abs(relative_lift)
        
        if abs_effect >= 0.20:
            return "LARGE"
        elif abs_effect >= 0.10:
            return "MODERATE" 
        elif abs_effect >= 0.05:
            return "SMALL"
        else:
            return "MINIMAL"
    
    def create_visualizations(self, output_dir: str = None) -> Dict[str, str]:
        """
        Generate key visualizations for stakeholder communication
        
        Creates a small set of focused charts that tell the story clearly.
        Avoids statistical jargon and focuses on business impact.
        """
        if not self.results:
            raise ValueError("Must run analyze_experiment first")
        
        if output_dir is None:
            output_dir = "/Users/kevin/Documents/repos/flit-experiments/analysis/outputs/visualizations"
        
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
        
        # User-level aggregation query - use config-defined metric names
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
          COUNT(*) as orders_per_eligible_user,
          -- Note: revenue metrics not available in current schema
          -- SUM(revenue) as revenue_per_eligible_user,  -- Would need revenue column
          -- AVG(revenue) as average_order_value,        -- Would need revenue column  
          CASE WHEN COUNT(*) > 0 THEN 1.0 ELSE 0.0 END as active_user_rate
        FROM `{self.project_id}.flit_marts.mart_free_shipping_threshold_analysis`
        WHERE time_period = 'experiment_period'
        GROUP BY user_id, treatment_group
        HAVING treatment_group IN ('control', 'treatment')
        """
        
        df = self.client.query(query).to_dataframe()
        
        if len(df) == 0:
            raise ValueError(f"No data found for experiment: {experiment_name}")
        
        # Load experiment config to get secondary metrics
        experiment_config = flit_experiment_configs.get_experiment_config(experiment_name)
        config_secondary_metrics = experiment_config.get('metrics', {}).get('secondary', [])
        
        # Map config-defined metrics to available data columns
        available_secondary_metrics = []
        for metric_config in config_secondary_metrics:
            metric_name = metric_config.get('name')
            if metric_name == 'active_user_rate' and 'active_user_rate' in df.columns:
                available_secondary_metrics.append(metric_name)
            # Skip revenue metrics since they're not available in current schema
            elif metric_name in ['average_order_value', 'revenue_per_eligible_user']:
                logger.warning(f"Secondary metric '{metric_name}' configured but not available in data schema")
        
        # Store complete dataframe for secondary metrics analysis
        self._experiment_df = df
        self._experiment_config = experiment_config
        self._secondary_metrics = available_secondary_metrics
        self._secondary_metrics_config = {m['name']: m for m in config_secondary_metrics}
        
        # Split into control and treatment groups for primary metric
        control_data = df[df['treatment_group'] == 'control'][metric_column]
        treatment_data = df[df['treatment_group'] == 'treatment'][metric_column]
        
        if len(control_data) == 0 or len(treatment_data) == 0:
            raise ValueError("Missing control or treatment group data")
        
        # Create experiment data object for primary metric - ensure numeric types
        experiment_data = create_experiment_data(
            control_values=control_data.astype(float),
            treatment_values=treatment_data.astype(float),
            metadata={
                'experiment_name': experiment_name,
                'metric': metric_column,
                'data_source': f"{self.project_id}.flit_marts.mart_free_shipping_threshold_analysis",
                'query_timestamp': datetime.now().isoformat()
            }
        )
        
        logger.info(f"Loaded data: {len(control_data)} control, {len(treatment_data)} treatment users")
        logger.info(f"Secondary metrics available: {self._secondary_metrics}")
        return experiment_data
    
    def _analyze_secondary_metrics(self) -> Dict[str, Any]:
        """
        Analyze secondary metrics as guardrails for business risk assessment
        
        This is lightweight analysis focused on threshold checking, not full statistical rigor.
        Used to identify if secondary metrics show concerning trends that might offset primary gains.
        """
        if not hasattr(self, '_experiment_df') or not hasattr(self, '_secondary_metrics'):
            logger.warning("No secondary metrics data available")
            return {'status': 'no_data', 'message': 'Secondary metrics data not loaded'}
        
        logger.info("Running secondary metrics guardrail analysis")
        
        # Prepare data for each secondary metric
        metrics_data = {}
        df = self._experiment_df
        
        for metric in self._secondary_metrics:
            # Split data by treatment group
            control_data = df[df['treatment_group'] == 'control'][metric]
            treatment_data = df[df['treatment_group'] == 'treatment'][metric]
            
            # Create ExperimentData for this metric
            metrics_data[metric] = create_experiment_data(
                control_values=control_data.astype(float),
                treatment_values=treatment_data.astype(float),
                metadata={'metric': metric, 'type': 'secondary'}
            )
        
        # Get guardrail thresholds from config
        config_thresholds = {}
        for metric in self._secondary_metrics:
            metric_config = self._secondary_metrics_config.get(metric, {})
            if 'guardrail_threshold' in metric_config:
                config_thresholds[metric] = metric_config['guardrail_threshold']
        
        logger.info(f"Using config-based thresholds: {config_thresholds}")
        
        # Use the lightweight guardrail checking (not full statistical analysis)
        guardrail_results = self.engine.check_secondary_metrics(metrics_data, config_thresholds)
        
        # Add business context to the results
        business_context = self._add_secondary_metrics_business_context(guardrail_results)
        
        return {
            'guardrail_results': guardrail_results,
            'business_context': business_context,
            'analysis_type': 'guardrail_checking',
            'recommendation': self._get_secondary_metrics_recommendation(guardrail_results)
        }
    
    def _add_secondary_metrics_business_context(self, guardrail_results: Dict[str, Any]) -> Dict[str, Any]:
        """Add business context to guardrail results"""
        
        overall_status = guardrail_results.get('_overall', {}).get('status', 'UNKNOWN')
        
        context = {
            'business_impact_assessment': self._assess_business_impact(guardrail_results),
            'risk_factors': self._identify_risk_factors(guardrail_results),
            'mitigation_strategies': self._suggest_mitigation_strategies(guardrail_results, overall_status)
        }
        
        return context
    
    def _assess_business_impact(self, results: Dict[str, Any]) -> str:
        """Assess the business impact of secondary metric changes"""
        
        alerts = results.get('_overall', {}).get('alerts_count', 0)
        warnings = results.get('_overall', {}).get('warnings_count', 0)
        
        if alerts > 0:
            return "HIGH RISK - Secondary metrics show significant declines that could offset primary gains"
        elif warnings > 1:
            return "MEDIUM RISK - Multiple secondary metrics show concerning trends"
        elif warnings == 1:
            return "LOW RISK - One secondary metric shows minor concerns"
        else:
            return "MINIMAL RISK - Secondary metrics stable or improving"
    
    def _identify_risk_factors(self, results: Dict[str, Any]) -> List[str]:
        """Identify specific risk factors from secondary metrics"""
        
        risk_factors = []
        
        for metric, result in results.items():
            if metric == '_overall':
                continue
                
            if result.get('status') == 'ALERT':
                risk_factors.append(f"CRITICAL: {result.get('interpretation', 'Unknown issue')}")
            elif result.get('status') == 'WARNING':
                risk_factors.append(f"CONCERN: {result.get('interpretation', 'Unknown issue')}")
        
        return risk_factors
    
    def _suggest_mitigation_strategies(self, results: Dict[str, Any], overall_status: str) -> List[str]:
        """Suggest mitigation strategies based on secondary metric issues"""
        
        strategies = []
        
        if overall_status == 'ALERT':
            strategies.extend([
                "Do not launch until secondary metric issues are resolved",
                "Investigate root causes of metric declines", 
                "Consider alternative treatment approaches",
                "Implement additional monitoring before any rollout"
            ])
        elif overall_status == 'WARNING':
            strategies.extend([
                "Consider phased rollout with enhanced monitoring",
                "Implement additional tracking for concerning metrics",
                "Prepare rollback plan if trends worsen",
                "Monitor post-launch for 2x normal duration"
            ])
        else:
            strategies.append("Proceed with standard monitoring protocols")
        
        return strategies
    
    def _get_secondary_metrics_recommendation(self, results: Dict[str, Any]) -> str:
        """Get final recommendation considering secondary metrics"""
        
        overall = results.get('_overall', {})
        status = overall.get('status', 'UNKNOWN')
        recommendation = overall.get('recommendation', 'Unable to determine recommendation')
        
        return f"SECONDARY METRICS: {status} - {recommendation}"
    
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
                           business_insights: Dict[str, Any], 
                           secondary_results: Dict[str, Any] = None,
                           experiment_config: Dict[str, Any] = None) -> BusinessRecommendation:
        """Generate final business recommendation"""
        
        stats = statistical_results
        insights = business_insights
        
        effect_size = stats['effect_sizes']['relative_lift']
        p_value = stats['significance_tests']['welch_ttest'].p_value
        power = stats['power_analysis']['achieved_power']
        
        # Get thresholds from experiment config with proper fallback logging
        if experiment_config:
            primary_config = experiment_config.get('metrics', {}).get('primary', {})
            significance_threshold = primary_config.get('statistical_significance_level')
            business_threshold = primary_config.get('business_significance_threshold')
            
            # Handle missing config values with warnings
            if significance_threshold is None:
                logger.warning("⚠️  statistical_significance_level not found in experiment config, using hardcoded fallback: 0.05")
                significance_threshold = 0.05
            if business_threshold is None:
                logger.warning("⚠️  business_significance_threshold not found in experiment config, using hardcoded fallback: 0.10")
                business_threshold = 0.10
                
            logger.info(f"Using config-based thresholds - statistical: {significance_threshold}, business: {business_threshold}")
        else:
            # Fallback to defaults with clear warning
            logger.warning("⚠️  EXPERIMENT CONFIG NOT AVAILABLE - falling back to hardcoded thresholds!")
            logger.warning("This means analysis may not match intended experiment design parameters")
            significance_threshold = 0.05
            business_threshold = 0.10
            logger.info(f"Using hardcoded fallback thresholds - statistical: {significance_threshold}, business: {business_threshold}")
        
        # Decision logic (now using config-driven thresholds)
        statistically_significant = p_value < significance_threshold
        practically_significant = abs(effect_size) >= business_threshold
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
        imbalance = stats['metadata']['imbalance_factor']
        
        if p_value < 0.01 and power > 0.80 and imbalance < 1.25:
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
        imbalance = stats['metadata']['imbalance_factor']
        
        if power < 0.70 and imbalance > 1.25:
            return "HIGH - Low statistical power and group imbalance"
        elif power < 0.70:
            return "MEDIUM - Low statistical power may miss true effects"
        elif imbalance > 1.25:
            return "MEDIUM - Group imbalance may affect generalizability"
        else:
            return "LOW - No major statistical concerns identified"
    
    def _list_confidence_factors(self, stats: Dict[str, Any]) -> List[str]:
        """List factors that increase/decrease confidence in results"""
        
        factors = []
        
        # Positive factors
        if stats['power_analysis']['achieved_power'] > 0.80:
            factors.append("High statistical power supports reliable detection")
        
        if stats['metadata']['imbalance_factor'] < 1.11:
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


def run_quick_analysis(experiment_name: str = "free_shipping_threshold_test_v1_1_1",
                       write_to_warehouse: bool = False,
                       use_legacy_schema: bool = False) -> Dict[str, Any]:
    """
    Quick analysis function for immediate results
    
    Use this when you just want the key insights without all the detailed
    statistical machinery. Good for rapid iteration and initial assessments.
    """
    print(f"🚀 Running quick analysis for: {experiment_name}")
    
    reporter = ExperimentReporter()
    
    try:
        # Run complete analysis
        results = reporter.analyze_experiment(experiment_name, 
                                            write_to_warehouse=write_to_warehouse,
                                            use_legacy_schema=use_legacy_schema)
        
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