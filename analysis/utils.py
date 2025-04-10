import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, time
import random

# Add parent directory to path so we can import from allocation_logic
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from allocation_logic import solve_schedule_gurobi, get_day0, datetime_to_slot, TOTAL_SLOTS, SLOTS_PER_DAY

def generate_random_tasks(num_tasks, seed=None):
    """
    Generate a set of random tasks for testing, with more realistic student parameters.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    tasks = []
    # (type, avg priority, avg difficulty, base_duration_min, duration_range_min, typical_preference)
    task_types = [
        ("Assignment", 4, 3, 75, 45, "any"),        # 60-120 min
        ("Study Session", 3, 2, 60, 30, "evening"), # 45-90 min
        ("Group Project", 4, 4, 120, 60, "afternoon"),# 90-180 min
        ("Reading", 2, 1, 45, 15, "any"),          # 30-60 min
        ("Exam Prep", 5, 5, 120, 30, "any"),       # 90-150 min
    ]
    # Adjust weights for more assignments/study, less frequent exam prep
    task_type_weights = [0.4, 0.3, 0.15, 0.1, 0.05]

    # Ensure day0 is initialized before calculating deadlines relative to it
    # day0 = get_day0() # Using current time's day0 for deadline calculation
    now = datetime.now() # Use current time for deadline base

    for i in range(num_tasks):
        # Choose task type based on weights
        task_type_info = random.choices(task_types, weights=task_type_weights, k=1)[0]
        task_type, base_prio, base_diff, base_duration, duration_range, typical_pref = task_type_info

        # Add some randomness to base values (slightly reduced range)
        priority = max(1, min(5, base_prio + random.randint(-1, 1)))
        difficulty = max(1, min(5, base_diff + random.randint(-1, 1)))

        # Calculate duration with randomness around the base for the type
        duration_offset = random.randint(-duration_range // 2, duration_range // 2)
        duration_min = max(15, base_duration + duration_offset)
        duration_min = round(duration_min / 15) * 15  # Round to nearest 15 min

        # Realistic Deadlines: Bias towards 3-7 days, small chance of urgent (1-2 days)
        deadline_roll = random.random()
        if deadline_roll < 0.15: # 15% chance of urgent deadline
            days_ahead = random.uniform(0.5, 2.0) # 0.5 to 2 days
        else: # 85% chance of standard deadline
            days_ahead = random.uniform(2.5, 7.0) # 2.5 to 7 days

        deadline_dt = now + timedelta(days=days_ahead)
        # Ensure deadline is not before minimum duration
        min_end_time = now + timedelta(minutes=duration_min)
        if deadline_dt < min_end_time:
            deadline_dt = min_end_time + timedelta(hours=random.uniform(1, 6)) # Add some buffer

        deadline = deadline_dt.isoformat() # Keep as ISO string

        # Preference: Higher chance of typical preference for the type
        preference_roll = random.random()
        if preference_roll < 0.4 and typical_pref != "any": # 40% chance of type-specific pref
            preference = typical_pref
        elif preference_roll < 0.6: # 20% chance of another specific pref
            preference = random.choice(["morning", "afternoon", "evening"])
        else: # 40% chance of 'any'
            preference = "any"

        task = {
            "id": f"task-{i}",
            "name": f"{task_type} {i+1}",
            "priority": priority,
            "difficulty": difficulty,
            "duration": duration_min, # Duration in minutes
            "deadline": deadline,     # Deadline as ISO string
            "preference": preference,
        }
        tasks.append(task)

    return tasks


def generate_random_commitments(seed=None):
    """
    Generate a more realistic set of student commitments over a 7-day period.
    Includes recurring classes, meals, and some random appointments.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    commitments = []
    # day0 = get_day0() # Get the reference start datetime (Today 8am)
    now = datetime.now()
    start_of_planning_week = now.replace(hour=8, minute=0, second=0, microsecond=0)

    commitment_id_counter = 0

    # --- 1. Recurring Classes ---
    # Example: 2 classes per week
    class_schedules = [
        # BC2411: Mon/Wed 10:00 - 11:30
        {"name": "BC2411 Lecture", "days": [0, 2], "start_time": time(10, 0), "duration_min": 90},
        # MH1810: Tue/Thu 14:00 - 15:30
        {"name": "MH1810 Tutorial", "days": [1, 3], "start_time": time(14, 0), "duration_min": 90},
    ]
    for schedule in class_schedules:
        for day_offset in schedule["days"]:
            # Ensure day_offset is within the 7-day range
            if 0 <= day_offset < 7:
                class_day = start_of_planning_week + timedelta(days=day_offset)
                start_dt = datetime.combine(class_day.date(), schedule["start_time"])
                # Ensure the generated datetime is not in the past relative to 'now'
                # (Only add future or ongoing commitments)
                if start_dt >= now - timedelta(minutes=schedule['duration_min']): # Allow ongoing
                     end_dt = start_dt + timedelta(minutes=schedule["duration_min"])
                     # Check if the commitment falls within the 8am-10pm window
                     if start_dt.time() >= time(8,0) and end_dt.time() <= time(22,0):
                         commitment = {
                             "id": f"commit-{commitment_id_counter}",
                             "activity": schedule["name"],
                             "startTime": start_dt.isoformat(),
                             "endTime": end_dt.isoformat(),
                         }
                         commitments.append(commitment)
                         commitment_id_counter += 1

    # --- 2. Daily Meals (Lunch & Dinner) ---
    meal_times = [
        {"name": "Lunch", "start_hour": 12, "duration_min": 45},
        {"name": "Dinner", "start_hour": 18, "duration_min": 60},
    ]
    for day_offset in range(7): # For each day of the week
        meal_day = start_of_planning_week + timedelta(days=day_offset)
        for meal in meal_times:
             # Add slight randomness to start time (+/- 15 min)
            start_minute_offset = random.choice([-15, 0, 15])
            start_hour = meal["start_hour"]
            start_time = time(start_hour, 0) # Base time

            start_dt = datetime.combine(meal_day.date(), start_time) + timedelta(minutes=start_minute_offset)
            # Ensure the generated datetime is not in the past
            if start_dt >= now - timedelta(minutes=meal['duration_min']): # Allow ongoing
                duration = meal["duration_min"] + random.choice([-15, 0, 15])
                duration = max(30, duration) # Ensure minimum 30 min
                end_dt = start_dt + timedelta(minutes=duration)
                 # Check if the commitment falls within the 8am-10pm window
                if start_dt.time() >= time(8,0) and end_dt.time() <= time(22,0):
                    commitment = {
                        "id": f"commit-{commitment_id_counter}",
                        "activity": meal["name"],
                        "startTime": start_dt.isoformat(),
                        "endTime": end_dt.isoformat(),
                    }
                    commitments.append(commitment)
                    commitment_id_counter += 1

    # --- 3. Random Appointments/Meetings ---
    num_random_commitments = random.randint(1, 3) # 1 to 3 extra random events
    appointment_names = ["Club Meeting", "Appointment", "Social Event", "Gym Session"]
    for _ in range(num_random_commitments):
         # Random day in the next week (0-6)
        day_offset = random.randrange(0, 7)
        event_day = start_of_planning_week + timedelta(days=day_offset)

        # Random hour between 9am and 7pm (more likely for meetings)
        hour = random.randrange(9, 19)
        minute = random.choice([0, 15, 30, 45])

        # Random duration between 60min and 120 min
        duration_min = random.randrange(4, 9) * 15  # 60 to 120 min

        start_dt = event_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Ensure not in the past
        if start_dt >= now - timedelta(minutes=duration_min): # Allow ongoing
            end_dt = start_dt + timedelta(minutes=duration_min)
             # Check if the commitment falls within the 8am-10pm window
            if start_dt.time() >= time(8,0) and end_dt.time() <= time(22,0):
                commitment = {
                    "id": f"commit-{commitment_id_counter}",
                    "activity": random.choice(appointment_names),
                    "startTime": start_dt.isoformat(),
                    "endTime": end_dt.isoformat(),
                }
                commitments.append(commitment)
                commitment_id_counter += 1

    # Remove potential duplicates (e.g., if random overlaps fixed) and sort
    unique_commitments = {c['startTime']: c for c in commitments}.values()
    return sorted(list(unique_commitments), key=lambda x: x['startTime'])


def run_optimization_with_params(tasks, commitments, alpha=1.0, beta=0.1, target_completion_rate=0.7, hard_task_threshold=4, daily_limit_slots=None, time_limit_sec=30):
    """
    Run the Gurobi optimization model with the given parameters.
    Handles conversion of task/commitment formats for the solver.
    """
    # --- Initialize Day0 ---
    # This is crucial so that datetime_to_slot uses the same reference
    get_day0()

    # --- Prepare Task Data for Solver ---
    solver_tasks = []
    for t in tasks:
        # Deadline is expected as ISO string, convert to target slot
        try:
            deadline_dt = datetime.fromisoformat(t["deadline"])
            # Convert naive ISO string (local time) to slot
            deadline_slot = datetime_to_slot(deadline_dt)
            # The deadline_slot represents the *last* slot the task can *finish* in.
            # Since tasks occupy s to s+dur-1, the latest start slot 's' must satisfy
            # s + duration_slots - 1 <= deadline_slot.
            # Gurobi constraint handles this. We pass the end slot boundary.
        except (ValueError, TypeError) as e:
            print(f"Warning: Invalid deadline format for task {t['id']}: {t['deadline']}. Using default (3 days). Error: {e}")
            deadline_slot = SLOTS_PER_DAY * 3 - 1 # Default end of day 3

        duration_slots = t["duration"] // 15
        if duration_slots <= 0:
            print(f"Warning: Task {t['id']} has non-positive duration ({t['duration']} min). Skipping task.")
            continue

        task = {
            "id": t["id"],
            "name": t["name"],
            "priority": t["priority"],
            "difficulty": t["difficulty"],
            "duration_slots": duration_slots,
            "deadline_slot": deadline_slot, # Last slot index task can occupy
            "preference": t.get("preference", "any") # Ensure preference exists
        }
        solver_tasks.append(task)

    # --- Prepare Commitment Data for Solver ---
    # Convert commitment time ranges to blocked slot dictionary {slot_index: 15}
    solver_commitments = {}
    for c in commitments:
        try:
            start_dt = datetime.fromisoformat(c["startTime"])
            end_dt = datetime.fromisoformat(c["endTime"])

            # Convert datetimes to slots
            # Clamp times outside 8am-10pm window handled by datetime_to_slot
            start_slot = datetime_to_slot(start_dt)
            # The end slot needs careful handling. If a commitment ends *at* the start
            # of a slot, that slot is *not* blocked.
            # E.g., ends at 10:00, slot 8 (10:00-10:15) is free.
            # We find the slot *containing* the time just before the end time.
            end_slot_containing = datetime_to_slot(end_dt - timedelta(microseconds=1))

            # Block all slots from start_slot up to and including end_slot_containing
            for s in range(start_slot, end_slot_containing + 1):
                 # Ensure we don't block slots beyond the horizon
                if 0 <= s < TOTAL_SLOTS:
                    solver_commitments[s] = 15 # Mark slot as blocked (value 15 min)

        except (ValueError, TypeError) as e:
            print(f"Warning: Invalid datetime format for commitment {c['id']}: {c['startTime']} or {c['endTime']}. Skipping commitment. Error: {e}")
            continue


    # --- Run the Optimization ---
    result = solve_schedule_gurobi(
        solver_tasks,
        solver_commitments,
        alpha=alpha,
        beta=beta,
        target_completion_rate=target_completion_rate,
        hard_task_threshold=hard_task_threshold,
        daily_limit_slots=daily_limit_slots,
        time_limit_sec=time_limit_sec
    )

    return result
