#!/usr/bin/env python3
"""
Power Analysis Runner - Command Line Interface

This script provides an easy way to run power analysis for any experiment
defined in the configuration package. It's designed for both interactive
use and integration into CI/CD pipelines.

Usage:
    python run_power_analysis.py free_shipping_threshold_test
    python run_power_analysis.py --list-experiments
    python run_power_analysis.py --help

Provision of clear CLI interfaces will allow 
stakeholders to run analyses independently and integrates well
with automated workflows.
"""

import argparse
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from design.power_analysis import ExperimentPowerAnalysis
from flit_experiment_configs import list_available_experiments

def setup_argument_parser():
    """Set up command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Run statistical power analysis for Flit experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Historical simulation (for TheLook data)
    python run_power_analysis.py free_shipping_threshold_test --reference-date 2024-03-01
    
    # Live experiment planning
    python run_power_analysis.py free_shipping_threshold_test
    
    # Development mode with mock data
    python run_power_analysis.py free_shipping_threshold_test --use-mock-data --reference-date 2024-03-01
    
    # List all available experiments  
    python run_power_analysis.py --list-experiments
    
    # Save results to JSON file
    python run_power_analysis.py free_shipping_threshold_test --output results.json --reference-date 2024-03-01
    
    # Verbose output for debugging
    python run_power_analysis.py free_shipping_threshold_test --verbose --reference-date 2024-03-01
        """
    )
    
    # Main argument - experiment name
    parser.add_argument(
        'experiment_name',
        nargs='?',
        help='Name of the experiment to analyze'
    )
    
    # Optional arguments
    parser.add_argument(
        '--list-experiments',
        action='store_true',
        help='List all available experiments and exit'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Save detailed results to JSON file'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging output'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate experiment config without running full analysis'
    )

    parser.add_argument(
        '--reference-date',
        type=str,
        help='Reference date for historical simulation (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--use-mock-data',
        action='store_true',
        help='Use mock data instead of BigQuery (for development/testing)'
    )

    parser.add_argument(
        '--project-id',
        help='GCP project ID for BigQuery data source'
    )
    
    return parser

def format_result_summary(result):
    """Format power analysis results for human-readable output"""
    
    print(f"\n{'='*60}")
    print(f"🔬 POWER ANALYSIS SUMMARY")
    print(f"{'='*60}")
    
    print(f"\n📋 Experiment: {result.experiment_name}")
    print(f"📦 Config Version: {result.config_version}")
    print(f"🎯 Status: {result.feasibility_status}")
    
    print(f"\n📊 Statistical Parameters:")
    print(f"   Baseline Rate: {result.baseline_rate:.1%}")
    print(f"   Treatment Rate: {result.treatment_rate:.1%}")
    print(f"   Effect Size: {result.effect_size:.1%} relative improvement")
    print(f"   Statistical Power: {result.statistical_power:.0%}")
    print(f"   Significance Level: {result.significance_level:.0%}")
    
    print(f"\n👥 Sample Size Requirements:")
    print(f"   Per Variant: {result.required_sample_per_variant:,} users")
    print(f"   Total Required: {result.total_required_sample:,} users")
    
    print(f"\n📈 Traffic Analysis:")
    print(f"   Daily Eligible Users: {result.daily_eligible_users:,}")
    print(f"   Daily Users Per Variant: {result.daily_users_per_variant:,}")
    print(f"   Traffic Variability: {result.traffic_variability:.1%}")
    
    print(f"\n⏱️ Duration Requirements:")
    print(f"   Required Duration: {result.required_duration_days} days ({result.required_duration_weeks} weeks)")
    print(f"   Final Planned Duration: {result.final_planned_duration} days")
    
    # Status-specific output
    if result.feasibility_status == "FEASIBLE":
        print(f"\n✅ FEASIBLE - Ready to implement!")
        
        if result.suggested_start_dates:
            print(f"\n📅 Recommended Start Dates:")
            for date, reason in result.suggested_start_dates.items():
                end_date = pd.to_datetime(date) + pd.Timedelta(days=result.final_planned_duration)
                print(f"   {date} → {end_date.strftime('%Y-%m-%d')}: {reason}")
    
    elif result.feasibility_status == "MARGINAL":
        print(f"\n⚠️ MARGINAL - Feasible with limitations")
        
    else:
        print(f"\n❌ NOT FEASIBLE - Requires design changes")
    
    # Show reasons and warnings
    if result.feasibility_reasons:
        print(f"\n📝 Feasibility Notes:")
        for reason in result.feasibility_reasons:
            print(f"   • {reason}")
    
    if result.warnings:
        print(f"\n⚠️ Warnings:")
        for warning in result.warnings:
            print(f"   • {warning}")
    
    # Next steps
    print(f"\n🎯 Next Steps:")
    if result.feasibility_status == "FEASIBLE":
        print("   1. Select a start date from the recommendations above")
        print("   2. Update experiment config with calculated values")  
        print("   3. Proceed to data generation phase")
        print("   4. Set up experiment monitoring and guardrails")
    elif result.feasibility_status == "MARGINAL":
        print("   1. Review warnings and assess acceptable risk level")
        print("   2. Consider extending maximum duration or reducing effect size")
        print("   3. Implement additional monitoring for identified risks")
    else:
        print("   1. Consider reducing target effect size")
        print("   2. Investigate ways to increase eligible user traffic")
        print("   3. Accept lower statistical power (increase alpha or decrease power)")
        print("   4. Extend maximum allowable experiment duration")

def save_results_to_json(result, output_file):
    """Save detailed results to JSON file for further analysis"""
    
    # Convert dataclass to dictionary for JSON serialization
    result_dict = {
        'experiment_name': result.experiment_name,
        'config_version': result.config_version,
        'analysis_timestamp': pd.Timestamp.now().isoformat(),
        
        'statistical_parameters': {
            'baseline_rate': result.baseline_rate,
            'treatment_rate': result.treatment_rate, 
            'effect_size': result.effect_size,
            'statistical_power': result.statistical_power,
            'significance_level': result.significance_level
        },
        
        'sample_size_requirements': {
            'required_sample_per_variant': result.required_sample_per_variant,
            'total_required_sample': result.total_required_sample
        },
        
        'traffic_analysis': {
            'daily_eligible_users': result.daily_eligible_users,
            'daily_users_per_variant': result.daily_users_per_variant,
            'traffic_variability': result.traffic_variability
        },
        
        'duration_requirements': {
            'required_duration_days': result.required_duration_days,
            'required_duration_weeks': result.required_duration_weeks,
            'final_planned_duration': result.final_planned_duration
        },
        
        'feasibility_assessment': {
            'status': result.feasibility_status,
            'reasons': result.feasibility_reasons,
            'assumptions_met': result.assumptions_met,
            'warnings': result.warnings
        },
        
        'calendar_recommendations': {
            'suggested_start_dates': result.suggested_start_dates
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(result_dict, f, indent=2, default=str)
    
    print(f"\n💾 Detailed results saved to: {output_file}")

def main():
    """Main CLI entry point"""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Handle list experiments request
    if args.list_experiments:
        experiments = list_available_experiments()
        print("\n📋 Available Experiments:")
        for exp in experiments:
            print(f"   • {exp}")
        print(f"\nFound {len(experiments)} experiment(s)")
        return
    
    # Validate experiment name provided
    if not args.experiment_name:
        print("❌ Error: experiment name is required")
        parser.print_help()
        sys.exit(1)
    
    # Validate experiment exists
    available_experiments = list_available_experiments()
    if args.experiment_name not in available_experiments:
        print(f"❌ Error: experiment '{args.experiment_name}' not found")
        print(f"\nAvailable experiments: {', '.join(available_experiments)}")
        sys.exit(1)
    
    try:
        # Configure logging level
        import logging
        if args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        # Initialize analyzer and run analysis
        print(f"🚀 Starting power analysis for: {args.experiment_name}")
        
        # Validate reference date if provided
        reference_date = None
        if args.reference_date:
            try:
                datetime.strptime(args.reference_date, '%Y-%m-%d')
                reference_date = args.reference_date
                print(f"📅 Using reference date: {reference_date} (historical simulation)")
            except ValueError:
                print(f"❌ Invalid reference date format: {args.reference_date}. Use YYYY-MM-DD")
                sys.exit(1)
        else:
            print(f"📅 Using current date (live experiment mode)")
        
        analyzer = ExperimentPowerAnalysis(
            project_id=args.project_id,
            use_mock_data=args.use_mock_data,
            reference_date=reference_date
        )
        
        if args.validate_only:
            # Just validate the config without full analysis
            from flit_experiment_configs import validate_experiment_config
            is_valid = validate_experiment_config(args.experiment_name)
            if is_valid:
                print("✅ Experiment configuration is valid")
            else:
                print("❌ Experiment configuration has errors")
                sys.exit(1)
            return
        
        # Run full power analysis
        result = analyzer.assess_experiment_feasibility(args.experiment_name)
        
        # Display results
        format_result_summary(result)
        
        # Save to file if requested
        if args.output:
            save_results_to_json(result, args.output)
        
        # Exit with appropriate code for CI/CD integration
        if result.feasibility_status == "FEASIBLE":
            print(f"\n🎉 Analysis complete - Experiment is ready!")
            sys.exit(0)
        elif result.feasibility_status == "MARGINAL":
            print(f"\n⚠️ Analysis complete - Review warnings before proceeding")
            sys.exit(0)  # Still success, but with warnings
        else:
            print(f"\n❌ Analysis complete - Experiment requires changes")
            sys.exit(1)  # Failure for CI/CD pipelines
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Analysis cancelled by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Power analysis failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()