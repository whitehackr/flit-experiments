# A/B Testing Statistical Analysis Framework

**Version:** 1.0.0  
**Last Updated:** September 10, 2025  
**Authors:** Data Science Team  

Enterprise-grade statistical analysis framework for A/B testing experiments with secondary metrics guardrails and normalized BigQuery integration.

## Setup & Installation

### 1. Clone Repository
```bash
git clone https://github.com/whitehackr/flit-experiments.git
cd flit-experiments
```

### 2. Environment Setup
```bash
# Create conda environment
conda create -n flit python=3.11
conda activate flit

# Install dependencies
pip install -e . && pip install -r requirements.txt
```

### 3. Credentials
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account.json
```

## Quick Start (30 seconds to results)

Navigate to the analysis directory and run:

```bash
cd analysis
python -c "
from business_intelligence import run_quick_analysis
results = run_quick_analysis('free_shipping_threshold_test_v1_1_1')
print(f'Decision: {results[\"recommendation\"][\"decision\"]}')
print(f'Effect: {results[\"statistical_results\"][\"effect_sizes\"][\"relative_lift_percent\"]:.1f}%')
print(f'P-value: {results[\"statistical_results\"][\"significance_tests\"][\"welch_ttest\"].p_value:.2e}')
"
```

## Entry Points

### Option 1: Quick Analysis Function (Recommended)
```python
# From analysis/ directory
from business_intelligence import run_quick_analysis

# Basic analysis
results = run_quick_analysis('your_experiment_name')

# With BigQuery export (normalized schema)
results = run_quick_analysis(
    experiment_name='your_experiment',
    write_to_warehouse=True
)

# Legacy single-table schema
results = run_quick_analysis(
    experiment_name='your_experiment', 
    write_to_warehouse=True,
    use_legacy_schema=True
)
```

### Option 2: Complete Analysis Script
```bash
# From analysis/ directory - runs full pipeline with all outputs
python run_complete_analysis.py
```
This script:
1. Runs statistical analysis using `statistical_engine.py`
2. Generates business insights via `business_intelligence.py` 
3. Exports JSON reports, dashboard data, and visualizations
4. Creates executive summary

### Option 3: ExperimentReporter Class (Advanced)
```python
# For custom analysis workflows
from business_intelligence import ExperimentReporter

reporter = ExperimentReporter(project_id="your-project")
results = reporter.analyze_experiment(
    experiment_name='your_experiment',
    write_to_warehouse=True
)

# Generate additional outputs
summary = reporter.create_executive_summary()
viz_files = reporter.create_visualizations()
dashboard_file = reporter.create_dashboard_export()
```

## Framework Architecture

```
statistical_engine.py      # Statistical analysis (t-tests, effect sizes, power analysis)
       ↓
business_intelligence.py   # Business insights, recommendations, BigQuery integration
       ↓  
run_complete_analysis.py   # Entry point with full pipeline + file exports
```

## Configuration

**Architecture**: Experiment configurations are managed through a GitHub package workflow. The Experiment Design Team in collab with the appropriate business team defines metrics, thresholds, and parameters, which are versioned and published as the `flit_experiment_configs` package. The analysis framework automatically consumes the latest approved configs during installation, ensuring analysts always use correct experiment parameters without manual configuration management.

**Config Structure**:
```yaml
your_experiment_name:
  metrics:
    primary:
      name: orders_per_eligible_user
      statistical_significance_level: 0.05
      business_significance_threshold: 0.20
    secondary:
      - name: active_user_rate
        guardrail_threshold: -0.02
```

## Key Features

- **Statistical Rigor**: Welch's t-test, Mann-Whitney U, bootstrap confidence intervals, power analysis
- **Secondary Metrics**: Lightweight guardrail checking for business risk assessment  
- **Config-Driven**: Integrates with `flit_experiment_configs` for experiment definitions
- **Normalized BigQuery**: Separate tables for primary/secondary metrics (dashboard-ready)
- **Business Recommendations**: Data-driven launch decisions (LAUNCH/NO_LAUNCH/EXTEND_TEST)

## Database Schema

### Normalized Schema (Default)
```sql
-- One row per experiment analysis
int_experiment_results_primary
├── analysis_id, experiment_name, analysis_date
├── control_mean, treatment_mean, relative_lift_percent
├── p_value, statistical_power, imbalance_factor
└── final_decision, confidence_level, risk_level

-- One row per secondary metric per analysis
int_experiment_results_secondary  
├── analysis_id (links to primary)
├── secondary_metric_name, secondary_metric_status
└── secondary_metric_effect_percent, interpretation
```

## Working Directory

All analysis commands should be run from the `analysis/` directory:

```bash
cd flit-experiments/analysis/

# Then run any of the entry points above
python run_complete_analysis.py
# or
python -c "from business_intelligence import run_quick_analysis; ..."
```

## Output Structure

```
analysis/outputs/
├── reports/                    # JSON analysis results
├── dashboards/                # BI-ready flattened data  
└── visualizations/            # PNG charts and graphs
```

## Business Recommendations

The framework provides data-driven launch recommendations:

- **STRONG_LAUNCH**: High statistical confidence + large business impact
- **LAUNCH**: Statistically significant with meaningful business impact  
- **CONSIDER_LAUNCH**: Significant but small effect - evaluate cost/benefit
- **EXTEND_TEST**: Promising signal but needs more data
- **NO_LAUNCH**: No evidence of positive impact or significant decline

## Documentation

- **[Complete Usage Guide](../methodology/experimentation-standards.md)** - Detailed methodology and standards
- **[Example Analyses](experiments/)** - Real experiment analyses (see `EXPERIMENT_ANALYSIS_*.md` files)
- **[Architecture Notes](experiments/FUTURE_GENERALIZATION_NOTES.md)** - Framework expansion roadmap

## Support

- **Issues**: Report at the main repository issues page
- **Questions**: Contact the Data Science team
- **Contributing**: See contribution guidelines in main repository

---

**Framework Version:** 1.0.0 | **Documentation Version:** 1.0.0