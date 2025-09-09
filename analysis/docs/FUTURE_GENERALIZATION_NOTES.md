# Secondary Metrics Framework Generalization - Sprint Planning Notes

## Context
**Date**: 2024-09-06
**Current State**: Working framework for free shipping threshold experiment with primary metric (`orders_during_experiment`) analysis. About to implement secondary metrics for current experiment only.

**Future Goal**: Generalize secondary metrics framework to handle any experiment type across different business domains.

## Current Implementation (After Secondary Metrics Sprint)
- **Statistical Engine**: Has `analyze_experiment()` for single metrics + `analyze_multiple_metrics()` for secondary metrics
- **Business Intelligence**: Loads specific metrics (`completion_rate`, `avg_items_per_order`, `is_active_user`) and provides hardcoded business interpretation
- **Experiment Config**: `experiments.yaml` already contains secondary metrics definitions but they're not being used programmatically

## Architecture Vision for Generalization Sprint

### 1. Configuration-Driven Analysis
**Current**: Secondary metrics are hardcoded in `business_intelligence.py`
**Target**: Read secondary metrics from `experiments.yaml` config

```python
# experiments.yaml structure already exists:
secondary:
  - name: "average_order_value"
    guardrail_threshold: -0.15
    expected_direction: "decrease"
  - name: "completion_rate" 
    target_direction: "stable"
```

**Implementation**: Create `ExperimentConfigLoader` that parses YAML and extracts metric definitions.

### 2. Generic Metric Analysis Pipeline
**Current**: Business Intelligence has specific knowledge of each metric
**Target**: Generic metric analyzer with pluggable interpretation

```python
class MetricInterpreter:
    def interpret(self, metric_name: str, results: Dict, config: Dict) -> BusinessInterpretation
    
# Different domains register their interpreters
interpreters = {
    'ecommerce': EcommerceMetricInterpreter(),
    'content': ContentMetricInterpreter(), 
    'pricing': PricingMetricInterpreter()
}
```

### 3. Data Schema Flexibility
**Current Issue**: BigQuery schema is fixed, not all experiments will have same columns
**Future Need**: Dynamic column mapping based on experiment type

```python
# Map experiment config metrics to actual data columns
metric_mappings = {
    'completion_rate': 'AVG(CASE WHEN is_completed = 1 THEN 1.0 ELSE 0.0 END)',
    'average_order_value': 'SUM(revenue) / COUNT(orders)',  # When revenue exists
    'customer_satisfaction': 'AVG(rating)'  # Different experiments, different schemas
}
```

## Key Design Principles for Generalization

1. **Backwards Compatibility**: Existing experiments continue working unchanged
2. **Domain Flexibility**: Support ecommerce, content, pricing, UX experiment domains
3. **Config-First**: Experiment YAML drives analysis behavior, not hardcoded logic
4. **Statistical Rigor**: All domains get same statistical quality (significance tests, power analysis, etc.)
5. **Business Context**: Each domain can define its own interpretation rules

## Implementation Sequence

### Phase 1: Config Reader
- Create `ExperimentConfig` class that parses YAML
- Extract primary/secondary metric definitions
- Map metric configs to data queries

### Phase 2: Generic Statistical Engine
- Extend `StatisticalAnalysisEngine` with `analyze_experiment_from_config()`
- Takes experiment config + data, returns analysis for all defined metrics
- Keep existing `analyze_experiment()` for backwards compatibility

### Phase 3: Pluggable Interpreters
- Create base `MetricInterpreter` interface
- Implement `EcommerceMetricInterpreter` (extracts current hardcoded logic)
- Register interpreters by experiment domain

### Phase 4: Dynamic Data Loading
- Make BigQuery queries configurable based on available schema
- Handle missing columns gracefully (skip metrics vs error)
- Support different data sources per experiment type

## Files to Modify in Generalization Sprint
- `statistical_engine.py`: Add config-driven analysis methods
- `business_intelligence.py`: Extract hardcoded interpretation to separate classes
- Create `experiment_config.py`: YAML parsing and validation
- Create `metric_interpreters/`: Domain-specific interpretation logic
- Create `data_adapters/`: Handle different data schemas per experiment type

## Success Criteria
- ✅ Current free shipping experiment works unchanged
- ✅ Can define new experiment type purely through YAML config
- ✅ Adding new business domain requires only new interpreter class
- ✅ Statistical rigor maintained across all experiment types
- ✅ No hardcoded metric logic in core framework

## Technical Debt to Address
- **Data Schema Coupling**: Currently assumes specific BigQuery table structure
- **Hardcoded Metrics**: Secondary metrics are hardcoded, not config-driven  
- **Domain Knowledge Mixing**: Statistical engine has some business logic
- **No Validation**: Experiment configs aren't validated against available data

## Context for Future Developer (You!)
The current implementation works great for the specific use case. The framework has proven its value with real business impact. Now it's time to scale it horizontally across experiment types while maintaining the statistical quality and business intelligence that made it successful.

Start with the config reader - parse the existing YAML structure and use it to drive the analysis. The statistical engine is already solid, just needs to accept config objects rather than hardcoded parameters.

## Related Files to Review
- `/flit_experiment_configs/configs/experiments.yaml` - Target config structure
- `/analysis/statistical_engine.py` - Core statistical methods to preserve
- `/analysis/business_intelligence.py` - Business logic to extract into interpreters
- Current experiment results - See what worked well to preserve in generalization

---
**Remember**: Don't optimize prematurely. The current focused implementation should run in production first, prove its business value, then we generalize based on real requirements from additional experiment types.