#!/usr/bin/env python3
"""
Complete Analysis Runner for Free Shipping Experiment

This script runs the full statistical analysis using our two-module framework:
1. Statistical engine handles all the math and tests
2. Business intelligence converts results into actionable insights

Usage:
    python run_complete_analysis.py

Outputs:
- Detailed statistical results (JSON)
- Executive summary for leadership
- Dashboard export for visualization tools
- Key charts and visualizations

Author: Kevin
Created: 2024-09-02
"""

import sys
import os
import logging
from datetime import datetime

# Add the analysis directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from business_intelligence import ExperimentReporter, run_quick_analysis

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run complete analysis pipeline"""
    
    print("🚀 Starting Free Shipping Threshold Experiment Analysis")
    print("=" * 65)
    
    try:
        # Initialize reporter
        print("📊 Initializing analysis framework...")
        reporter = ExperimentReporter()
        
        # Run complete analysis
        print("🔍 Running statistical analysis...")
        results = reporter.analyze_experiment(
            experiment_name="free_shipping_threshold_test_v1_1_1",
            metric_column="orders_during_experiment"
        )
        
        # Generate all outputs
        print("📈 Creating business reports...")
        
        # Executive summary
        exec_summary = reporter.create_executive_summary()
        
        # Detailed report
        detailed_report_path = reporter.create_detailed_report()
        
        # Dashboard export
        dashboard_path = reporter.create_dashboard_export()
        
        # Visualizations
        print("📊 Generating visualizations...")
        viz_files = reporter.create_visualizations()
        
        # Print executive summary
        print("\n" + "=" * 65)
        print("🎯 EXECUTIVE SUMMARY")
        print("=" * 65)
        print(f"Bottom Line: {exec_summary['bottom_line_recommendation']}")
        print(f"Key Finding: {exec_summary['key_finding']}")
        print(f"Confidence: {exec_summary['statistical_confidence']}")
        print(f"Sample Quality: {exec_summary['sample_quality']}")
        print(f"Business Impact: {exec_summary['business_impact']}")
        print(f"Risk Level: {exec_summary['risk_assessment']}")
        
        print(f"\n📋 IMMEDIATE NEXT STEPS:")
        for i, step in enumerate(exec_summary['executive_next_steps'], 1):
            print(f"  {i}. {step}")
        
        # File outputs summary
        print(f"\n📁 GENERATED FILES:")
        print(f"  • Detailed Report: {detailed_report_path}")
        print(f"  • Dashboard Data: {dashboard_path}")
        for viz_name, viz_path in viz_files.items():
            print(f"  • {viz_name.replace('_', ' ').title()}: {viz_path}")
        
        print("\n" + "=" * 65)
        print("✅ ANALYSIS COMPLETE!")
        print("All files ready for stakeholder review and dashboard integration.")
        print("=" * 65)
        
        return results
        
    except Exception as e:
        logger.error(f"Analysis pipeline failed: {e}")
        print(f"\n❌ ANALYSIS FAILED: {e}")
        print("Check logs for detailed error information.")
        raise


if __name__ == "__main__":
    # Run the complete analysis
    main()