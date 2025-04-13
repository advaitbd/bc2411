"""
schedule_variation_hard_threshold.py

This script runs the standard scheduling model (without deadline penalty)
for a set of hard task threshold values and visualizes the resulting
schedules in a set of Gantt charts arranged in a grid.
Each subplot represents one hard task threshold value.

Assumptions:
- Uses the same data-generation functions (auto_generate_tasks and auto_generate_blocked)
  and the data preparation function from sensitivity_analysis.py.
- Tasks are scheduled by solve_no_y (the standard model).
- Time slots start at 8 AM and end at 10 PM (15-minute intervals).
- The schedule is assumed to be non-overlapping so that tasks are assigned to separate rows.
  (If tasks could overlap or if the scheduler might return multiple tasks per “lane”,
  a more sophisticated allocation algorithm would be needed.)

Usage:
    python schedule_variation_hard_threshold.py
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta

# Import the scheduler and data generation functions from your modules
from allocation_logic_deadline_penalty import solve_schedule_gurobi as solve_no_y, get_day0_ref_midnight, datetime_to_slot
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
    # Reference day midnight from the imported module.
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

def run_schedule_grid_threshold(thresholds):
    """
    For each hard task threshold in the provided list, run the scheduler and store the schedule.
    Returns a dictionary mapping each hard task threshold value to its schedule.
    """
    schedule_results = {}
    # Use a fixed seed for reproducibility
    np.random.seed(42)
    random.seed(42)
    tasks = auto_generate_tasks(num_tasks=10)
    blocked_intervals = auto_generate_blocked(n_intervals=10)
    solver_tasks, solver_commitments = prepare_data_for_solver(tasks, blocked_intervals)

    # Fixed parameters for non-varying aspects
    fixed_alpha = 1.0
    fixed_beta = 0.1

    # Loop through each hard task threshold value
    for threshold in thresholds:
        result = solve_no_y(
            tasks=solver_tasks.copy(),
            commitments=solver_commitments.copy(),
            alpha=fixed_alpha,
            beta=fixed_beta,
            daily_limit_slots=None,
            time_limit_sec=30,
            hard_task_threshold=threshold
        )
        # We assume result['schedule'] is a list of tasks with at least: 'id', 'start_slot', and 'end_slot'
        schedule_results[threshold] = result.get('schedule', [])
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
        # Draw rectangle: (x, y) is bottom-left; height is set to a fixed amount
        rect = patches.Rectangle((start, idx - 0.4), duration, 0.8,
                                 edgecolor='black', facecolor='skyblue', lw=1.5)
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

def plot_schedule_grid_threshold(schedule_results, thresholds):
    """
    Create a grid of subplots (one per hard task threshold value) that show how
    the schedules vary when the hard task threshold changes.
    """
    n = len(thresholds)
    fig, axes = plt.subplots(1, n, figsize=(4*n, 4), squeeze=False)
    for i, threshold in enumerate(thresholds):
        schedule = schedule_results.get(threshold, [])
        title = f"Hard Threshold = {threshold}"
        plot_schedule_gantt(axes[0][i], schedule, title=title)
    plt.suptitle("Schedule Variations with Different Hard Task Thresholds", fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig("schedule_variation_results/schedule_grid_hard_threshold.png", dpi=300, bbox_inches='tight')
    plt.close()

def main():
    # Define a set of hard task threshold values (choose a few for clarity)
    thresholds = [3, 4, 5]

    # Get schedule results for each hard task threshold value
    schedule_results = run_schedule_grid_threshold(thresholds)

    # Plot the grid of schedules for the different hard task thresholds
    plot_schedule_grid_threshold(schedule_results, thresholds)
    print("Schedule variation grid saved to 'schedule_variation_results/schedule_grid_hard_threshold.png'.")

if __name__ == "__main__":
    main()
