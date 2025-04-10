"""
Analyze how hard tasks are distributed across days with and without the hard task constraint.
"""
import matplotlib.pyplot as plt
import numpy as np
import os
from utils import generate_random_tasks, generate_random_commitments, run_optimization_with_params

# Create output directory if it doesn't exist
os.makedirs("plots", exist_ok=True)

def get_hard_tasks_by_day(schedule, hard_task_threshold=4):
    """Count hard tasks scheduled on each day."""
    days = [0] * 7  # One entry per day

    for task in schedule:
        # Check if task is hard
        if task.get("difficulty", 0) >= hard_task_threshold:
            # Get day from start_slot (simplified)
            day = task.get("start_slot", 0) // 56  # 56 slots per day
            if 0 <= day < 7:
                days[day] += 1

    return days

def analyze_hard_task_distribution():
    """Compare hard task distribution with and without the constraint."""
    print("Running hard task distribution analysis...")

    # Generate tasks with a good number of hard tasks
    tasks = []
    for i in range(35):
        # Make 40% of tasks hard (difficulty 4-5)
        difficulty = 4 if i % 10 < 4 else np.random.randint(1, 4)
        task = {
            "id": f"task-{i}",
            "name": f"Task {i+1}",
            "priority": np.random.randint(1, 6),
            "difficulty": difficulty,
            "duration": np.random.choice([30, 45, 60, 90]),
            "deadline": np.random.randint(1, 6),  # 1-5 days
            "preference": np.random.choice(["morning", "afternoon", "evening", "any"])
        }
        tasks.append(task)

    commitments = generate_random_commitments(seed=42)

    # Run optimization with hard task constraint
    result_with = run_optimization_with_params(
        tasks, commitments,
        target_completion_rate=0.8,
        hard_task_threshold=4
    )

    # Run optimization without hard task constraint
    # We do this by setting the threshold very high (6) so no tasks are considered "hard"
    result_without = run_optimization_with_params(
        tasks, commitments,
        target_completion_rate=0.8,
        hard_task_threshold=6
    )

    # Get hard tasks by day for both results
    hard_tasks_with = get_hard_tasks_by_day(result_with.get("schedule", []), 4)
    hard_tasks_without = get_hard_tasks_by_day(result_without.get("schedule", []), 4)

    # Plot the comparison
    days = list(range(7))
    day_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    plt.figure(figsize=(12, 7))
    width = 0.35

    # Create the bars
    plt.bar([d - width/2 for d in days], hard_tasks_with, width, label='With Constraint', color='skyblue')
    plt.bar([d + width/2 for d in days], hard_tasks_without, width, label='Without Constraint', color='coral')

    # Add labels and title
    plt.xlabel('Day of Week')
    plt.ylabel('Number of Hard Tasks (Difficulty ≥ 4)')
    plt.title('Hard Task Distribution With vs Without Constraint')
    plt.xticks(days, day_labels, rotation=45)
    plt.legend(loc='upper right')

    # Add value labels above the bars
    for i, v in enumerate(hard_tasks_with):
        plt.text(i - width/2, v + 0.1, str(v), ha='center', fontweight='bold')

    for i, v in enumerate(hard_tasks_without):
        plt.text(i + width/2, v + 0.1, str(v), ha='center', fontweight='bold')

    # Add a horizontal line at y=1 to show the constraint limit
    plt.axhline(y=1, color='red', linestyle='--', alpha=0.7)
    plt.text(6.5, 1.1, "Constraint Limit", color='red', ha='right')

    plt.tight_layout()
    plt.savefig('plots/hard_task_distribution.png')
    print("Saved hard task distribution plot")

    return {
        'days': days,
        'with_constraint': hard_tasks_with,
        'without_constraint': hard_tasks_without
    }

def analyze_task_selection_patterns():
    """Analyze characteristics of scheduled vs. unscheduled tasks."""
    print("Running task selection patterns analysis...")

    # Generate tasks
    tasks = generate_random_tasks(50, seed=345)
    commitments = generate_random_commitments(seed=345)

    # Run optimization
    result = run_optimization_with_params(
        tasks, commitments,
        target_completion_rate=0.7,
        hard_task_threshold=4
    )

    # Extract scheduled tasks
    scheduled_tasks = result.get("schedule", [])
    scheduled_ids = set(task["id"] for task in scheduled_tasks)

    # Separate scheduled and unscheduled tasks
    scheduled = []
    unscheduled = []

    for task in tasks:
        task_features = {
            'priority': task['priority'],
            'difficulty': task['difficulty'],
            'duration': task['duration'] // 15  # Convert to slots (15 min each)
        }

        if task["id"] in scheduled_ids:
            scheduled.append(task_features)
        else:
            unscheduled.append(task_features)

    # Calculate average features
    avg_scheduled = {
        'priority': np.mean([t['priority'] for t in scheduled]),
        'difficulty': np.mean([t['difficulty'] for t in scheduled]),
        'duration': np.mean([t['duration'] for t in scheduled])
    }

    avg_unscheduled = {
        'priority': np.mean([t['priority'] for t in unscheduled]),
        'difficulty': np.mean([t['difficulty'] for t in unscheduled]),
        'duration': np.mean([t['duration'] for t in unscheduled])
    }

    # Create bar chart comparing scheduled vs unscheduled tasks
    features = ['Priority', 'Difficulty', 'Duration (slots)']
    scheduled_values = [avg_scheduled['priority'], avg_scheduled['difficulty'], avg_scheduled['duration']]
    unscheduled_values = [avg_unscheduled['priority'], avg_unscheduled['difficulty'], avg_unscheduled['duration']]

    plt.figure(figsize=(10, 6))
    width = 0.35
    x = np.arange(len(features))

    plt.bar(x - width/2, scheduled_values, width, label='Scheduled Tasks', color='green', alpha=0.7)
    plt.bar(x + width/2, unscheduled_values, width, label='Unscheduled Tasks', color='red', alpha=0.7)

    # Add value labels
    for i, v in enumerate(scheduled_values):
        plt.text(i - width/2, v + 0.05, f"{v:.2f}", ha='center')

    for i, v in enumerate(unscheduled_values):
        plt.text(i + width/2, v + 0.05, f"{v:.2f}", ha='center')

    plt.xlabel('Task Feature')
    plt.ylabel('Average Value')
    plt.title('Characteristics of Scheduled vs. Unscheduled Tasks')
    plt.xticks(x, features)
    plt.legend()

    plt.tight_layout()
    plt.savefig('plots/task_selection_patterns.png')
    print("Saved task selection patterns plot")

    return {
        'features': features,
        'avg_scheduled': avg_scheduled,
        'avg_unscheduled': avg_unscheduled
    }

if __name__ == "__main__":
    analyze_hard_task_distribution()
    analyze_task_selection_patterns()
