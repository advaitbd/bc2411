"""
Analyze how completion rate varies with different target rates
and how task priority affects completion likelihood.
"""
import matplotlib.pyplot as plt
import numpy as np
import os
from utils import generate_random_tasks, generate_random_commitments, run_optimization_with_params

# Create output directory if it doesn't exist
os.makedirs("plots", exist_ok=True)

def analyze_completion_rate():
    """Analyze how achieved completion rate varies with target rate."""
    print("Running completion rate analysis...")

    # Create consistent dataset for all runs
    tasks = generate_random_tasks(30, seed=42)
    commitments = generate_random_commitments(seed=42)

    # Test different target rates
    target_rates = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    achieved_rates = []
    leisure_values = []
    stress_values = []

    for rate in target_rates:
        print(f"  Testing target rate {rate}...")
        result = run_optimization_with_params(
            tasks, commitments,
            target_completion_rate=rate
        )

        achieved_rates.append(result.get("completion_rate", 0))
        leisure_values.append(result.get("total_leisure", 0))
        stress_values.append(result.get("total_stress", 0))

    # Plot target vs. achieved rates
    plt.figure(figsize=(10, 6))
    plt.plot(target_rates, target_rates, 'r--', label='Target=Achieved')
    plt.plot(target_rates, achieved_rates, 'bo-', label='Actual Achievement', linewidth=2)
    plt.xlabel('Target Completion Rate')
    plt.ylabel('Achieved Completion Rate')
    plt.title('Task Completion Rate: Target vs. Achieved')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig('plots/completion_rate_analysis.png')
    print("Saved completion rate analysis plot")

    # Create a second plot showing impact on leisure and stress
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Leisure line (left y-axis)
    color = 'tab:blue'
    ax1.set_xlabel('Target Completion Rate')
    ax1.set_ylabel('Total Leisure (minutes)', color=color)
    ax1.plot(target_rates, leisure_values, 'o-', color=color, linewidth=2)
    ax1.tick_params(axis='y', labelcolor=color)

    # Create second y-axis for stress
    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Total Stress Score', color=color)
    ax2.plot(target_rates, stress_values, 'o-', color=color, linewidth=2)
    ax2.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()
    plt.title('Effect of Target Completion Rate on Leisure and Stress')
    plt.grid(False)
    plt.savefig('plots/completion_rate_impact.png')
    print("Saved completion rate impact plot")

    return {
        'target_rates': target_rates,
        'achieved_rates': achieved_rates,
        'leisure_values': leisure_values,
        'stress_values': stress_values
    }

def analyze_priority_completion():
    """Analyze how task priority affects likelihood of being scheduled."""
    print("Running priority completion analysis...")

    # Create a dataset with varied priorities
    tasks = generate_random_tasks(50, seed=123)
    commitments = generate_random_commitments(seed=123)

    # Run optimization with 70% target rate
    result = run_optimization_with_params(
        tasks, commitments,
        target_completion_rate=0.7
    )

    # Extract scheduled tasks and their priorities
    scheduled_tasks = result.get("schedule", [])
    scheduled_ids = set(task["id"] for task in scheduled_tasks)

    # Count completion by priority level
    priority_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    priority_completed = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    for task in tasks:
        priority = task["priority"]
        priority_counts[priority] += 1

        if task["id"] in scheduled_ids:
            priority_completed[priority] += 1

    # Calculate completion rates by priority
    priority_levels = [1, 2, 3, 4, 5]
    completion_rates = [
        priority_completed[p] / priority_counts[p] if priority_counts[p] > 0 else 0
        for p in priority_levels
    ]

    # Plot priority vs completion rate
    plt.figure(figsize=(10, 6))
    plt.bar(priority_levels, completion_rates, color='skyblue')
    for i, rate in enumerate(completion_rates):
        plt.text(priority_levels[i], rate + 0.02, f"{rate:.2f}", ha='center')

    plt.xlabel('Task Priority')
    plt.ylabel('Completion Rate')
    plt.title('Task Completion Rate by Priority Level')
    plt.xticks(priority_levels)
    plt.ylim(0, 1.1)  # Set y-axis to go from 0 to 1.1 for better text visibility
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig('plots/priority_completion_rate.png')
    print("Saved priority completion rate plot")

    return {
        'priority_levels': priority_levels,
        'completion_rates': completion_rates,
        'priority_counts': priority_counts,
        'priority_completed': priority_completed
    }

if __name__ == "__main__":
    analyze_completion_rate()
    analyze_priority_completion()
