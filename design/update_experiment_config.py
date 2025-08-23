#!/usr/bin/env python3
"""
Experiment Configuration Updater

This script updates the experiment configuration with power analysis results,
creating a complete specification that data generation can consume.

Key features:
- Updates null fields with calculated values
- Preserves all original design decisions
- Creates a complete audit trail
- Versions the configuration appropriately

Usage:
    python update_experiment_config.py free_shipping_threshold_test --start-date 2024-02-01
"""

import argparse
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from design.power_analysis import ExperimentPowerAnalysis, PowerAnalysisResult
from flit_experiment_configs import get_experiment_config
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ExperimentConfigUpdater:
    """Updates experiment configurations with power analysis results"""
    
    def __init__(self, config_file_path: str = None):
        """
        Initialize the config updater
        
        Args:
            config_file_path: Path to experiments.yaml file
        """
        if config_file_path:
            self.config_path = Path(config_file_path)
        else:
            # Default to the package config file
            self.config_path = Path(__file__).parent.parent / "flit_experiment_configs" / "configs" / "experiments.yaml"
        
        logger.info(f"Using config file: {self.config_path}")
    
    def update_experiment_with_power_analysis(
        self, 
        experiment_name: str, 
        power_result: PowerAnalysisResult,
        selected_start_date: str
    ) -> None:
        """
        Update experiment configuration with power analysis results
        
        Args:
            experiment_name: Name of experiment to update
            power_result: Results from power analysis
            selected_start_date: Chosen start date (YYYY-MM-DD format)
        """
        # Load current config
        with open(self.config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if experiment_name not in config_data['experiments']:
            raise ValueError(f"Experiment '{experiment_name}' not found in config")
        
        experiment_config = config_data['experiments'][experiment_name]
        
        # Calculate end date
        start_date = datetime.strptime(selected_start_date, '%Y-%m-%d')
        end_date = start_date + timedelta(days=power_result.final_planned_duration)
        
        # Update temporal schedule
        experiment_config['design']['temporal_schedule'].update({
            'start_date': selected_start_date,
            'planned_end_date': end_date.strftime('%Y-%m-%d'),
            'planned_duration_days': power_result.final_planned_duration,
        })
        
        # Update power analysis results
        power_analysis_config = experiment_config['power_analysis']
        
        # Update sample size requirements
        power_analysis_config['sample_size'].update({
            'required_per_variant': power_result.required_sample_per_variant,
            'total_required': power_result.total_required_sample,
            'final_target_per_variant': int(power_result.required_sample_per_variant * 1.1)  # with buffer
        })
        
        # Update traffic analysis
        power_analysis_config['traffic_analysis'].update({
            'daily_total_users': power_result.daily_eligible_users,  # Simplified assumption
            'daily_eligible_users': power_result.daily_eligible_users,
            'eligible_user_percentage': 1.0,  # Since we filtered already
            'daily_users_per_variant': power_result.daily_users_per_variant,
            'traffic_variability': power_result.traffic_variability
        })
        
        # Update duration calculation
        power_analysis_config['duration_calculation'].update({
            'required_duration_days': power_result.required_duration_days,
            'final_planned_duration': power_result.final_planned_duration,
            'feasibility_status': power_result.feasibility_status.lower()
        })
        
        # Update experiment metadata
        experiment_config['metadata'].update({
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'power_analysis_completed': datetime.now().strftime('%Y-%m-%d'),
            'feasibility_status': power_result.feasibility_status,
            'config_version': "1.0.1"  # Bump version after power analysis
        })
        
        # Add power analysis summary to metadata
        experiment_config['metadata']['power_analysis_summary'] = {
            'statistical_power': power_result.