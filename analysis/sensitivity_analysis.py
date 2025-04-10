"""
Analyze sensitivity of the optimization model to different parameter values.
"""
import matplotlib.pyplot as plt
import numpy as np
import os
from utils import generate_random_tasks, generate_random_commitments, run_optimization_with_params

# Create output directory if it doesn't exist
os.makedirs("plots", exist_ok=True)

def analyze_threshold_sensitivity():
    """Analyze how changing the hard task threshold affects schedule quality."""
    print("Running hard task threshold sensitivity analysis...")

    # Create consistent dataset
    tasks = generate_random_tasks(40, seed=456)
    commitments = generate_random_commitments(seed=456)

    # Test different hard task thresholds
    thresholds = [2, 3, 4, 5]
    results = []

    for threshold in thresholds:
        print(f"  Testing hard task threshold {threshold}...")
        result = run_optimization_with_params(
            tasks, commitments,
            target_completion_rate=0.7,
            hard_task_threshold=threshold
        )

        # Store metrics
        results.append({
            'threshold': threshold,
            'leisure': result.get('total_leisure', 0),
            'stress': result.get('total_stress', 0),
            'completion_rate': result.get('completion_rate', 0),
            'solve_time': result.get('solve_time_seconds', 0)
        })

    # Extract data for plotting
    leisure_values = [r['leisure'] for r in results]
    stress_values = [r['stress'] for r in results]
    completion_values = [100 * r['completion_rate'] for r in results]  # Convert to percentage
    solve_time_values = [r['solve_time'] for r in results]

    # Create plot for leisure and stress
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Leisure line (left y-axis)
    color = 'tab:blue'
    ax1.set_xlabel('Hard Task Threshold')
    ax1.set_ylabel('Total Leisure (minutes)', color=color)
    ax1.plot(thresholds, leisure_values, 'o-', color=color, linewidth=2)
    ax1.tick_params(axis='y', labelcolor=color)

    # Create second y-axis for stress
    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Total Stress Score', color=color)
    ax2.plot(thresholds, stress_values, 's-', color=color, linewidth=2)
    ax2.tick_params(axis='y', labelcolor=color)

    # Add a legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, ['Leisure', 'Stress'], loc='upper left')

    fig.tight_layout()
    plt.title('Effect of Hard Task Threshold on Leisure and Stress')
    plt.grid(False)
    plt.savefig('plots/threshold_sensitivity_leisure_stress.png')
    print("Saved threshold sensitivity plot (leisure/stress)")

    # Create plot for completion rate and solve time
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Completion rate line (left y-axis)
    color = 'tab:green'
    ax1.set_xlabel('Hard Task Threshold')
    ax1.set_ylabel('Completion Rate (%)', color=color)
    ax1.plot(thresholds, completion_values, 'o-', color=color, linewidth=2)
    ax1.tick_params(axis='y', labelcolor=color)

    # Create second y-axis for solve time
    ax2 = ax1.twinx()
    color = 'tab:purple'
    ax2.set_ylabel('Solve Time (seconds)', color=color)
    ax2.plot(thresholds, solve_time_values, 's-', color=color, linewidth=2)
    ax2.tick_params(axis='y', labelcolor=color)

    # Add a legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, ['Completion Rate', 'Solve Time'], loc='upper right')

    fig.tight_layout()
    plt.title('Effect of Hard Task Threshold on Completion Rate and Solve Time')
    plt.grid(False)
    plt.savefig('plots/threshold_sensitivity_completion_time.png')
    print("Saved threshold sensitivity plot (completion/solve time)")

    return {
        'thresholds': thresholds,
        'results': results
    }

def analyze_objective_weights():
    """Analyze how different alpha/beta weights affect the objective function."""
    print("Running objective weights sensitivity analysis...")

    # Create consistent dataset
    tasks = generate_random_tasks(30, seed=789)
    commitments = generate_random_commitments(seed=789)

    # Test different alpha values (keeping beta=0.1 constant)
    alpha_values = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    results = []

    for alpha in alpha_values:
        beta = 0.1  # Keep beta constant
        print(f"  Testing alpha={alpha}, beta={beta}...")

        result = run_optimization_with_params(
            tasks, commitments,
            alpha=alpha,
            beta=beta,
            target_completion_rate=0.7,
            hard_task_threshold=4
        )

        # Calculate objective value
        objective = alpha * result.get('total_leisure', 0) - beta * result.get('total_stress', 0)

        # Store metrics
        results.append({
            'alpha': alpha,
            'beta': beta,
            'alpha_beta_ratio': alpha/beta,
            'leisure': result.get('total_leisure', 0),
            'stress': result.get('total_stress', 0),
            'objective': objective,
            'completion_rate': result.get('completion_rate', 0)
        })

    # Extract data for plotting
    ratios = [r['alpha_beta_ratio'] for r in results]
    leisure_values = [r['leisure'] for r in results]
    stress_values = [r['stress'] for r in results]
    objective_values = [r['objective'] for r in results]

    # Create plot
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Leisure and stress lines
    ax1.set_xlabel('Alpha/Beta Ratio (Higher means leisure is more important)')
    ax1.set_ylabel('Minutes / Stress Score')
    line1 = ax1.plot(ratios, leisure_values, 'o-', color='tab:blue', linewidth=2, label='Leisure (min)')
    line2 = ax1.plot(ratios, stress_values, 's-', color='tab:red', linewidth=2, label='Stress Score')

    # Create second y-axis for objective value
    ax2 = ax1.twinx()
    ax2.set_ylabel('Objective Function Value')
    line3 = ax2.plot(ratios, objective_values, '^-', color='tab:green', linewidth=2, label='Objective Value')

    # Add a legend
    lines = line1 + line2 + line3
    labels = ['Leisure (min)', 'Stress Score', 'Objective Value']
    ax1.legend(lines, labels, loc='upper left')

    # Use log scale for x-axis as ratios can vary widely
    ax1.set_xscale('log')

    # Set custom x-tick labels
    ax1.set_xticks(ratios)
    ax1.set_xticklabels([f"{r:.1f}" for r in ratios])

    fig.tight_layout()
    plt.title('Effect of Alpha/Beta Ratio on Schedule Quality')
    plt.grid(False)
    plt.savefig('plots/objective_weights_sensitivity.png')
    print("Saved objective weights sensitivity plot")

    # Create scatter plot showing leisure vs stress trade-off
    plt.figure(figsize=(10, 6))
    plt.scatter(stress_values, leisure_values, s=80, c=ratios, cmap='viridis')

    # Add labels for each point showing the alpha/beta ratio
    for i, r in enumerate(ratios):
        plt.annotate(f"α/β={r:.1f}",
                    (stress_values[i], leisure_values[i]),
                    xytext=(7, 0),
                    textcoords='offset points')

    plt.xlabel('Stress Score')
    plt.ylabel('Leisure Time (minutes)')
    plt.title('Leisure vs. Stress Trade-off at Different Alpha/Beta Ratios')
    plt.colorbar(label='Alpha/Beta Ratio')
    plt.grid(True, alpha=0.3)
    plt.savefig('plots/leisure_stress_tradeoff.png')
    print("Saved leisure-stress tradeoff plot")

    return {
        'alpha_values': alpha_values,
        'ratios': ratios,
        'results': results
    }

if __name__ == "__main__":
    analyze_threshold_sensitivity()
    analyze_objective_weights()
