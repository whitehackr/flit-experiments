# flit_experiment_configs/__init__.py
"""
Flit Experiment Configuration Package

This package provides versioned, validated experiment configurations for the Flit
Experimentation platform. It serves as the single source of truth for all experiment
specifications, ensuring reproducibility and consistency across the data pipeline.

Architecture Pattern: Configuration as a Service
- Experiment specs are defined once in this package
- Multiple services (data generation, analysis) consume these specs
- Versioning ensures exact reproducibility of experiments
- Validation prevents invalid configurations from propagating

Usage:
    from flit_experiment_configs import get_experiment_config
    
    config = get_experiment_config("free_shipping_threshold_test")
    print(f"Effect size: {config['power_analysis']['effect_size']['magnitude']}")

Design Principles:
1. Single Source of Truth - All experiment logic defined here
2. Version Control - Every config change gets a version bump
3. Validation - Configs are validated before use
4. Documentation - Self-documenting configuration structure
"""

# Package version - this should match setup.py and pyproject.toml
# In production, this would be auto-synced during CI/CD
__version__ = "1.0.0"

# Package metadata
__author__ = "Flit Experimentation Team"
__email__ = "kevwaithakam@gmail.com"
__description__ = "Experiment configuration package for Flit's A/B testing platform"

# Public API - what users can import from this package
from .client import (
    get_experiment_config,
    list_available_experiments,
    get_package_version,
    validate_experiment_config,
)

# Make these functions available at package level
# Users can do: from flit_experiment_configs import get_experiment_config
__all__ = [
    "get_experiment_config",
    "list_available_experiments", 
    "get_package_version",
    "validate_experiment_config",
    "__version__",
]

# Package-level configuration
# These could be overridden by environment variables in production
DEFAULT_CONFIG_FILE = "experiments.yaml"

# This should ideally be a growing list. We ought to use descriptive experiment type names
SUPPORTED_EXPERIMENT_TYPES = [
    "conversion_rate_test",      # A/B tests for conversion optimization
    "continuous_metric_test",    # Tests for metrics like AOV, revenue
    "count_metric_test",         # Tests for metrics like items per order
]

# TODO: Validation schemas
# We'll use these to validate experiment configs before they're used
REQUIRED_CONFIG_FIELDS = [
    "business_justification",
    "hypothesis",
    "design",
    "population",
    "variants",
    "metrics",
    "power_analysis",
]

# Logging configuration for package
import logging

# Create a logger for this package
# Other modules can use this logger for consistent logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add a null handler to prevent logging errors if no handler is configured
logger.addHandler(logging.NullHandler())

# Export the logger for use in other modules
__all__.append("logger")