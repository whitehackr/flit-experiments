"""
Configuration Client - Core functionality for accessing experiment configurations

This module provides the primary interface for reading and validating experiment
configurations. It handles the complexity of finding config files within the
installed package and provides a clean API for consumers.

Design Considerations:
- Error handling for missing experiments (fail fast, clear messages)
- Package resource management (works in installed packages, not just dev)
- Configuration validation (catch errors early in the pipeline)
- Performance optimization (cache configs to avoid repeated file I/O)
"""

import yaml
import pkg_resources
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

# Get the package logger
logger = logging.getLogger(__name__)


class ExperimentConfigError(Exception):
    """
    Custom exception for experiment configuration errors
    
    Goal here is to make error handling more precise and helps with debugging. 
    Instead of generic ValueError, we can catch specific configuration issues.
    """
    pass


class ExperimentConfigClient:
    """
    Client for accessing experiment configurations
    """
    
    def __init__(self, config_filename: str = "experiments.yaml"):
        """
        Initialize the configuration client
        Args:
            config_filename: Name of the YAML file containing experiment configs
        """
        self.config_filename = config_filename
        self._config_cache: Optional[Dict[str, Any]] = None
        self._config_path: Optional[str] = None
        
        logger.info(f"Initialized ExperimentConfigClient with config: {config_filename}")
    
    def _get_config_path(self) -> str:
        """
        Get the full path to the configuration file within the installed package
        Allows us to find our config file in different situations -- whether we're:
        1. Running in development (pip install -e .)
        2. Running from an installed package (pip install flit-experiment-configs)
        3. Running tests
        
        pkg_resources handles all these cases.
        """
        try:
            # pkg_resources.resource_filename finds files within installed packages
            # Even if the package is installed in site-packages
            config_path = pkg_resources.resource_filename(
                'flit_experiment_configs', 
                f'configs/{self.config_filename}'
            )
            logger.debug(f"Found config file at: {config_path}")
            return config_path
            
        except Exception as e:
            # Fail fast with a clear message if we can't find the config file
            raise ExperimentConfigError(
                f"Could not locate experiment config file '{self.config_filename}'. "
                f"Make sure the package is properly installed. Error: {e}"
            )
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load and parse the experiment configuration file
        
        Caching strategy: Load once, reuse many times
        Important because config loading involves file I/O and YAML parsing
        """
        if self._config_cache is not None:
            logger.debug("Using cached configuration")
            return self._config_cache
        
        config_path = self._get_config_path()
        self._config_path = config_path
        
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)
                
            # Basic validation - make sure we have the expected structure
            if not isinstance(config_data, dict):
                raise ExperimentConfigError("Config file must contain a YAML dictionary")
            
            if 'experiments' not in config_data:
                raise ExperimentConfigError("Config file must contain an 'experiments' section")
            
            # Cache the loaded config
            self._config_cache = config_data
            logger.info(f"Successfully loaded configuration from {config_path}")
            
            return config_data
            
        except yaml.YAMLError as e:
            raise ExperimentConfigError(f"Invalid YAML in config file: {e}")
        except FileNotFoundError:
            raise ExperimentConfigError(f"Config file not found: {config_path}")
        except Exception as e:
            raise ExperimentConfigError(f"Unexpected error loading config: {e}")
    
    def get_experiment_config(self, experiment_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific experiment
        
        Args:
            experiment_name: Name of the experiment (e.g., "free_shipping_threshold_test")
            
        Returns:
            Dictionary containing the complete experiment configuration
            
        Raises:
            ExperimentConfigError: If experiment not found or config invalid
        """
        config_data = self._load_config()
        experiments = config_data['experiments']
        
        if experiment_name not in experiments:
            available_experiments = list(experiments.keys())
            raise ExperimentConfigError(
                f"Experiment '{experiment_name}' not found. "
                f"Available experiments: {available_experiments}"
            )
        
        experiment_config = experiments[experiment_name]
        
        # Basic validation - ensure required fields are present 
        # to catch configuration errors early, before they cause problems
        # in data generation or analysis
        required_fields = [
            'business_justification', 'hypothesis', 'design', 
            'population', 'variants', 'metrics', 'power_analysis'
        ]
        
        missing_fields = [field for field in required_fields 
                         if field not in experiment_config]
        
        if missing_fields:
            raise ExperimentConfigError(
                f"Experiment '{experiment_name}' is missing required fields: {missing_fields}"
            )
        
        logger.info(f"Successfully retrieved config for experiment: {experiment_name}")
        return experiment_config
    
    def list_available_experiments(self) -> List[str]:
        """
        Get a list of all available experiment names
        
        Useful for:
        - CLI tools that show available experiments
        - Validation scripts that process all experiments
        - Docs generation
        """
        config_data = self._load_config()
        experiments = list(config_data['experiments'].keys())
        logger.info(f"Found {len(experiments)} available experiments: {experiments}")
        return experiments
    
    def validate_experiment_config(self, experiment_name: str) -> bool:
        """
        Validate an experiment configuration without returning it
        
        Useful for:
        - CI/CD pipelines that validate configs before deployment
        - Configuration testing
        - Pre-flight checks before expensive operations
        
        Returns:
            True if configuration is valid
            
        Raises:
            ExperimentConfigError: If configuration is invalid
        """
        try:
            # Getting the config runs all the validation logic
            self.get_experiment_config(experiment_name)
            logger.info(f"Configuration validation passed for: {experiment_name}")
            return True
        except ExperimentConfigError:
            # Re-raise with additional context
            logger.error(f"Configuration validation failed for: {experiment_name}")
            raise
    
    def get_package_version(self) -> str:
        """
        Get the version of the currently installed configuration package
        
        For reproducibility, log which config version
        was used to generate data or run analysis
        """
        try:
            version = pkg_resources.get_distribution('flit-experiment-configs').version
            logger.debug(f"Package version: {version}")
            return version
        except Exception as e:
            logger.warning(f"Could not determine package version: {e}")
            return "unknown"


# Create a global client instance for convenience
# This allows simple function-based API while still getting benefits of the class
_default_client = ExperimentConfigClient()

# Public API functions - these are what users actually call
def get_experiment_config(experiment_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific experiment
    
    This is the main function that data generation and analysis scripts will use.
    Simple API abstracts away the complexity of package resource management.
    """
    return _default_client.get_experiment_config(experiment_name)


def list_available_experiments() -> List[str]:
    """Get a list of all available experiment names"""
    return _default_client.list_available_experiments()


def validate_experiment_config(experiment_name: str) -> bool:
    """Validate an experiment configuration"""
    return _default_client.validate_experiment_config(experiment_name)


def get_package_version() -> str:
    """Get the version of the configuration package"""
    return _default_client.get_package_version()