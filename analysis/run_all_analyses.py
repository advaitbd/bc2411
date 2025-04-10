"""
Main script to run all analyses for the task scheduler optimization model.
"""
import os
import time
from completion_rate_analysis import analyze_completion_rate, analyze_priority_completion
from hard_task_analysis import analyze_hard_task_distribution, analyze_task_selection_patterns
from sensitivity_analysis import analyze_threshold_sensitivity, analyze_objective_weights

def run_all_analyses():
    """Run all analysis scripts and measure execution time."""
    # Create output directory if it doesn't exist
    os.makedirs("plots", exist_ok=True)

    start_time = time.time()

    print("\n" + "="*50)
    print("RUNNING ALL TASK SCHEDULER ANALYSES")
    print("="*50)

    # Run all analyses
    print("\n1. Completion Rate Analysis")
    print("-"*30)
    analyze_completion_rate()
    analyze_priority_completion()

    print("\n2. Hard Task Distribution Analysis")
    print("-"*30)
    analyze_hard_task_distribution()
    analyze_task_selection_patterns()

    print("\n3. Sensitivity Analysis")
    print("-"*30)
    analyze_threshold_sensitivity()
    analyze_objective_weights()

    # Print execution summary
    elapsed_time = time.time() - start_time
    print("\n" + "="*50)
    print(f"All analyses completed in {elapsed_time:.2f} seconds")
    print("Results saved to bc2411/analysis/plots/")
    print("="*50)

if __name__ == "__main__":
    run_all_analyses()
