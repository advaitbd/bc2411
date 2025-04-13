# sensitivity_analysis.py
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import time
from itertools import product
import os
from datetime import datetime, timedelta
import random
# Import the scheduler functions
from allocation_logic_no_y import solve_schedule_gurobi as solve_no_y
from allocation_logic_deadline_penalty import solve_schedule_gurobi as solve_with_deadline_penalty
from app import auto_generate_tasks, auto_generate_blocked

# Configure plots
plt.style.use('seaborn-v0_8-whitegrid')
sns.set(font_scale=1.2)
sns.set_style("whitegrid")

# Create output directory for charts
os.makedirs('sensitivity_results', exist_ok=True)

def run_sensitivity_analysis(models="both"):
    """Run comprehensive sensitivity analysis on scheduler models.
    
    Args:
        models (str): Which models to run sensitivity analysis for:
            - "standard": Only run the standard model (without deadline penalty)
            - "deadline": Only run the deadline penalty model
            - "both": Run both models (default)
    """
    print(f"Starting sensitivity analysis for {models} model(s)...")
    
    # Validate models parameter
    if models not in ["standard", "deadline", "both"]:
        raise ValueError("'models' must be one of: 'standard', 'deadline', 'both'")

    # Generate consistent test data (use seed for reproducibility)
    np.random.seed(42)
    random.seed(42)
    tasks = auto_generate_tasks(num_tasks=10)
    blocked_intervals = auto_generate_blocked(n_intervals=10)

    # Convert tasks and blocked intervals to solver format
    solver_tasks, solver_commitments = prepare_data_for_solver(tasks, blocked_intervals)

    # Define parameter ranges for sensitivity analysis
    alpha_values = [0.1, 0.5, 1.0, 2.0, 5.0]
    beta_values = [0.01, 0.05, 0.1, 0.5, 1.0]
    gamma_values = [0.0, 0.5, 1.0, 2.0, 5.0]  # For deadline penalty model
    hard_task_thresholds = [3, 4, 5]
    daily_limit_slots = [None, 12, 16, 20]

    # Run sensitivity analyses
    alpha_sensitivity(solver_tasks, solver_commitments, alpha_values, models)
    beta_sensitivity(solver_tasks, solver_commitments, beta_values, models)
    
    # Only run gamma sensitivity for deadline model
    if models in ["deadline", "both"]:
        gamma_sensitivity(solver_tasks, solver_commitments, gamma_values)
    
    hard_task_sensitivity(solver_tasks, solver_commitments, hard_task_thresholds, models)
    daily_limit_sensitivity(solver_tasks, solver_commitments, daily_limit_slots, models)

    # Run model comparison only if both models are selected
    if models == "both":
        compare_models(solver_tasks, solver_commitments)

    print(f"Sensitivity analysis for {models} model(s) complete. Results saved to 'sensitivity_results' directory.")

def prepare_data_for_solver(tasks, blocked_intervals):
    """Convert task and blocked interval data to solver format."""
    # Process tasks to solver format
    solver_tasks = []
    start_hour = 8
    end_hour = 22
    slots_per_day = (end_hour - start_hour) * 4
    total_slots = slots_per_day * 7  # 7 days

    from allocation_logic_no_y import get_day0_ref_midnight, datetime_to_slot

    day0_ref = get_day0_ref_midnight()

    for i, task in enumerate(tasks):
        # Extract task information
        duration_min = task["duration"]
        duration_slots = (duration_min + 14) // 15  # Ceiling division by 15

        # Parse deadline
        deadline_str = task["deadline"]
        deadline_dt = datetime.fromisoformat(deadline_str.replace('Z', '+00:00')).replace(tzinfo=None)
        deadline_slot = datetime_to_slot(deadline_dt, start_hour, end_hour, slots_per_day, total_slots)

        # Create solver task
        solver_task = {
            "id": task["id"],
            "name": task["name"],
            "priority": task["priority"],
            "difficulty": task["difficulty"],
            "duration_slots": duration_slots,
            "deadline_slot": deadline_slot,
            "preference": task["preference"]
        }
        solver_tasks.append(solver_task)

    # Process blocked intervals to solver commitments
    solver_commitments = {}
    for block in blocked_intervals:
        start_str = block["startTime"]
        end_str = block["endTime"]

        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00')).replace(tzinfo=None)
        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')).replace(tzinfo=None)

        start_slot = datetime_to_slot(start_dt, start_hour, end_hour, slots_per_day, total_slots)
        end_slot = datetime_to_slot(end_dt - timedelta(microseconds=1), start_hour, end_hour, slots_per_day, total_slots)

        for slot in range(start_slot, end_slot + 1):
            if 0 <= slot < total_slots:
                solver_commitments[slot] = 15  # Mark as blocked

    return solver_tasks, solver_commitments

def alpha_sensitivity(tasks, commitments, alpha_values, models="both"):
    """Analyze sensitivity to alpha parameter (leisure weight).
    
    Args:
        tasks: List of tasks
        commitments: Dictionary of commitments
        alpha_values: List of alpha values to test
        models: Which models to run ("standard", "deadline", or "both")
    """
    results_no_y = []
    results_deadline = []

    # Run selected models with different alpha values
    for alpha in alpha_values:
        # Run standard model if selected
        if models in ["standard", "both"]:
            result_no_y = solve_no_y(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=alpha,
                beta=0.1,  # Fixed
                daily_limit_slots=None,
                time_limit_sec=30,
                hard_task_threshold=4
            )
            results_no_y.append({
                'alpha': alpha,
                'objective': result_no_y.get('objective_value', 0),
                'leisure': result_no_y.get('total_leisure', 0),
                'stress': result_no_y.get('total_stress', 0),
                'completion_rate': result_no_y.get('completion_rate', 0)
            })

        # Run deadline penalty model if selected
        if models in ["deadline", "both"]:
            result_deadline = solve_with_deadline_penalty(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=alpha,
                beta=0.1,  # Fixed
                gamma=1.0,  # Fixed
                daily_limit_slots=None,
                time_limit_sec=30,
                hard_task_threshold=4
            )
            results_deadline.append({
                'alpha': alpha,
                'objective': result_deadline.get('objective_value', 0),
                'leisure': result_deadline.get('total_leisure', 0),
                'stress': result_deadline.get('total_stress', 0),
                'completion_rate': result_deadline.get('completion_rate', 0)
            })

    # Create dataframes
    df_no_y = pd.DataFrame(results_no_y) if results_no_y else None
    df_deadline = pd.DataFrame(results_deadline) if results_deadline else None

    # Plot results
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Sensitivity to Alpha (Leisure Weight)', fontsize=16)

    metrics = ['objective', 'leisure', 'stress', 'completion_rate']
    titles = ['Objective Value', 'Total Leisure (minutes)', 'Total Stress', 'Completion Rate']

    for i, (metric, title) in enumerate(zip(metrics, titles)):
        row, col = i // 2, i % 2
        ax = axs[row, col]

        # Plot standard model if selected
        if models in ["standard", "both"] and df_no_y is not None:
            ax.plot(df_no_y['alpha'], df_no_y[metric], 'o-', label='Standard Model')
        
        # Plot deadline model if selected
        if models in ["deadline", "both"] and df_deadline is not None:
            ax.plot(df_deadline['alpha'], df_deadline[metric], 's-', label='Deadline Penalty Model')

        ax.set_xlabel('Alpha (α)')
        ax.set_ylabel(title)
        ax.set_title(title)
        ax.legend()

        # Add data labels
        if models in ["standard", "both"] and df_no_y is not None:
            for x, y in zip(df_no_y['alpha'], df_no_y[metric]):
                ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                            xytext=(0, 10), ha='center')
        
        if models in ["deadline", "both"] and df_deadline is not None:
            for x, y in zip(df_deadline['alpha'], df_deadline[metric]):
                ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                            xytext=(0, 10), ha='center')

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    
    # Save with model-specific filename
    if models == "both":
        filename = 'alpha_sensitivity.png'
    elif models == "standard":
        filename = 'alpha_sensitivity_standard.png'
    else:
        filename = 'alpha_sensitivity_deadline.png'
        
    plt.savefig(f'sensitivity_results/{filename}', dpi=300, bbox_inches='tight')
    plt.close()

def beta_sensitivity(tasks, commitments, beta_values, models="both"):
    """Analyze sensitivity to beta parameter (stress weight).
    
    Args:
        tasks: List of tasks
        commitments: Dictionary of commitments
        beta_values: List of beta values to test
        models: Which models to run ("standard", "deadline", or "both")
    """
    results_no_y = []
    results_deadline = []

    # Run selected models with different beta values
    for beta in beta_values:
        # Run standard model if selected
        if models in ["standard", "both"]:
            result_no_y = solve_no_y(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=1.0,  # Fixed
                beta=beta,
                daily_limit_slots=None,
                time_limit_sec=30,
                hard_task_threshold=4
            )
            results_no_y.append({
                'beta': beta,
                'objective': result_no_y.get('objective_value', 0),
                'leisure': result_no_y.get('total_leisure', 0),
                'stress': result_no_y.get('total_stress', 0),
                'completion_rate': result_no_y.get('completion_rate', 0)
            })

        # Run deadline penalty model if selected
        if models in ["deadline", "both"]:
            result_deadline = solve_with_deadline_penalty(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=1.0,  # Fixed
                beta=beta,
                gamma=1.0,  # Fixed
                daily_limit_slots=None,
                time_limit_sec=30,
                hard_task_threshold=4
            )
            results_deadline.append({
                'beta': beta,
                'objective': result_deadline.get('objective_value', 0),
                'leisure': result_deadline.get('total_leisure', 0),
                'stress': result_deadline.get('total_stress', 0),
                'completion_rate': result_deadline.get('completion_rate', 0)
            })

    # Create dataframes
    df_no_y = pd.DataFrame(results_no_y) if results_no_y else None
    df_deadline = pd.DataFrame(results_deadline) if results_deadline else None

    # Plot results
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Sensitivity to Beta (Stress Weight)', fontsize=16)

    metrics = ['objective', 'leisure', 'stress', 'completion_rate']
    titles = ['Objective Value', 'Total Leisure (minutes)', 'Total Stress', 'Completion Rate']

    for i, (metric, title) in enumerate(zip(metrics, titles)):
        row, col = i // 2, i % 2
        ax = axs[row, col]

        # Plot standard model if selected
        if models in ["standard", "both"]:
            ax.plot(df_no_y['beta'], df_no_y[metric], 'o-', label='Standard Model')
        
        # Plot deadline model if selected
        if models in ["deadline", "both"]:
            ax.plot(df_deadline['beta'], df_deadline[metric], 's-', label='Deadline Penalty Model')

        ax.set_xlabel('Beta (β)')
        ax.set_ylabel(title)
        ax.set_title(title)
        ax.legend()

        # Add data labels
        if models in ["standard", "both"]:
            for x, y in zip(df_no_y['beta'], df_no_y[metric]):
                ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                            xytext=(0, 10), ha='center')
        
        if models in ["deadline", "both"]:
            for x, y in zip(df_deadline['beta'], df_deadline[metric]):
                ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                            xytext=(0, 10), ha='center')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # Save with model-specific filename
    if models == "both":
        filename = 'beta_sensitivity.png'
    elif models == "standard":
        filename = 'beta_sensitivity_standard.png'
    else:
        filename = 'beta_sensitivity_deadline.png'
        
    plt.savefig(f'sensitivity_results/{filename}', dpi=300, bbox_inches='tight')
    plt.close()

def gamma_sensitivity(tasks, commitments, gamma_values):
    """Analyze sensitivity to gamma parameter (deadline penalty weight)."""
    results = []

    # Run deadline penalty model with different gamma values
    for gamma in gamma_values:
        result = solve_with_deadline_penalty(
            tasks=tasks.copy(),
            commitments=commitments.copy(),
            alpha=1.0,  # Fixed
            beta=0.1,   # Fixed
            gamma=gamma,
            daily_limit_slots=None,
            time_limit_sec=30,
            hard_task_threshold=4
        )
        results.append({
            'gamma': gamma,
            'objective': result.get('objective_value', 0),
            'leisure': result.get('total_leisure', 0),
            'stress': result.get('total_stress', 0),
            'completion_rate': result.get('completion_rate', 0)
        })

    # Create dataframe
    df = pd.DataFrame(results)

    # Plot results
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Sensitivity to Gamma (Deadline Penalty Weight)', fontsize=16)

    metrics = ['objective', 'leisure', 'stress', 'completion_rate']
    titles = ['Objective Value', 'Total Leisure (minutes)', 'Total Stress', 'Completion Rate']

    for i, (metric, title) in enumerate(zip(metrics, titles)):
        row, col = i // 2, i % 2
        ax = axs[row, col]

        ax.plot(df['gamma'], df[metric], 'o-', label='Deadline Penalty Model')

        ax.set_xlabel('Gamma (γ)')
        ax.set_ylabel(title)
        ax.set_title(title)

        # Add data labels
        for x, y in zip(df['gamma'], df[metric]):
            ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                        xytext=(0, 10), ha='center')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig('sensitivity_results/gamma_sensitivity.png', dpi=300, bbox_inches='tight')
    plt.close()

    # Analyze task scheduling relative to deadlines
    analyze_deadline_proximity(tasks, commitments, gamma_values)

def analyze_deadline_proximity(tasks, commitments, gamma_values):
    """Analyze how gamma affects task scheduling relative to deadlines."""
    proximity_data = []

    for gamma in gamma_values:
        result = solve_with_deadline_penalty(
            tasks=tasks.copy(),
            commitments=commitments.copy(),
            alpha=1.0,  # Fixed
            beta=0.1,   # Fixed
            gamma=gamma,
            daily_limit_slots=None,
            time_limit_sec=30,
            hard_task_threshold=4
        )

        if 'schedule' in result and result['schedule']:
            # For each task in schedule, calculate proximity to deadline
            for task in result['schedule']:
                task_id = task['id']
                start_slot = task['start_slot']

                # Find original task to get deadline
                deadline_slot = next((t['deadline_slot'] for t in tasks if t['id'] == task_id), None)

                if deadline_slot is not None:
                    # Calculate latest possible start slot
                    duration_slots = task['end_slot'] - task['start_slot'] + 1
                    latest_start = deadline_slot - duration_slots + 1

                    # Calculate proximity ratio (0 = scheduled at earliest, 1 = scheduled at latest possible slot)
                    proximity = start_slot / max(1, latest_start) if latest_start > 0 else 0

                    proximity_data.append({
                        'gamma': gamma,
                        'task_id': task_id,
                        'task_name': task['name'],
                        'proximity': proximity,
                        'priority': task['priority'],
                        'difficulty': task['difficulty']
                    })

    if proximity_data:
        # Create dataframe
        df_proximity = pd.DataFrame(proximity_data)

        # Aggregate by gamma
        df_agg = df_proximity.groupby('gamma')['proximity'].mean().reset_index()

        # Plot proximity vs gamma
        plt.figure(figsize=(10, 6))
        plt.plot(df_agg['gamma'], df_agg['proximity'], 'o-', linewidth=2, markersize=10)

        plt.title('Effect of Gamma on Task Scheduling Proximity to Deadlines', fontsize=14)
        plt.xlabel('Gamma (γ)', fontsize=12)
        plt.ylabel('Average Proximity to Deadline\n(0 = Early, 1 = Last Minute)', fontsize=12)
        plt.grid(True, alpha=0.3)

        # Add data labels
        for x, y in zip(df_agg['gamma'], df_agg['proximity']):
            plt.annotate(f'{y:.2f}', (x, y), textcoords='offset points',
                         xytext=(0, 10), ha='center')

        plt.tight_layout()
        plt.savefig('sensitivity_results/gamma_deadline_proximity.png', dpi=300, bbox_inches='tight')
        plt.close()

        # Plot proximity by task priority and difficulty for the highest gamma
        high_gamma = df_proximity[df_proximity['gamma'] == max(gamma_values)]
        if not high_gamma.empty:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

            # Priority vs proximity
            sns.boxplot(x='priority', y='proximity', data=high_gamma, ax=ax1)
            ax1.set_title(f'Proximity to Deadline by Priority (γ={max(gamma_values)})')
            ax1.set_xlabel('Task Priority')
            ax1.set_ylabel('Proximity to Deadline')

            # Difficulty vs proximity
            sns.boxplot(x='difficulty', y='proximity', data=high_gamma, ax=ax2)
            ax2.set_title(f'Proximity to Deadline by Difficulty (γ={max(gamma_values)})')
            ax2.set_xlabel('Task Difficulty')
            ax2.set_ylabel('Proximity to Deadline')

            plt.tight_layout()
            plt.savefig('sensitivity_results/proximity_by_task_attributes.png', dpi=300, bbox_inches='tight')
            plt.close()

def hard_task_sensitivity(tasks, commitments, threshold_values, models="both"):
    """Analyze sensitivity to hard task threshold.
    
    Args:
        tasks: List of tasks
        commitments: Dictionary of commitments
        threshold_values: List of hard task threshold values to test
        models: Which models to run ("standard", "deadline", or "both")
    """
    results_no_y = []
    results_deadline = []

    # Run selected models with different threshold values
    for threshold in threshold_values:
        # Run standard model if selected
        if models in ["standard", "both"]:
            result_no_y = solve_no_y(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=1.0,  # Fixed
                beta=0.1,   # Fixed
                daily_limit_slots=None,
                time_limit_sec=30,
                hard_task_threshold=threshold
            )
            results_no_y.append({
                'threshold': threshold,
                'objective': result_no_y.get('objective_value', 0),
                'leisure': result_no_y.get('total_leisure', 0),
                'stress': result_no_y.get('total_stress', 0),
                'completion_rate': result_no_y.get('completion_rate', 0)
            })

        # Run deadline penalty model if selected
        if models in ["deadline", "both"]:
            result_deadline = solve_with_deadline_penalty(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=1.0,  # Fixed
                beta=0.1,   # Fixed
                gamma=1.0,  # Fixed
                daily_limit_slots=None,
                time_limit_sec=30,
                hard_task_threshold=threshold
            )
            results_deadline.append({
                'threshold': threshold,
                'objective': result_deadline.get('objective_value', 0),
                'leisure': result_deadline.get('total_leisure', 0),
                'stress': result_deadline.get('total_stress', 0),
                'completion_rate': result_deadline.get('completion_rate', 0)
            })

    # Create dataframes
    df_no_y = pd.DataFrame(results_no_y) if results_no_y else None
    df_deadline = pd.DataFrame(results_deadline) if results_deadline else None

    # Plot results
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Sensitivity to Hard Task Threshold', fontsize=16)

    metrics = ['objective', 'leisure', 'stress', 'completion_rate']
    titles = ['Objective Value', 'Total Leisure (minutes)', 'Total Stress', 'Completion Rate']

    for i, (metric, title) in enumerate(zip(metrics, titles)):
        row, col = i // 2, i % 2
        ax = axs[row, col]

        # Plot standard model if selected
        if models in ["standard", "both"]:
            ax.plot(df_no_y['threshold'], df_no_y[metric], 'o-', label='Standard Model')
        
        # Plot deadline model if selected
        if models in ["deadline", "both"]:
            ax.plot(df_deadline['threshold'], df_deadline[metric], 's-', label='Deadline Penalty Model')

        ax.set_xlabel('Hard Task Threshold')
        ax.set_ylabel(title)
        ax.set_title(title)
        ax.legend()

        # Add data labels
        if models in ["standard", "both"]:
            for x, y in zip(df_no_y['threshold'], df_no_y[metric]):
                ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                            xytext=(0, 10), ha='center')
        
        if models in ["deadline", "both"]:
            for x, y in zip(df_deadline['threshold'], df_deadline[metric]):
                ax.annotate(f'{y:.1f}', (x, y), textcoords='offset points',
                            xytext=(0, 10), ha='center')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # Save with model-specific filename
    if models == "both":
        filename = 'hard_task_threshold_sensitivity.png'
    elif models == "standard":
        filename = 'hard_task_threshold_sensitivity_standard.png'
    else:
        filename = 'hard_task_threshold_sensitivity_deadline.png'
        
    plt.savefig(f'sensitivity_results/{filename}', dpi=300, bbox_inches='tight')
    plt.close()

def daily_limit_sensitivity(tasks, commitments, limit_values, models="both"):
    """Analyze sensitivity to daily limit slots.
    
    Args:
        tasks: List of tasks
        commitments: Dictionary of commitments
        limit_values: List of daily limit slot values to test
        models: Which models to run ("standard", "deadline", or "both")
    """
    results_no_y = []
    results_deadline = []

    # Display "None" as "No Limit" for clarity
    x_labels = ['No Limit' if limit is None else str(limit) for limit in limit_values]

    # Run selected models with different daily limit values
    for limit in limit_values:
        # Run standard model if selected
        if models in ["standard", "both"]:
            result_no_y = solve_no_y(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=1.0,  # Fixed
                beta=0.1,   # Fixed
                daily_limit_slots=limit,
                time_limit_sec=30,
                hard_task_threshold=4
            )
            results_no_y.append({
                'limit': limit,
                'limit_label': 'No Limit' if limit is None else str(limit),
                'objective': result_no_y.get('objective_value', 0),
                'leisure': result_no_y.get('total_leisure', 0),
                'stress': result_no_y.get('total_stress', 0),
                'completion_rate': result_no_y.get('completion_rate', 0)
            })

        # Run deadline penalty model if selected
        if models in ["deadline", "both"]:
            result_deadline = solve_with_deadline_penalty(
                tasks=tasks.copy(),
                commitments=commitments.copy(),
                alpha=1.0,  # Fixed
                beta=0.1,   # Fixed
                gamma=1.0,  # Fixed
                daily_limit_slots=limit,
                time_limit_sec=30,
                hard_task_threshold=4
            )
            results_deadline.append({
                'limit': limit,
                'limit_label': 'No Limit' if limit is None else str(limit),
                'objective': result_deadline.get('objective_value', 0),
                'leisure': result_deadline.get('total_leisure', 0),
                'stress': result_deadline.get('total_stress', 0),
                'completion_rate': result_deadline.get('completion_rate', 0)
            })

    # Create dataframes
    df_no_y = pd.DataFrame(results_no_y) if results_no_y else None
    df_deadline = pd.DataFrame(results_deadline) if results_deadline else None

    # Plot results
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Sensitivity to Daily Task Limit', fontsize=16)

    metrics = ['objective', 'leisure', 'stress', 'completion_rate']
    titles = ['Objective Value', 'Total Leisure (minutes)', 'Total Stress', 'Completion Rate']

    for i, (metric, title) in enumerate(zip(metrics, titles)):
        row, col = i // 2, i % 2
        ax = axs[row, col]

        # Get indices for x-axis positioning
        x_indices = range(len(x_labels))

        # Initialize sorted dataframes
        if models in ["standard", "both"]:
            df_no_y_sorted = df_no_y.sort_values(by='limit_label')
        
        if models in ["deadline", "both"]:
            df_deadline_sorted = df_deadline.sort_values(by='limit_label')

        # Plot standard model if selected
        if models in ["standard", "both"]:
            ax.plot(x_indices, df_no_y_sorted[metric], 'o-', label='Standard Model')
        
        # Plot deadline model if selected
        if models in ["deadline", "both"]:
            ax.plot(x_indices, df_deadline_sorted[metric], 's-', label='Deadline Penalty Model')

        ax.set_xticks(x_indices)
        ax.set_xticklabels(x_labels)
        ax.set_xlabel('Daily Limit (slots)')
        ax.set_ylabel(title)
        ax.set_title(title)
        ax.legend()

        # Add data labels
        if models in ["standard", "both"]:
            for i, y in enumerate(df_no_y_sorted[metric]):
                ax.annotate(f'{y:.1f}', (i, y), textcoords='offset points',
                            xytext=(0, 10), ha='center')
        
        if models in ["deadline", "both"]:
            offset = 0 if models == "deadline" else 15
            for i, y in enumerate(df_deadline_sorted[metric]):
                ax.annotate(f'{y:.1f}', (i, y), textcoords='offset points',
                            xytext=(0, 10 + offset), ha='center')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # Save with model-specific filename
    if models == "both":
        filename = 'daily_limit_sensitivity.png'
    elif models == "standard":
        filename = 'daily_limit_sensitivity_standard.png'
    else:
        filename = 'daily_limit_sensitivity_deadline.png'
        
    plt.savefig(f'sensitivity_results/{filename}', dpi=300, bbox_inches='tight')
    plt.close()

def compare_models(tasks, commitments):
    """Compare standard model with deadline penalty model across multiple metrics."""
    # Fixed parameters for comparison
    alpha = 1.0
    beta = 0.1
    gamma = 1.0
    hard_task_threshold = 4
    daily_limit_slots = None

    # Run standard model
    result_no_y = solve_no_y(
        tasks=tasks.copy(),
        commitments=commitments.copy(),
        alpha=alpha,
        beta=beta,
        daily_limit_slots=daily_limit_slots,
        time_limit_sec=30,
        hard_task_threshold=hard_task_threshold
    )

    # Run deadline penalty model
    result_deadline = solve_with_deadline_penalty(
        tasks=tasks.copy(),
        commitments=commitments.copy(),
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        daily_limit_slots=daily_limit_slots,
        time_limit_sec=30,
        hard_task_threshold=hard_task_threshold
    )

    # Extract key metrics
    metrics = ['objective_value', 'total_leisure', 'total_stress', 'completion_rate', 'solve_time_seconds']
    metric_labels = ['Objective Value', 'Total Leisure (min)', 'Total Stress', 'Completion Rate', 'Solve Time (s)']

    # Create comparison data
    comparison_data = []
    for metric, label in zip(metrics, metric_labels):
        standard_value = result_no_y.get(metric, 0)
        deadline_value = result_deadline.get(metric, 0)

        comparison_data.append({
            'Metric': label,
            'Standard Model': standard_value,
            'Deadline Penalty Model': deadline_value
        })

    # Create dataframe
    df_comparison = pd.DataFrame(comparison_data)

    # Plot bar chart comparison
    plt.figure(figsize=(12, 8))

    # Convert to long format for seaborn
    df_long = pd.melt(df_comparison, id_vars=['Metric'],
                       value_vars=['Standard Model', 'Deadline Penalty Model'],
                       var_name='Model', value_name='Value')

    # Create bar chart
    chart = sns.barplot(x='Metric', y='Value', hue='Model', data=df_long)

    plt.title('Comparison of Standard vs. Deadline Penalty Model', fontsize=16)
    plt.ylabel('Value', fontsize=12)
    plt.xlabel('', fontsize=12)
    plt.xticks(rotation=15)
    plt.legend(title='', loc='upper right')

    # Add value labels on bars
    for container in chart.containers:
        chart.bar_label(container, fmt='%.2f')

    plt.tight_layout()
    plt.savefig('sensitivity_results/model_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()

    # Also analyze task distribution by day for both models
    analyze_task_distribution(result_no_y, result_deadline)

def analyze_task_distribution(result_no_y, result_deadline):
    """Analyze how tasks are distributed across days in both models."""
    # Extract schedules
    schedule_no_y = result_no_y.get('schedule', [])
    schedule_deadline = result_deadline.get('schedule', [])

    # Count tasks per day
    days_no_y = {'Day 1': 0, 'Day 2': 0, 'Day 3': 0, 'Day 4': 0, 'Day 5': 0, 'Day 6': 0, 'Day 7': 0}
    days_deadline = days_no_y.copy()

    # Get slots per day from config
    slots_per_day = 56  # (22 - 8) * 4 = 14 hours * 4 slots per hour

    # Count by day for standard model
    for task in schedule_no_y:
        start_slot = task.get('start_slot', 0)
        day_index = start_slot // slots_per_day
        if 0 <= day_index < 7:
            days_no_y[f'Day {day_index+1}'] += 1

    # Count by day for deadline penalty model
    for task in schedule_deadline:
        start_slot = task.get('start_slot', 0)
        day_index = start_slot // slots_per_day
        if 0 <= day_index < 7:
            days_deadline[f'Day {day_index+1}'] += 1

    # Create dataframe
    data = []
    for day in days_no_y.keys():
        data.append({'Day': day, 'Model': 'Standard Model', 'Tasks': days_no_y[day]})
        data.append({'Day': day, 'Model': 'Deadline Penalty Model', 'Tasks': days_deadline[day]})

    df_distribution = pd.DataFrame(data)

    # Plot bar chart
    plt.figure(figsize=(12, 6))

    chart = sns.barplot(x='Day', y='Tasks', hue='Model', data=df_distribution)

    plt.title('Task Distribution by Day', fontsize=16)
    plt.ylabel('Number of Tasks', fontsize=12)
    plt.xlabel('Day', fontsize=12)
    plt.legend(title='', loc='upper right')

    # Add value labels on bars
    for container in chart.containers:
        chart.bar_label(container, fmt='%d')

    plt.tight_layout()
    plt.savefig('sensitivity_results/task_distribution_by_day.png', dpi=300, bbox_inches='tight')
    plt.close()

# Run the sensitivity analysis if executed directly
if __name__ == "__main__":
    import random
    import sys
    
    # Default to running both models if no argument is provided
    model_option = "both"
    
    # Allow command-line argument to specify which model to run
    if len(sys.argv) > 1:
        model_arg = sys.argv[1].lower()
        if model_arg in ["standard", "deadline", "both"]:
            model_option = model_arg
        else:
            print(f"Invalid model option: {model_arg}")
            print("Valid options are: 'standard', 'deadline', 'both'")
            sys.exit(1)
    
    print(f"Running sensitivity analysis for {model_option} model(s)...")
    run_sensitivity_analysis(models=model_option)
