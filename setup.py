# setup.py
"""
Python package configuration for flit-experiment-configs

This file tells Python how to build and install our experiment configuration package.

Key concepts covered:
- Package versioning (critical for reproducibility)
- Dependency management (libraries needed)
- File inclusion (YAML configs get bundled with the package)
- Distribution (how other repos can pip install this)
"""

from setuptools import setup, find_packages
import os

def read_readme():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    readme_path = os.path.join(current_dir, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Flit Experiment Configuration Package"

setup(
    # Package identity - this is what a user will 'pip install'
    # In particular, for ease of distribution, I will host this on Github, so:
    # pip install git+https://github.com/whitehackr/flit-experiments.git

    name="flit-experiment-configs",
    
    # Version management - CRITICAL for experiment reproducibility
    # We'll bump this every time we add/modify experiments
    # v1.0.0 = initial free shipping experiment
    # v1.1.0 = add checkout flow experiment  
    # v2.0.0 = major config structure change
    version="1.0.0",
    
    # Package metadata - shows up in pip show, PyPI, etc.
    author="Kevin Waithaka",
    author_email="kevwaithakam@gmail.com",
    description="Experiment configuration package for Flit's A/B testing platform",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    
    # Package discovery - automatically find all Python packages
    # This finds flit_experiment_configs/ and any subpackages
    packages=find_packages(),
    
    # File inclusion - CRITICAL: tells setuptools to include non-Python files
    # Without this, our YAML configs wouldn't be bundled in the package
    include_package_data=True,
    
    # Explicit file inclusion - belt-and-suspenders approach
    # Ensures our experiment YAML configs are definitely included
    package_data={
        'flit_experiment_configs': [
            'configs/*.yaml',  # Include all YAML files in configs/
            'configs/*.yml',   # Handle both .yaml and .yml extensions
        ]
    },
    
    # Python version requirements
    python_requires=">=3.9",
    
    # Dependencies 
    install_requires=[
        "pyyaml>=6.0",        # For parsing experiment YAML configs
        "pydantic>=1.10.0",   # For configuration validation (future enhancement perhaps)
    ],
    
    # Development dependencies - only needed when working on this package
    # Install with: pip install -e ".[dev]"
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",      # Code formatting
            "flake8>=4.0.0",      # Linting
            "mypy>=0.950",        # Type checking
        ]
    },
    
    # Package classification
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    
    # Entry points
    entry_points={
        # Future: could add CLI commands here
        # 'console_scripts': [
        #     'flit-experiment=flit_experiment_configs.cli:main',
        # ],
    },
    
    # Project URLs - where people can find more info
    project_urls={
        "Bug Reports": "https://github.com/whitehackr/flit-experiments/issues",
        "Source": "https://github.com/whitehackr/flit-experiments",
        "Documentation": "https://github.com/whitehackr/flit-experiments/blob/main/README.md",
    },
)