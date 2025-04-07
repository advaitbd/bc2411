import numpy as np
# import pandas as pd # Pandas not actually used here, can be removed if desired
from datetime import datetime, timedelta, timezone # Import timezone
from pulp import (
    LpProblem, LpMaximize, LpVariable, LpBinary, LpContinuous,
    lpSum, LpStatus, PULP_CBC_CMD # Import solver if needed explicitly
)
import math # Ensure math is imported
# ------------------------------------------------------------
# CONFIG: 7 days, each day has 56 slots => 392 total slots
# Each slot = 15 minutes from 08:00 to 22:00 (exclusive end) LOCAL TIME
# ------------------------------------------------------------
SLOTS_PER_DAY = 56 # (22 - 8) hours * 4 slots/hour = 14 * 4 = 56
TOTAL_DAYS = 7
TOTAL_SLOTS = SLOTS_PER_DAY * TOTAL_DAYS  # 392

# We'll define "day 0" as "today at 08:00 local time."
# Store as naive local time. Calculations will be relative to this.
_day0_naive_local = None
def get_day0():
    global _day0_naive_local
    if _day0_naive_local is None:
        _day0_naive_local = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        print(f"Initialized DAY0 (naive local): {_day0_naive_local}")
    return _day0_naive_local

# ------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------

def slot_to_datetime(slot):
    """
    Convert a global slot index [0..TOTAL_SLOTS-1] back to a naive local datetime object.
    Represents the START time of the slot.
    """
    day0 = get_day0()
    if not (0 <= slot < TOTAL_SLOTS):
        raise ValueError(f"Slot index {slot} is out of valid range [0, {TOTAL_SLOTS-1}]")

    day_index = slot // SLOTS_PER_DAY
    slot_in_day = slot % SLOTS_PER_DAY # Slot index within the 8am-10pm window (0 to 55)

    # Calculate minutes from the start of the 8am window for that day
    total_minutes_from_8am = slot_in_day * 15

    # Calculate the target datetime by adding days and minutes to day0
    target_datetime = day0 + timedelta(days=day_index, minutes=total_minutes_from_8am)
    # print(f"slot_to_datetime({slot}) -> day={day_index}, slot_in_day={slot_in_day}, mins_from_8am={total_minutes_from_8am} -> {target_datetime}")
    return target_datetime # Returns naive local datetime

def datetime_to_slot(dt):
    """
    Convert a NAIVE LOCAL datetime object 'dt' to a global slot index [0..TOTAL_SLOTS-1].
    Clamps times outside the 7-day horizon and the daily 8am-10pm window.
    """
    day0 = get_day0()

    # --- 1. Clamp to 7-day Horizon ---
    horizon_end = day0 + timedelta(days=TOTAL_DAYS)
    if dt < day0:
        dt_clamped = day0
        # print(f"datetime_to_slot: Clamped {dt} to start of horizon {day0}")
    elif dt >= horizon_end:
         # Clamp to the *start* of the last possible slot
        dt_clamped = slot_to_datetime(TOTAL_SLOTS - 1)
        # print(f"datetime_to_slot: Clamped {dt} to end of horizon {dt_clamped}")
    else:
        dt_clamped = dt

    # --- 2. Calculate Day Index and Time within Day ---
    time_since_day0 = dt_clamped - day0
    # Use total_seconds for precision with timedelta
    total_minutes_from_day0_start = time_since_day0.total_seconds() / 60.0

    # Determine the day index relative to day0
    day_index = int(total_minutes_from_day0_start // (24 * 60))
    # Ensure day_index is valid (0 to 6) due to clamping above
    day_index = max(0, min(day_index, TOTAL_DAYS - 1))

    # Calculate the minute of the day (0 to 1439) for the clamped datetime
    # This requires getting the time component of dt_clamped
    hour = dt_clamped.hour
    minute = dt_clamped.minute
    minutes_into_day = hour * 60 + minute # Minutes from midnight of that specific day

    # --- 3. Map to 8am-10pm Window (slots 0-55 within the day) ---
    start_minute_of_window = 8 * 60  # 480
    end_minute_of_window = 22 * 60 # 1320 (Window is [8:00, 22:00) )

    if minutes_into_day < start_minute_of_window:
        # Time is before 8am on this day -> maps to slot 0 of this day
        slot_in_day = 0
        # print(f"  Time {hour:02d}:{minute:02d} is before 8am, mapping to slot_in_day 0")
    elif minutes_into_day >= end_minute_of_window:
        # Time is 10pm or later on this day -> maps to the last slot (55) of this day
        slot_in_day = SLOTS_PER_DAY - 1
        # print(f"  Time {hour:02d}:{minute:02d} is 10pm or later, mapping to slot_in_day {slot_in_day}")
    else:
        # Time is within the 8am to 10pm window
        minutes_from_8am = minutes_into_day - start_minute_of_window
        slot_in_day = int(minutes_from_8am // 15) # floor division
        # print(f"  Time {hour:02d}:{minute:02d} is within window, {minutes_from_8am} min from 8am, mapping to slot_in_day {slot_in_day}")

    # Ensure slot_in_day is valid (0 to 55)
    slot_in_day = max(0, min(slot_in_day, SLOTS_PER_DAY - 1))

    # --- 4. Calculate Global Slot ---
    global_slot = day_index * SLOTS_PER_DAY + slot_in_day
    # print(f"datetime_to_slot({dt}) -> clamped={dt_clamped}, day={day_index}, slot_in_day={slot_in_day} -> global_slot={global_slot}")

    # Final safety clamp (shouldn't be needed if logic is correct)
    return max(0, min(global_slot, TOTAL_SLOTS - 1))


# Build sets of valid slots for "morning", "afternoon", "evening"
morning_slots = []
afternoon_slots = []
evening_slots = []
for day in range(TOTAL_DAYS):
    base = day * SLOTS_PER_DAY
    # morning => 08:00..<12:00 => slots 0..15 for that day (16 slots)
    morning_slots.extend(range(base, base + 16))
    # afternoon => 12:00..<16:00 => slots 16..31 (16 slots)
    afternoon_slots.extend(range(base + 16, base + 32))
    # evening => 16:00..<22:00 => slots 32..55 (24 slots)
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
        commitments (dict): Dictionary mapping blocked GLOBAL slots to duration (15), e.g., {10: 15, ...}
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
        # Use task ID for variable naming if available, otherwise index
        task_key = tasks[i].get('id', f'task{i}').replace('-', '_').replace('.', '_') # Sanitize ID for variable name
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
        task_key = tasks[i].get('id', i)
        model += lpSum(X[(i, s)] for s in range(TOTAL_SLOTS)) == 1, f"Assign_{task_key}"

    # (b) Deadlines: Task i must finish by its deadline_slot
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"] # Use duration_slots
        dl = tasks[i]["deadline_slot"]
        task_key = tasks[i].get('id', i)
        # If a task starts at slot 's', it occupies slots s, s+1, ..., s+dur-1
        # The last slot occupied is s+dur-1. This must be <= deadline_slot (dl).
        # So, if s + dur - 1 > dl, then X[(i, s)] must be 0.
        for s in range(TOTAL_SLOTS):
            if s + dur - 1 > dl:
                # Also ensure the task can even start (s < TOTAL_SLOTS)
                # This constraint prevents starting too late to meet the deadline
                 model += (X[(i, s)] == 0), f"Deadline_{task_key}_s{s}"
            # Add constraint: task must start early enough to fit within total slots
            if s + dur > TOTAL_SLOTS:
                 model += (X[(i, s)] == 0), f"HorizonEnd_{task_key}_s{s}"


    # (c) No Overlap: At most one task can *occupy* any given slot t
    for t in range(TOTAL_SLOTS):
        # Identify all (task_i, start_slot_s) pairs that would result in task i occupying slot t
        occupying_tasks_vars = []
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            # Task i occupies slot t if it starts in any slot 's' such that s <= t < s + dur
            # Iterate through possible start slots 's' that could cover slot 't'
            # The earliest start slot 's' that covers 't' is t - dur + 1
            # The latest start slot 's' that covers 't' is t
            for s in range(max(0, t - dur + 1), t + 1):
                 # Check if s is a valid start slot index for *this* task
                 # (considering horizon end constraint from (b))
                 if s + dur <= TOTAL_SLOTS:
                     occupying_tasks_vars.append(X[(i, s)])

        # The sum of X variables for tasks occupying slot t must be <= 1
        if occupying_tasks_vars:
             model += lpSum(occupying_tasks_vars) <= 1, f"NoOverlap_s{t}"

    # (d) Preferences: Task i can only start in a slot matching its preference
    for i in range(n_tasks):
        pref = tasks[i].get("preference", "any")
        task_key = tasks[i].get('id', i)
        if pref not in PREFERENCE_MAP:
             print(f"Warning: Invalid preference '{pref}' for task {task_key}. Defaulting to 'any'.")
             pref = "any"
        allowed_slots = PREFERENCE_MAP.get(pref, PREFERENCE_MAP["any"]) # Fallback to 'any'

        # Constrain start slot based on preference
        for s in range(TOTAL_SLOTS):
            if s not in allowed_slots:
                model += X[(i, s)] == 0, f"PrefWin_{task_key}_s{s}"

    # (e) Commitments: No task can start if it would overlap with a committed slot
    committed_slots = set(commitments.keys())
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"]
        task_key = tasks[i].get('id', i)
        for s in range(TOTAL_SLOTS):
             # Check if any slot the task *would* occupy (s to s+dur-1) is committed
             task_occupies = set(range(s, s + dur))
             # Ensure task_occupies doesn't go beyond TOTAL_SLOTS
             task_occupies = {slot for slot in task_occupies if slot < TOTAL_SLOTS}

             if task_occupies.intersection(committed_slots):
                 # If there's an overlap, this task cannot start at slot s
                 model += X[(i, s)] == 0, f"CommitOverlap_{task_key}_s{s}"


    # (f) Leisure Calculation: Link L_var with Y (task occupation) and commitments
    for s in range(TOTAL_SLOTS):
        # Determine if slot 's' is occupied by *any* task starting earlier
        occupying_task_vars = []
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            # Task i occupies slot s if it starts in range [s - dur + 1, s]
            for start_slot in range(max(0, s - dur + 1), s + 1):
                 if start_slot + dur <= TOTAL_SLOTS: # Ensure task fits if started here
                     occupying_task_vars.append(X[(i, start_slot)])

        # Y[s] = 1 if occupied by a task, 0 otherwise
        if occupying_task_vars:
             # Using Big M method approximation (less strict but often works):
             # M * Y[s] >= sum(X) => If sum(X)>=1, Y[s] must be >= 1/M (so Y=1)
             # Y[s] <= sum(X)    => If sum(X)=0, Y[s] <= 0 (so Y=0). If sum(X)=1, Y[s]<=1.
             # M should be at least the maximum possible value of sum(X), which is 1 here. Let's use M=1.
             # model += Y[s] >= lpSum(occupying_task_vars), f"Link_Y_Lower_{s}" # Y[s] >= sum(X)
             # model += Y[s] <= lpSum(occupying_task_vars), f"Link_Y_Upper_{s}" # Y[s] <= sum(X)
             # This forces Y[s] = sum(X). Since sum(X) can only be 0 or 1 (due to NoOverlap constraint), this works.
             model += Y[s] == lpSum(occupying_task_vars), f"Link_Y_Exact_{s}"

        else:
             # If no task can possibly occupy this slot, Y[s] must be 0
             model += Y[s] == 0, f"Force_Y_zero_{s}"

        # Calculate leisure based on commitment and task occupation (Y)
        is_committed = 1 if s in commitments else 0

        # Leisure L[s] = 15 if slot 's' is NOT committed AND NOT occupied by a task (Y[s]=0)
        # Leisure L[s] = 0 otherwise
        # We express this using the definition: L[s] <= 15 * (1 - Y[s]) * (1 - is_committed)
        # Since is_committed is a constant 0 or 1 for each s:
        if is_committed:
             model += L_var[s] == 0, f"NoLeisure_Committed_{s}"
        else: # Slot is not committed
             # L_var[s] can be at most 15 if Y[s] is 0, and 0 if Y[s] is 1.
             model += L_var[s] <= 15 * (1 - Y[s]), f"LeisureBound_NotCommitted_{s}"


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
        solver = PULP_CBC_CMD(msg=0, timeLimit=30) # Add a time limit (e.g., 30 seconds)
        status = model.solve(solver)
        solve_time = model.solutionTime
        print(f"Solver status: {LpStatus[status]} (solved in {solve_time:.2f}s)")
    except Exception as e:
        print(f"Error during PuLP solve: {e}")
        return {'status': 'Error', 'message': f"Solver failed: {e}"}

    # --- Process Results ---
    # Note: Even if 'Optimal', check variable values carefully, floating point issues can occur.
    solution_threshold = 0.9 # Consider a variable > 0.9 as selected (1)

    if LpStatus[status] in ["Optimal", "Feasible"]: # Accept Feasible solutions too
        print("Solver: Solution found!")
        schedule_records = []

        for i in range(n_tasks):
            task_scheduled = False
            for s in range(TOTAL_SLOTS):
                # Check if the variable exists and its value is close to 1
                if (i, s) in X and X[(i, s)].varValue is not None and X[(i, s)].varValue > solution_threshold:
                    start_slot = s
                    dur_slots = tasks[i]["duration_slots"]
                    end_slot = s + dur_slots - 1 # Last slot *index* occupied

                     # Double-check bounds
                    if end_slot >= TOTAL_SLOTS:
                         print(f"Warning: Task {tasks[i]['id']} starts at {s} but end_slot {end_slot} exceeds limit {TOTAL_SLOTS-1}. Skipping.")
                         continue # Should be prevented by constraints, but safety check

                    start_dt = slot_to_datetime(start_slot) # Naive local
                    # End time is the start time of the slot *after* the last occupied slot
                    # Check if the next slot exists
                    if end_slot + 1 < TOTAL_SLOTS:
                         end_dt = slot_to_datetime(end_slot + 1) # Naive local
                    else:
                         # If it ends in the very last slot, the end time is the start of that slot + 15 mins
                         end_dt = slot_to_datetime(end_slot) + timedelta(minutes=15) # Naive local

                    record = {
                        "id": tasks[i].get('id', f"task-result-{i}"), # Use original task ID
                        "name": tasks[i]["name"],
                        "priority": tasks[i]["priority"],
                        "difficulty": tasks[i]["difficulty"],
                        "start_slot": start_slot,
                        "end_slot": end_slot,
                        # Return ISO format string WITHOUT timezone indicator 'Z'
                        "startTime": start_dt.isoformat(),
                        "endTime": end_dt.isoformat(),
                        "duration_min": dur_slots * 15,
                        "preference": tasks[i].get("preference", "any")
                    }
                    schedule_records.append(record)
                    task_scheduled = True
                    break # Move to next task once start slot is found

            if not task_scheduled and LpStatus[status] == "Optimal":
                 # If Optimal, every task should have been scheduled due to constraint (a)
                 print(f"ERROR: Task {i} ('{tasks[i]['name']}') appears unscheduled despite Optimal status! Check solver output/constraints.")
                 # Potentially return an error here or a specific status


        schedule_records.sort(key=lambda x: x["start_slot"])

        # Calculate total leisure from L_var values
        total_leisure_val = sum(L_var[s].varValue for s in range(TOTAL_SLOTS) if L_var[s].varValue is not None)

        # Recalculate total stress based on the objective function's stress component value
        stress_component_value = sum(X[(i, s)].varValue * (tasks[i]["priority"] * tasks[i]["difficulty"])
                                     for i in range(n_tasks) for s in range(TOTAL_SLOTS)
                                     if (i, s) in X and X[(i, s)].varValue is not None and X[(i, s)].varValue > solution_threshold)
        calculated_stress = stress_component_value

        print(f"Solver: Calculated Total Leisure = {total_leisure_val:.1f} minutes")
        print(f"Solver: Calculated Total Stress Score = {calculated_stress:.1f}")

        final_status = LpStatus[status]
        if LpStatus[status] == "Optimal" and not all(
             any(X[(i, s)].varValue > solution_threshold for s in range(TOTAL_SLOTS) if (i,s) in X and X[(i,s)].varValue is not None) for i in range(n_tasks)
             ):
             print("WARNING: Optimal status reported but not all tasks seem scheduled based on variable values > 0.9. Reporting as Feasible.")
             final_status = "Feasible" # Downgrade status if inconsistency found


        return {
            "status": final_status,
            "schedule": schedule_records,
            "total_leisure": round(total_leisure_val, 1),
            "total_stress": round(calculated_stress, 1),
            "solve_time_seconds": round(solve_time, 2)
        }
    elif LpStatus[status] == "Infeasible":
        print("Solver: Model is infeasible.")
        # Try to find conflicting constraints (requires more advanced analysis, maybe uncommenting model.writeLP())
        # model.writeLP("infeasible_schedule_model.lp")
        # print("Wrote LP file for infeasible model to infeasible_schedule_model.lp")
        return {"status": "Infeasible", "schedule": [], "message": "Could not find a feasible schedule. Check constraints: deadlines too tight? Too many commitments or tasks for available time? Daily limits too strict?"}
    elif LpStatus[status] == "Not Solved":
         print(f"Solver: Not Solved. Might be due to time limit ({solver.timeLimit}s?) or other issues.")
         return {"status": "Not Solved", "schedule": [], "message": f"Solver did not find a solution, possibly due to time limits or complexity."}
    else:
        print(f"Solver finished with unhandled status: {LpStatus[status]}")
        return {"status": LpStatus[status], "schedule": [], "message": f"Solver finished with status: {LpStatus[status]}."}
