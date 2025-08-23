# Flit Experimentation Methodology

> **Experimental Design Standards**  
> Rigorous, reproducible, business-oriented A/B testing methodology

## **Experimentation Philosophy**

### **Hypothesis-Driven Approach**
Every experiment at Flit begins with a **clear business hypothesis** backed by data and strategic reasoning. We don't run tests to "see what happens" - we run tests to validate or refute specific predictions about customer behavior and business outcomes.

**Core Principles:**
- **Business First**: Every test must solve a real business problem
- **Statistical Rigor**: Proper power analysis drives all design decisions  
- **Risk Management**: Guardrail metrics protect business health
- **Learning Orientation**: Failed tests provide valuable insights

### **Scientific Standards**
We follow **publication-quality statistical practices** to ensure reliable, actionable results:

- **Pre-registration**: Complete experimental design before data collection
- **Power Analysis**: Calculate required sample sizes before starting
- **Multiple Testing Correction**: Adjust for multiple comparisons
- **Effect Size Focus**: Emphasize practical significance, not just statistical significance

---

## **Experimental Design Framework**

### **1. Hypothesis Formation**

#### **Primary Hypothesis**
The main business question driving the experiment. Must be:
- **Specific**: Clear prediction with quantified effect size
- **Measurable**: Tied to a specific metric we can calculate
- **Actionable**: Results will drive a clear business decision
- **Time-bound**: Expected timeline for effects to emerge

**Template:**
> "Changing [intervention] will [direction] [metric] by [magnitude] because [mechanism]"

**Example:**
> "Reducing free shipping threshold from $50 to $35 will increase conversion rate by 8% because lower purchase barriers reduce cart abandonment"

#### **Secondary Hypotheses**  
Additional questions we can answer with the same data:
- **Trade-off Analysis**: Understanding negative side effects
- **Mechanism Validation**: Testing our theory of why the change works
- **Segmentation Insights**: How effects vary across customer groups

### **2. Population Definition**

#### **Target Population**
Clearly define who the experiment is designed to help:
- **Business Relevance**: Focus on users who matter for the business question
- **Generalizability**: Ensure results will apply to broader population
- **Statistical Power**: Large enough for reliable effect detection

#### **Eligibility Criteria**
Systematic inclusion/exclusion rules:

**Inclusion Criteria** (must meet ALL):
- Relevant customer segments for the business question
- Geographic markets with stable operational conditions
- Minimum engagement level to show meaningful behavior
- Device/platform compatibility with the intervention

**Exclusion Criteria** (any ONE excludes):
- High-value customers (minimize risk to revenue -- unless the test is specifically about high value customers)
- Internal accounts (eliminate bias)
- Users in other experiments (prevent interaction effects)
- Edge cases that could confound results

#### **Stratified Randomization**
Balance treatment groups across key dimensions:
- **Customer Segments**: New vs. returning vs. lapsed
- **Behavioral Patterns**: High vs. low engagement
- **Demographic Factors**: Geographic regions, device types
- **Historical Performance**: Previous purchase behavior

### **3. Treatment Design**

#### **Control Group**
Represents the current state of the business:
- **Exact Current Experience**: No changes to existing flow
- **Measurement Infrastructure**: Same tracking as treatment
- **Consistent Implementation**: Identical technical setup

#### **Treatment Group(s)**
Implements the hypothesized improvement:
- **Minimal Viable Change**: Test smallest possible intervention
- **Clear Implementation**: Unambiguous specification of the change
- **Technical Feasibility**: Can be implemented reliably
- **Reversibility**: Can be quickly undone if problems emerge

### **4. Metrics Framework**

#### **Primary Metric**
The single most important business outcome:
- **Business Critical**: Directly tied to company objectives
- **Sensitive to Change**: Will respond to the intervention
- **Reliable Measurement**: Can be calculated consistently
- **Interpretable**: Stakeholders understand what it means

#### **Secondary Metrics**
Additional insights and trade-off analysis:
- **User Experience**: Satisfaction, engagement, retention
- **Business Health**: Revenue, profitability, operational efficiency  
- **Technical Performance**: Page load times, error rates
- **Long-term Impact**: Lifetime value, repeat behavior

#### **Guardrail Metrics**
Safety measures with automatic stop conditions:
- **Business Risk**: Revenue, refunds, customer complaints
- **Technical Risk**: System performance, error rates
- **User Experience Risk**: Satisfaction scores, support volume
- **Brand Risk**: Quality metrics, trust indicators

---

## **Statistical Methodology**

### **Power Analysis**

#### **Effect Size Determination**
How we decide what effect size to target:

**Business Significance**: Minimum improvement worth implementing
- Cost-benefit analysis of the intervention
- Strategic importance of the metric
- Competitive landscape considerations

**Statistical Detectability**: Can we reliably measure this effect?
- Historical variability of the metric
- Available sample size and time constraints  
- Multiple testing adjustments

**Practical Constraints**: Real-world limitations
- Engineering implementation complexity
- Risk tolerance for false positives/negatives
- Business calendar and seasonal effects

#### **Sample Size Calculation**
Rigorous statistical planning before data collection:

```
Required Sample Size = f(
    effect_size,           # How big a change we want to detect
    statistical_power,     # Probability of detecting true effects (80%)
    significance_level,    # False positive rate (5%)
    baseline_variance,     # Natural variability in the metric
    allocation_ratio       # Split between control/treatment (usually 50/50)
)
```

#### **Duration Planning**
How long to run the experiment:

**Statistical Requirements**: Time to collect required sample size
**Business Cycles**: Capture representative behavior patterns  
**Seasonal Considerations**: Avoid confounding from external events
**Effect Emergence**: Allow time for behavioral adaptation

### **Statistical Testing**

#### **Primary Analysis**
Pre-specified analysis plan executed exactly as designed:

**Two-Sample Tests**: Compare treatment vs. control groups
- **Proportions**: Z-test for conversion rates, click-through rates
- **Continuous Metrics**: T-test for revenue, order value, time metrics
- **Count Data**: Poisson test for items per order, page views

**Confidence Intervals**: Quantify uncertainty in effect estimates
- **Wilson Score**: More accurate for proportions with small samples
- **Bootstrap**: Non-parametric method for complex metrics
- **Bayesian**: Incorporate prior knowledge and business context

#### **Sequential Testing & Early Stopping**

**Sequential testing allows early termination while preserving statistical validity through careful alpha spending.**

##### **The Peeking Problem**
Naive interim analysis without proper adjustment inflates Type I error:
```
True Alpha = 1 - (1 - α)^k where k = number of looks
Example: 5 looks at α=0.05 → True α ≈ 0.23 (not 0.05!)
```

##### **Alpha Spending Functions**
We control overall Type I error by "spending" alpha across interim analyses:

**O'Brien-Fleming (Conservative - Our Standard at Flit)**:
- Very strict early boundaries, easier final boundary
- Protects against false early stopping
- Formula: `z_k = z_α * √(K/k)` where k=current look, K=total looks

**Pocock (Liberal)**:
- Equal boundaries at each look
- Higher chance of early stopping
- Formula: `z_k = z_α * √(K/(2K-1))`

**Lan-DeMets (Flexible)**:
- Allows unequal time intervals
- Can handle irregular interim analyses
- Uses spending function: α(t) where t = information fraction

##### **Implementation Protocol**

**Pre-Registration Requirements (Critical)**:
1. **Fixed Analysis Schedule**: Specify exact interim analysis dates
2. **Spending Function Choice**: Select O'Brien-Fleming (preferred/default), Pocock, or custom
3. **Stopping Boundaries**: Calculate adjusted p-value thresholds
4. **Maximum Duration**: Set absolute time limit regardless of results

**Example Sequential Design**:
```yaml
sequential_testing:
  method: "obrien_fleming"
  planned_looks: 4
  look_schedule: [7, 14, 21, 28]  # Days after start
  
  # Calculated boundaries for O'Brien-Fleming with 4 looks
  stopping_boundaries:
    superiority:      # Stop if effect is significant
      look_1: 0.00001  # p < 0.00001 (z > 4.33)
      look_2: 0.00138  # p < 0.00138 (z > 3.06) 
      look_3: 0.00851  # p < 0.00851 (z > 2.65)
      look_4: 0.02169  # p < 0.02169 (z > 2.31)
    
    futility:         # Stop if effect is clearly null
      look_1: 0.50     # Continue if p < 0.50
      look_2: 0.25     # Continue if p < 0.25
      look_3: 0.15     # Continue if p < 0.15
      look_4: 0.05     # Standard final boundary
```

**Boundary Calculation**:
```python
# O'Brien-Fleming boundaries calculation
import scipy.stats as stats

def calculate_obrien_fleming_boundaries(K, alpha=0.05):
    """Calculate O'Brien-Fleming stopping boundaries"""
    z_alpha = stats.norm.ppf(1 - alpha/2)  # Two-sided critical value
    
    boundaries = {}
    for k in range(1, K+1):
        z_k = z_alpha * math.sqrt(K / k)
        p_k = 2 * (1 - stats.norm.cdf(z_k))  # Two-sided p-value
        boundaries[f'look_{k}'] = p_k
    
    return boundaries
```

##### **Execution Rules**

**Superiority Stopping** (Treatment is significantly better):
- Calculate test statistic at interim analysis
- Compare to adjusted boundary for current look
- If boundary exceeded: STOP and implement treatment
- Document: "Early stopping for efficacy at look k"

**Futility Stopping** (Treatment effect unlikely):
- Calculate conditional power: P(final significance | current data)
- If conditional power < threshold (e.g., 20%): STOP
- Document: "Early stopping for futility - unlikely to reach significance"

**Safety Stopping** (Guardrail violations):
- Monitor guardrail metrics at every look
- If any guardrail exceeded: IMMEDIATE STOP
- Override all other considerations
- Document: "Early stopping for safety concerns"

##### **Post-Analysis Considerations**

**Effect Size Estimation**: 
- Early stopped experiments have biased effect estimates
- Use bias-adjusted estimators (median unbiased estimation)
- Report confidence intervals accounting for sequential nature

**Business Decision Making**:
- Early efficacy stops: High confidence in implementation
- Futility stops: Consider alternative interventions  
- Safety stops: Investigate root causes before future tests

##### **Common Pitfalls & Avoidance**

**❌ Invalid Practices**:
- Peeking without pre-planned boundaries
- Changing stopping rules mid-experiment  
- Cherry-picking favorable interim results
- Ignoring safety signals for promising efficacy

**✅ Valid Practices**:  
- Pre-registered sequential design
- Blinded interim analyses when possible
- Independent data monitoring committee
- Complete documentation of all stopping decisions

**Documentation Requirements**:
Every sequential test must document:
1. Pre-registered analysis plan with exact boundaries
2. Interim analysis results and stopping decisions
3. Bias-corrected final effect estimates
4. Sensitivity analysis for robustness

#### **Subgroup Analysis**
Understand how effects vary across customer segments:

**Pre-specified Subgroups**: Defined before data collection
- Customer segments (new/returning/lapsed)
- Geographic regions (US/CA/UK)  
- Device types (desktop/mobile/tablet)
- Purchase history (high/medium/low value)

**Interaction Testing**: Statistical tests for differential effects
**Clinical Significance**: Business importance of subgroup differences

---

## **Business Decision Framework**

### **Launch Criteria**
Clear, pre-specified conditions for implementing the treatment:

#### **Statistical Significance**
- Primary metric p-value < 0.05 (95% confidence)
- Confidence interval excludes zero effect
- Multiple testing correction applied

#### **Practical Significance**  
- Effect size meets minimum business threshold
- Confidence interval excludes trivially small effects
- Cost-benefit analysis shows positive ROI

#### **Safety Validation**
- All guardrail metrics within acceptable bounds
- No concerning trends in secondary metrics
- Subgroup analysis shows broadly positive effects

#### **Implementation Readiness**
- Engineering team can implement at scale
- Customer support prepared for potential issues
- Monitoring infrastructure in place for ongoing measurement

### **Stop Criteria**
Conditions that trigger immediate experiment termination:

#### **Safety Violations**
- Any guardrail metric exceeds predefined threshold
- Significant degradation in user experience
- Technical issues affecting experiment validity

#### **Futility Analysis**
- No reasonable chance of achieving statistical significance
- Effect size trending toward business irrelevance
- Cost of continuing experiment exceeds potential value

#### **External Factors**
- Major changes in business priorities or strategy
- Competitive actions that change the landscape
- Seasonal events that would confound results

### **Decision Documentation**
Every experiment conclusion includes:

**Statistical Summary**: Effect sizes, confidence intervals, p-values
**Business Impact**: Revenue implications, user experience effects
**Implementation Plan**: Next steps, rollout timeline, success monitoring
**Lessons Learned**: Insights for future experiments, methodology improvements

---

## **Operational Excellence**

### **Experiment Lifecycle Management**

#### **Planning Phase**
- Business stakeholder alignment on success criteria
- Technical feasibility assessment with engineering
- Calendar coordination to avoid conflicts
- Resource allocation and timeline planning

#### **Execution Phase**
- Daily monitoring of key metrics and guardrails
- Weekly stakeholder updates on experiment progress  
- Technical performance monitoring and issue resolution
- Data quality validation and anomaly detection

#### **Analysis Phase**
- Statistical analysis following pre-registered plan
- Business impact assessment and recommendation formation
- Stakeholder presentation and decision discussion
- Documentation and knowledge sharing

#### **Implementation Phase**
- Technical rollout planning and execution
- Success monitoring and performance tracking
- Iteration planning based on learnings
- Portfolio strategy updates

### **Quality Assurance**

#### **Design Review Process**
- Statistical methodology peer review
- Business logic validation with stakeholders
- Technical implementation feasibility check
- Risk assessment and mitigation planning

#### **Data Quality Monitoring**
- Real-time tracking of assignment balance
- Anomaly detection for unusual patterns
- Sample ratio mismatch testing
- Exposure validation and tracking

#### **Analysis Validation**
- Independent replication of key results
- Sensitivity analysis for robustness
- Cross-validation with external data sources
- Peer review of conclusions and recommendations

---

## 📚 **Continuous Learning**

### **Methodology Evolution**
Our experimentation practices continuously improve through:

**Literature Review**: Staying current with academic research
**Industry Benchmarking**: Learning from other companies' practices
**Internal Retrospectives**: Analyzing our own successes and failures
**Tool and Technique Adoption**: Implementing better statistical methods

### **Knowledge Sharing**
We document and share learnings across the organization:

**Experiment Registry**: Central repository of all tests and results
**Best Practices Documentation**: Evolving guidance based on experience
**Training Programs**: Educating stakeholders on experimental thinking
**Success Stories**: Highlighting impactful experiments and insights

### **Cultural Development**
Building an experimentation-first culture:

**Hypothesis Training**: Teaching stakeholders to think experimentally
**Data Literacy**: Improving statistical understanding across teams
**Decision Science**: Integrating experiments into business processes
**Innovation Encouragement**: Celebrating both successful and failed experiments

---

*This methodology represents our commitment to scientific rigor, business impact, and continuous learning in data-driven decision making.*
