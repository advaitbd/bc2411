"""
schedule_variation_visualization.py

This script runs the standard scheduling model (without deadline penalty)
for a grid of alpha (leisure weight) and beta (stress weight) values and visualizes
the resulting schedules in a set of Gantt charts arranged in a grid.
Each subplot represents one (alpha, beta) combination.

Assumptions:
- Uses the same data-generation functions (auto_generate_tasks and auto_generate_blocked)
  and the data preparation function from sensitivity_analysis.py.
- Tasks are scheduled by solve_no_y (the standard model).
- Time slots start at 8 AM and end at 10 PM (15-minute intervals).
- The schedule is assumed to be non-overlapping so that tasks are assigned to separate rows.
  If tasks could overlap (or if the scheduler might return multiple tasks per “lane”),
  a more sophisticated allocation algorithm would be needed.

Usage:
    python schedule_variation_visualization.py
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta

# Import the scheduler and data generation functions from your modules
from allocation_logic_no_y import solve_schedule_gurobi as solve_no_y, get_day0_ref_midnight, datetime_to_slot
from app import auto_generate_tasks, auto_generate_blocked

# Create output directory for schedule charts
os.makedirs('schedule_variation_results', exist_ok=True)

# Configuration for time slots (must match the scheduler configuration)
start_hour = 8
end_hour = 22
slots_per_day = (end_hour - start_hour) * 4  # 15-minute slots
total_slots = slots_per_day * 7  # For 7 days

def prepare_data_for_solver(tasks, blocked_intervals):
    """Convert tasks and blocked intervals into the format required by the scheduler."""
    solver_tasks = []
    # Reference day midnight: from the imported module.
    day0_ref = get_day0_ref_midnight()

    for task in tasks:
        # Convert task duration (in minutes) to slots (ceiling division by 15)
        duration_slots = (task["duration"] + 14) // 15
        # Parse deadline and convert to a slot number (assumes ISO string with 'Z' replaced by +00:00)
        deadline_dt = datetime.fromisoformat(task["deadline"].replace('Z', '+00:00')).replace(tzinfo=None)
        deadline_slot = datetime_to_slot(deadline_dt, start_hour, end_hour, slots_per_day, total_slots)
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

    # Process blocked intervals into commitments dictionary
    solver_commitments = {}
    for block in blocked_intervals:
        start_dt = datetime.fromisoformat(block["startTime"].replace('Z', '+00:00')).replace(tzinfo=None)
        end_dt = datetime.fromisoformat(block["endTime"].replace('Z', '+00:00')).replace(tzinfo=None)
        start_slot = datetime_to_slot(start_dt, start_hour, end_hour, slots_per_day, total_slots)
        # Subtract a microsecond for correct endpoint conversion
        end_slot = datetime_to_slot(end_dt - timedelta(microseconds=1), start_hour, end_hour, slots_per_day, total_slots)
        for slot in range(start_slot, end_slot + 1):
            if 0 <= slot < total_slots:
                solver_commitments[slot] = 15  # Mark as blocked

    return solver_tasks, solver_commitments

def run_schedule_grid(alphas, betas):
    """
    For each combination of alpha and beta, run the scheduler and store the schedule.
    Returns a nested dictionary where keys are (alpha, beta) tuples.
    """
    schedule_results = {}
    # Use a fixed seed for reproducibility
    np.random.seed(42)
    random.seed(42)
    tasks = auto_generate_tasks(num_tasks=5)
    blocked_intervals = auto_generate_blocked(n_intervals=10)
    solver_tasks, solver_commitments = prepare_data_for_solver(tasks, blocked_intervals)

    # Loop through each alpha and beta combination
    for alpha in alphas:
        for beta in betas:
            result = solve_no_y(
                tasks=solver_tasks.copy(),
                commitments=solver_commitments.copy(),
                alpha=alpha,
                beta=beta,
                daily_limit_slots=None,
                time_limit_sec=30,
                hard_task_threshold=4
            )
            # In this example we assume result['schedule'] is a list of dicts with at least:
            #   'id', 'start_slot', and 'end_slot'
            schedule_results[(alpha, beta)] = result.get('schedule', [])
    return schedule_results

def plot_schedule_gantt(ax, schedule, title=""):
    """
    Plot a Gantt chart for a given schedule on the provided axis.

    Each task is drawn as a colored rectangle. The x-axis represents time slots
    over 7 days and the y-axis represents different tasks (ordered by start time).
    """
    if not schedule:
        ax.text(0.5, 0.5, "No tasks scheduled", ha='center', va='center', transform=ax.transAxes)
        ax.set_title(title)
        return

    # Sort tasks by start_slot and assign a row for each task
    schedule = sorted(schedule, key=lambda t: t.get('start_slot', 0))
    for idx, task in enumerate(schedule):
        start = task.get('start_slot', 0)
        end = task.get('end_slot', start)  # If end_slot is not provided, assume instantaneous
        duration = end - start + 1  # +1 because slots are inclusive
        # Draw rectangle: (x,y) is bottom left; height is set to a fixed amount
        rect = patches.Rectangle((start, idx - 0.4), duration, 0.8, edgecolor='black', facecolor='skyblue', lw=1.5)
        ax.add_patch(rect)
        # Annotate with task name (or id)
        ax.text(start + duration/2, idx, str(task.get("name", task.get("id", ""))),
                ha='center', va='center', fontsize=8)

    # Set axis limits
    ax.set_xlim(0, total_slots)
    ax.set_ylim(-0.5, len(schedule) - 0.5)
    ax.set_ylabel("Task Index")
    ax.set_title(title)

    # Customize x-axis: add vertical lines for day boundaries
    for day in range(8):  # 0...7 boundaries for 7 days
        ax.axvline(day * slots_per_day, color='gray', linestyle='--', linewidth=0.5)
    # Set custom ticks for each day
    day_ticks = [day * slots_per_day + slots_per_day / 2 for day in range(7)]
    ax.set_xticks(day_ticks)
    ax.set_xticklabels([f"Day {day+1}" for day in range(7)])

def plot_schedule_grid(schedule_results, alphas, betas):
    """
    Create a grid of subplots (rows by alpha, columns by beta) that show how
    the schedules vary when alpha and beta parameters change.
    """
    n_rows = len(alphas)
    n_cols = len(betas)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 3*n_rows), squeeze=False)
    for i, alpha in enumerate(alphas):
        for j, beta in enumerate(betas):
            schedule = schedule_results.get((alpha, beta), [])
            title = f"α={alpha}, β={beta}"
            plot_schedule_gantt(axes[i][j], schedule, title=title)
    plt.suptitle("Schedule Variations with Different α and β", fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig("schedule_variation_results/schedule_grid.png", dpi=300, bbox_inches='tight')
    plt.close()

def main():
    # Define a set of values (choose a few for clarity)
    # alphas = [0.1, 1.0, 5.0]
    # betas = [0.01, 0.1, 1.0]
    # Define even wider range of alpha and beta values
    alphas = [0.1, 1.0, 5.0, 10.0, 20.0]
    betas = [0.01, 0.1, 1.0, 10.0, 20.0]

    # Get schedule results for each parameter combination
    schedule_results = run_schedule_grid(alphas, betas)

    # Plot the grid of schedules
    plot_schedule_grid(schedule_results, alphas, betas)
    print("Schedule variation grid saved to 'schedule_variation_results/schedule_grid.png'.")

if __name__ == "__main__":
    main()
