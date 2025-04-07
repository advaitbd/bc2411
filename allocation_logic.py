import numpy as np
# import pandas as pd # Pandas not actually used here, can be removed if desired
from datetime import datetime, timedelta
from pulp import (
    LpProblem, LpMaximize, LpVariable, LpBinary, LpContinuous,
    lpSum, LpStatus, PULP_CBC_CMD # Import solver if needed explicitly
)
import math # Ensure math is imported
# ------------------------------------------------------------
# CONFIG: 7 days, each day has 56 slots => 392 total slots
# Each slot = 15 minutes from 08:00 to 22:00
# ------------------------------------------------------------
SLOTS_PER_DAY = 56 # 14 hours * 4 slots/hour
TOTAL_DAYS = 7
TOTAL_SLOTS = SLOTS_PER_DAY * TOTAL_DAYS  # 392

# We'll define "day 0" as "today at 08:00 local time."
# Ensure DAY0 calculation happens when the module is loaded or appropriately passed
_day0 = None
def get_day0():
    global _day0
    if _day0 is None:
        _day0 = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    return _day0

# ------------------------------------------------------------
# HELPER FUNCTIONS (Adapted from test.py)
# ------------------------------------------------------------

def slot_to_datetime(slot):
    """
    Convert a slot [0..TOTAL_SLOTS-1] back to a datetime object.
    """
    day0 = get_day0()
    if not (0 <= slot < TOTAL_SLOTS):
        # Handle invalid slot index, maybe return None or raise error
        raise ValueError(f"Slot index {slot} is out of valid range [0, {TOTAL_SLOTS-1}]")

    day_index = slot // SLOTS_PER_DAY
    slot_in_day = slot % SLOTS_PER_DAY

    # Calculate hours and minutes from the start of the 8am window
    total_minutes_from_8am = slot_in_day * 15
    hours_from_8am = total_minutes_from_8am // 60
    minutes_remainder = total_minutes_from_8am % 60

    # Actual hour of the day (8am is base)
    hour_of_day = 8 + hours_from_8am
    minute_of_hour = minutes_remainder

    # Combine with the base date (day0) plus the day index
    target_datetime = day0 + timedelta(days=day_index, hours=hour_of_day, minutes=minute_of_hour)
    return target_datetime

def clamp_to_7day_horizon(dt):
    """
    Clamp dt to be within [DAY0, DAY0 + 7 days].
    If dt < DAY0, set dt = DAY0.
    If dt > DAY0+7 days, set dt = day0+7 days (end of last slot).
    """
    day0 = get_day0()
    if dt < day0:
        return day0
    limit = day0 + timedelta(days=TOTAL_DAYS)
    # Check if it's on or after the start of the day *after* the horizon
    if dt >= limit:
        # Return the very last possible time slot's start time
        return slot_to_datetime(TOTAL_SLOTS - 1)
    return dt

def datetime_to_slot(dt):
    """
    Convert dt to a slot index in [0..TOTAL_SLOTS-1], each slot = 15 minutes
    from 08:00 to 22:00 over 7 days relative to DAY0.
    Clamps times outside 8am-10pm to the nearest valid slot boundary for that day.
    """
    day0 = get_day0()
    dt_clamped_horizon = clamp_to_7day_horizon(dt) # Ensure it's within the 7-day overall range

    delta = dt_clamped_horizon - day0
    total_minutes_from_day0 = delta.total_seconds() / 60

    # Day index (0 to 6)
    day_index = int(total_minutes_from_day0 // (24 * 60))
    # Should be safe due to clamp_to_7day_horizon, but double check
    day_index = max(0, min(day_index, TOTAL_DAYS - 1))

    # Calculate minutes *within the start of the specific day* (midnight)
    minutes_into_day = total_minutes_from_day0 % (24 * 60)

    # Map these minutes to the 8am-10pm window (480 to 1320 minutes from midnight)
    # 8am = 480 mins from midnight
    # 10pm = 1320 mins from midnight (exclusive end)
    start_minute_of_window = 8 * 60
    end_minute_of_window = 22 * 60 # Window ends *before* 10pm

    if minutes_into_day < start_minute_of_window:
         # Before 8am on that day? Treat as the first slot (0) of that day's window
         minutes_in_window = 0
    elif minutes_into_day >= end_minute_of_window:
         # At or after 10pm on that day? Treat as the last slot (55) of that day's window
         # The effective time for the last slot is 21:45, total minutes = 14*60 - 15
         minutes_in_window = (SLOTS_PER_DAY - 1) * 15 # minutes corresponding to the start of the last slot
    else:
         # Within the 8am-10pm window
         minutes_in_window = minutes_into_day - start_minute_of_window

    # Calculate the slot index within the day (0 to 55)
    slot_in_day = int(minutes_in_window // 15)
    slot_in_day = max(0, min(slot_in_day, SLOTS_PER_DAY - 1)) # Clamp within day

    # Calculate the global slot index
    global_slot = day_index * SLOTS_PER_DAY + slot_in_day

    # Final clamping to ensure it's within the valid range [0, TOTAL_SLOTS - 1]
    return max(0, min(global_slot, TOTAL_SLOTS - 1))


# Build sets of valid slots for "morning", "afternoon", "evening"
morning_slots = []
afternoon_slots = []
evening_slots = []
for day in range(TOTAL_DAYS):
    base = day * SLOTS_PER_DAY
    # morning => 08:00..<12:00 => slots 0..15 for that day
    morning_slots.extend(range(base, base + 16))
    # afternoon => 12:00..<16:00 => slots 16..31
    afternoon_slots.extend(range(base + 16, base + 32))
    # evening => 16:00..<22:00 => slots 32..55
    evening_slots.extend(range(base + 32, base + SLOTS_PER_DAY)) # up to 56 exclusive

PREFERENCE_MAP = {
    "any": set(range(TOTAL_SLOTS)), # Allow any slot if preference is 'any'
    "morning": set(morning_slots),
    "afternoon": set(afternoon_slots),
    "evening": set(evening_slots)
}

# ------------------------------------------------------------
# MAIN SCHEDULER FUNCTION
# ------------------------------------------------------------

def solve_schedule_pulp(tasks, commitments, alpha=1.0, beta=0.1, daily_limit_slots=None):
    """
    Solves the scheduling problem using PuLP.

    Args:
        tasks (list): List of task dictionaries, e.g.,
            [{'id': '...', 'name': 'Task 1', 'priority': 5, 'difficulty': 3, 'duration_slots': 4,
              'deadline_slot': 100, 'preference': 'morning'}, ...]
        commitments (dict): Dictionary mapping blocked slots to duration (15), e.g., {10: 15, ...}
        alpha (float): Weight for maximizing leisure time.
        beta (float): Weight for minimizing stress.
        daily_limit_slots (int, optional): Maximum number of task slots allowed per day.

    Returns:
        dict: Optimization status and results.
    """
    print(f"Solver received {len(tasks)} tasks.")
    print(f"Solver received {len(commitments)} commitment slots.")
    print(f"Solver params: Alpha={alpha}, Beta={beta}, DailyLimitSlots={daily_limit_slots}")

    n_tasks = len(tasks)
    if n_tasks == 0:
        print("Solver: No tasks to schedule.")
        total_possible_minutes = TOTAL_SLOTS * 15
        committed_minutes = len(commitments) * 15
        initial_leisure = total_possible_minutes - committed_minutes
        return {'status': 'Optimal', 'schedule': [], 'total_leisure': initial_leisure, 'total_stress': 0.0, 'message': 'No tasks provided.'}

    model = LpProblem("Weekly_Scheduler", LpMaximize)

    # --- Decision variables ---
    # X[i, s] = 1 if task i starts at slot s, 0 otherwise
    X = {}
    for i in range(n_tasks):
        task_key = tasks[i].get('id', f'task{i}')
        for s in range(TOTAL_SLOTS):
            X[(i, s)] = LpVariable(f"X_{task_key}_s{s}", cat=LpBinary)

    # Y[s] = 1 if slot s is occupied by *any* task, 0 otherwise
    Y = {s: LpVariable(f"Y_s{s}", cat=LpBinary) for s in range(TOTAL_SLOTS)}
    # L_var[s] = amount of leisure time (in minutes) in slot s
    L_var = {s: LpVariable(f"L_s{s}", lowBound=0, upBound=15, cat=LpContinuous) for s in range(TOTAL_SLOTS)}

    # --- Objective Function ---
    # Maximize leisure, minimize stress (weighted sum of priority*difficulty for scheduled tasks)
    # Note: The stress part uses the X variable directly, summing over all *possible* start slots.
    # If X[i, s] = 1, the task starts at s, and its stress contribution is counted once.
    model += (
        alpha * lpSum(L_var[s] for s in range(TOTAL_SLOTS))
        - beta * lpSum(X[(i, s)] * (tasks[i]["priority"] * tasks[i]["difficulty"])
                       for i in range(n_tasks) for s in range(TOTAL_SLOTS))
    ), "Maximize_Leisure_Minus_Stress"

    # --- Constraints ---
    # (a) Each task assigned exactly one starting slot
    for i in range(n_tasks):
        model += lpSum(X[(i, s)] for s in range(TOTAL_SLOTS)) == 1, f"Assign_{tasks[i].get('id', i)}"

    # (b) Deadlines: Task i must finish by its deadline_slot
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"] # Use duration_slots
        dl = tasks[i]["deadline_slot"]
        # If a task starts at slot 's', it occupies slots s, s+1, ..., s+dur-1
        # The last slot occupied is s+dur-1. This must be <= deadline_slot (dl).
        # So, if s + dur - 1 > dl, then X[(i, s)] must be 0.
        for s in range(TOTAL_SLOTS):
            if s + dur - 1 > dl:
                model += (X[(i, s)] == 0), f"Deadline_{tasks[i].get('id', i)}_s{s}"

    # (c) No Overlap: At most one task can *occupy* any given slot t
    for t in range(TOTAL_SLOTS):
        # Identify all (task_i, start_slot_s) pairs that would result in task i occupying slot t
        occupying_tasks_vars = []
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            # Task i occupies slot t if it starts in any slot 's' such that s <= t < s + dur
            # Iterate through possible start slots 's' that could cover slot 't'
            for s in range(max(0, t - dur + 1), t + 1):
                 # Check if s is a valid start slot index and if starting at s covers t
                 if s < TOTAL_SLOTS: # Ensure start slot is valid
                     # Condition s <= t < s + dur is implicitly handled by the loop range
                     occupying_tasks_vars.append(X[(i, s)])

        # The sum of X variables for tasks occupying slot t must be <= 1
        if occupying_tasks_vars:
             model += lpSum(occupying_tasks_vars) <= 1, f"NoOverlap_s{t}"

    # (d) Preferences: Task i can only start in a slot matching its preference
    for i in range(n_tasks):
        pref = tasks[i].get("preference", "any")
        if pref not in PREFERENCE_MAP:
             print(f"Warning: Invalid preference '{pref}' for task {tasks[i]['name']}. Defaulting to 'any'.")
             pref = "any"
        allowed_slots = PREFERENCE_MAP.get(pref, PREFERENCE_MAP["any"]) # Fallback to 'any'

        # Constrain start slot based on preference
        for s in range(TOTAL_SLOTS):
            if s not in allowed_slots:
                model += X[(i, s)] == 0, f"PrefWin_{tasks[i].get('id', i)}_s{s}"

    # (e) Commitments: No task can start if it would overlap with a committed slot
    committed_slots = set(commitments.keys())
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"]
        task_key = tasks[i].get('id', i)
        for s in range(TOTAL_SLOTS):
             # Check if any slot the task *would* occupy (s to s+dur-1) is committed
             task_occupies = set(range(s, s + dur))
             if task_occupies.intersection(committed_slots):
                 # If there's an overlap, this task cannot start at slot s
                 model += X[(i, s)] == 0, f"CommitOverlap_{task_key}_s{s}"

    # (f) Leisure Calculation: Link L_var with Y (task occupation) and commitments
    for s in range(TOTAL_SLOTS):
        # Determine if slot 's' is occupied by *any* task starting earlier
        occupying_task_vars = []
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            for start_slot in range(max(0, s - dur + 1), s + 1):
                 if start_slot < TOTAL_SLOTS:
                    occupying_task_vars.append(X[(i, start_slot)])

        # Y[s] = 1 if occupied by a task, 0 otherwise
        if occupying_task_vars:
             # Using Big M method: Y[s] >= sum(X)/M is not correct for binary Y.
             # Instead, Y[s] = 1 if sum(X) >= 1.
             # Constraint: Y[s] >= X[i, start] for all relevant i, start
             # Constraint: Y[s] <= sum(X[i, start])
             for x_var in occupying_task_vars:
                 model += Y[s] >= x_var, f"Link_Y_Lower_{s}_{x_var.name.replace('X_','')}"
             model += Y[s] <= lpSum(occupying_task_vars), f"Link_Y_Upper_{s}"
        else:
             # If no task can possibly occupy this slot, Y[s] must be 0
             model += Y[s] == 0, f"Force_Y_zero_{s}"

        # Calculate leisure based on commitment and task occupation (Y)
        is_committed = 1 if s in commitments else 0
        available_minutes = 15 * (1 - is_committed) # 15 if not committed, 0 if committed

        if available_minutes <= 0:
            # If slot is committed, leisure must be 0
            model += L_var[s] == 0, f"NoLeisure_Committed_{s}"
        else:
            # If slot is NOT committed (available_minutes = 15):
            # Leisure L[s] can be at most 15 * (1 - Y[s])
            # If Y[s] = 1 (task occupies), L[s] <= 0
            # If Y[s] = 0 (no task), L[s] <= 15
            model += L_var[s] <= available_minutes * (1 - Y[s]), f"LeisureBound_{s}"


    # (g) Daily Limits (Optional)
    if daily_limit_slots is not None and daily_limit_slots >= 0:
         print(f"Applying daily limit of {daily_limit_slots} slots ({daily_limit_slots * 15} minutes)")
         for d in range(TOTAL_DAYS):
             day_start_slot = d * SLOTS_PER_DAY
             day_end_slot = day_start_slot + SLOTS_PER_DAY

             # Sum of Y[s] (slots occupied by *any* task) for the day
             daily_task_slots_sum = lpSum(Y[s] for s in range(day_start_slot, day_end_slot))
             model += daily_task_slots_sum <= daily_limit_slots, f"DailyLimit_Day_{d}"
             print(f"  Constraint Day {d}: sum(Y[{day_start_slot}...{day_end_slot-1}]) <= {daily_limit_slots}")

    # --- Solve ---
    print("Solver: Solving the model...")
    try:
        # Use default CBC solver, increase verbosity (msg=1) for debugging if needed
        solver = PULP_CBC_CMD(msg=0) # Set msg=0 for less output
        status = model.solve(solver)
        solve_time = model.solutionTime
        print(f"Solver status: {LpStatus[status]} (solved in {solve_time:.2f}s)")
    except Exception as e:
        print(f"Error during PuLP solve: {e}")
        return {'status': 'Error', 'message': f"Solver failed: {e}"}

    # --- Process Results ---
    if LpStatus[status] == "Optimal" or LpStatus[status] == "Feasible":
        print("Solver: Solution found!")
        schedule_records = []
        # scheduled_tasks_details = {} # No longer needed for stress calculation

        for i in range(n_tasks):
            task_scheduled = False
            for s in range(TOTAL_SLOTS):
                if X[(i, s)].varValue is not None and X[(i, s)].varValue > 0.5:
                    start_slot = s
                    dur_slots = tasks[i]["duration_slots"]
                    end_slot = s + dur_slots - 1 # Last slot *index* occupied
                    start_dt = slot_to_datetime(start_slot)
                    # End time is the start time of the slot *after* the last occupied slot
                    end_dt = slot_to_datetime(end_slot) + timedelta(minutes=15)

                    record = {
                        "id": tasks[i].get('id', f"task-result-{i}"), # Use original task ID
                        "name": tasks[i]["name"],
                        "priority": tasks[i]["priority"],
                        "difficulty": tasks[i]["difficulty"],
                        "start_slot": start_slot,
                        "end_slot": end_slot,
                        "startTime": start_dt.isoformat() + "Z",
                        "endTime": end_dt.isoformat() + "Z",
                        "duration_min": dur_slots * 15,
                        "preference": tasks[i].get("preference", "any")
                    }
                    schedule_records.append(record)
                    # scheduled_tasks_details[i] = {...} # Not needed
                    task_scheduled = True
                    break # Move to next task once start slot is found
            if not task_scheduled:
                 # This case should ideally not happen if status is Optimal/Feasible and constraint (a) holds
                 print(f"Warning: Task {i} ('{tasks[i]['name']}') appears unscheduled despite {LpStatus[status]} status.")

        schedule_records.sort(key=lambda x: x["start_slot"])

        # Calculate total leisure from L_var values
        total_leisure_val = sum(L_var[s].varValue for s in range(TOTAL_SLOTS) if L_var[s].varValue is not None)

        # Recalculate total stress based on the objective function's stress component value
        # This ensures consistency with what the solver optimized
        stress_component_value = sum(X[(i, s)].varValue * (tasks[i]["priority"] * tasks[i]["difficulty"])
                                     for i in range(n_tasks) for s in range(TOTAL_SLOTS)
                                     if X[(i, s)].varValue is not None) # Sum contributions from tasks that were scheduled (X=1)
        calculated_stress = stress_component_value # This is the total stress score


        print(f"Solver: Calculated Total Leisure = {total_leisure_val:.1f} minutes")
        print(f"Solver: Calculated Total Stress Score = {calculated_stress:.1f}")

        return {
            "status": LpStatus[status],
            "schedule": schedule_records,
            "total_leisure": round(total_leisure_val, 1),
            "total_stress": round(calculated_stress, 1),
            "solve_time_seconds": round(solve_time, 2)
        }
    elif LpStatus[status] == "Infeasible":
        print("Solver: Model is infeasible.")
        return {"status": "Infeasible", "message": "Could not find a feasible schedule. Check constraints: deadlines too tight? Too many commitments or tasks for available time? Daily limits too strict?"}
    else:
        print(f"Solver finished with status: {LpStatus[status]}")
        return {"status": LpStatus[status], "message": f"Solver finished with status: {LpStatus[status]}."}
