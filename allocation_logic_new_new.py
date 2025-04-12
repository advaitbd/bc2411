# bc2411/allocation_logic_new_copy.py
import numpy as np
from datetime import datetime, timedelta, timezone
import math
import traceback # Keep for potential debugging in helpers
# --- Import Gurobi ---
import gurobipy as gp
from gurobipy import GRB

# ------------------------------------------------------------
# CONFIG (Now mostly dynamic, TOTAL_DAYS is fixed)
# ------------------------------------------------------------
TOTAL_DAYS = 7

# --- Global Day 0 Reference ---
# We still need a reference point, but the *hour* will be dynamic.
# Initialize lazily.
_day0_naive_local_ref_midnight = None

def get_day0_ref_midnight():
    """Returns the date of Day 0 at midnight, naive local."""
    global _day0_naive_local_ref_midnight
    if _day0_naive_local_ref_midnight is None:
        now = datetime.now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        _day0_naive_local_ref_midnight = start_of_today
        # print(f"Initialized DAY0 Reference Midnight (naive local): {_day0_naive_local_ref_midnight}") # Keep quiet
    return _day0_naive_local_ref_midnight

# ------------------------------------------------------------
# HELPER FUNCTIONS (Modified for Dynamic Hours)
# ------------------------------------------------------------

def calculate_dynamic_config(start_hour, end_hour):
    """Calculates slots_per_day and total_slots based on hours."""
    if not (0 <= start_hour < 24 and 0 < end_hour <= 24 and start_hour < end_hour):
        raise ValueError(f"Invalid start/end hours: {start_hour}-{end_hour}. Must be 0 <= start < end <= 24.")
    slots_per_day = (end_hour - start_hour) * 4
    total_slots = slots_per_day * TOTAL_DAYS
    if total_slots < 0: # Should be prevented by start < end check, but safety
        total_slots = 0
    if slots_per_day < 0:
        slots_per_day = 0
    return slots_per_day, total_slots

def slot_to_datetime(slot, start_hour, slots_per_day, total_slots):
    """
    Convert a global slot index [0..total_slots-1] back to a naive local datetime object.
    Represents the START time of the slot, based on dynamic hours.
    Also handles slot == total_slots to represent the end of the schedule.
    """
    day0_ref_midnight = get_day0_ref_midnight()
    day0_actual_start = day0_ref_midnight.replace(hour=start_hour, minute=0)

    # Handle edge case: No slots available
    if total_slots <= 0:
         if slot == 0: # Requesting time for slot 0 when none exist
             return day0_actual_start # Return the intended start time
         else:
            raise ValueError(f"Slot index {slot} requested but total_slots is {total_slots}")


    if not (0 <= slot <= total_slots): # Allow slot == total_slots for end time calculation
        raise ValueError(f"Slot index {slot} is out of valid range [0, {total_slots}] for {slots_per_day} slots/day")

    # If slot is exactly total_slots, it represents the end time of the last slot
    if slot == total_slots:
        # Calculate the time corresponding to the start of the slot *after* the last one
        # This is equivalent to adding TOTAL_DAYS to the actual start time of day 0
        return day0_actual_start + timedelta(days=TOTAL_DAYS)

    # Proceed for valid slots 0 to total_slots - 1
    if slots_per_day <= 0: # Should not happen if total_slots > 0, but safety
        raise ValueError("slots_per_day is zero or negative, cannot calculate slot time.")

    day_index = slot // slots_per_day
    slot_in_day = slot % slots_per_day # Slot index within the start_hour to end_hour window

    # Calculate minutes from the start_hour for that day
    total_minutes_from_start_hour = slot_in_day * 15

    # Calculate the target datetime by adding days and minutes to the actual day 0 start time
    target_datetime = day0_actual_start + timedelta(days=day_index, minutes=total_minutes_from_start_hour)
    return target_datetime # Returns naive local datetime

def datetime_to_slot(dt, start_hour, end_hour, slots_per_day, total_slots):
    """
    Convert a NAIVE LOCAL datetime object 'dt' to a global slot index [0..total_slots-1].
    Clamps times outside the 7-day horizon and the daily start_hour-end_hour window.
    Returns the index of the slot *containing* the datetime dt.
    """
    day0_ref_midnight = get_day0_ref_midnight()
    day0_actual_start = day0_ref_midnight.replace(hour=start_hour, minute=0)

    # Handle edge case: No slots available
    if total_slots <= 0:
        return 0 # Map everything to slot 0 if no slots exist

    # --- 1. Clamp to 7-day Horizon ---
    horizon_end = day0_actual_start + timedelta(days=TOTAL_DAYS) # This is start_hour on day 7 (exclusive boundary)

    # Determine the start time of the very last slot
    last_slot_index = total_slots - 1
    last_slot_start_dt = slot_to_datetime(last_slot_index, start_hour, slots_per_day, total_slots)
    # Determine the end time of the very last slot
    last_slot_end_dt = slot_to_datetime(total_slots, start_hour, slots_per_day, total_slots)


    if dt < day0_actual_start:
        dt_clamped = day0_actual_start # Clamp to beginning of horizon
    elif dt >= horizon_end:
        # If dt is exactly or after the end horizon, map it to the last slot index
        dt_clamped = last_slot_start_dt # Assign to the start of the last possible slot
    else:
        dt_clamped = dt

    # --- 2. Calculate Day Index and Time within Day ---
    # Use clamped time relative to the actual start of the scheduling window on day 0
    time_since_day0_schedule_start = dt_clamped - day0_actual_start
    total_minutes_since_schedule_start = time_since_day0_schedule_start.total_seconds() / 60.0

    if total_minutes_since_schedule_start < 0: # Should be handled by clamping, but safety
        total_minutes_since_schedule_start = 0

    # Day index relative to the start of scheduling
    day_index = int(total_minutes_since_schedule_start // (24 * 60))
    # Ensure day index is within the allowed range [0, TOTAL_DAYS - 1]
    day_index = max(0, min(day_index, TOTAL_DAYS - 1))

    # Time within the specific day (00:00 to 23:59)
    hour = dt_clamped.hour
    minute = dt_clamped.minute
    minutes_into_day_from_midnight = hour * 60 + minute

    # --- 3. Map to start_hour - end_hour Window ---
    start_minute_of_window = start_hour * 60
    # End minute is exclusive boundary (e.g., if end_hour=22, window is up to 21:59:59)
    end_minute_of_window = end_hour * 60

    if minutes_into_day_from_midnight < start_minute_of_window:
        # Time is before the window starts on this day, map to first slot of the day
        slot_in_day = 0
    elif minutes_into_day_from_midnight >= end_minute_of_window:
        # Time is at or after the window ends, map to last slot of the day
        slot_in_day = slots_per_day - 1
    else:
        # Time is within the window
        minutes_from_window_start = minutes_into_day_from_midnight - start_minute_of_window
        slot_in_day = int(minutes_from_window_start // 15) # Integer division gives slot index

    # Ensure slot_in_day is valid (handles slots_per_day=0 case implicitly covered by total_slots=0 check earlier)
    slot_in_day = max(0, min(slot_in_day, slots_per_day - 1))


    # --- 4. Calculate Global Slot ---
    global_slot = day_index * slots_per_day + slot_in_day

    # Final clamping to the overall range [0, total_slots - 1]
    return max(0, min(global_slot, total_slots - 1))


# ------------------------------------------------------------
# DEFAULT WEIGHT/MULTIPLIER GENERATION
# ------------------------------------------------------------

def generate_default_leisure_weights(total_slots, start_hour, slots_per_day):
    """Generates default leisure weights: higher value for evenings (6 PM onwards)."""
    weights = {}
    if total_slots == 0: return weights
    for s in range(total_slots):
        try:
            dt = slot_to_datetime(s, start_hour, slots_per_day, total_slots)
            if dt.hour >= 18: # 6 PM or later
                weights[s] = 1.5
            else:
                weights[s] = 1.0
        except ValueError:
            weights[s] = 1.0 # Default if slot conversion fails
    return weights

def generate_default_stress_multipliers(total_slots, start_hour, slots_per_day):
    """Generates default stress multipliers: higher during core hours (9 AM - 5 PM)."""
    multipliers = {}
    if total_slots == 0: return multipliers
    for s in range(total_slots):
        try:
            dt = slot_to_datetime(s, start_hour, slots_per_day, total_slots)
            # Core hours: 9:00 AM up to (but not including) 5:00 PM
            if 9 <= dt.hour < 17:
                multipliers[s] = 1.2
            else:
                multipliers[s] = 1.0
        except ValueError:
             multipliers[s] = 1.0 # Default if slot conversion fails
    return multipliers


# ------------------------------------------------------------
# GUROBI SCHEDULER FUNCTION (MODIFIED FOR CONTEXTUAL LEISURE/STRESS & CONTIGUITY)
# ------------------------------------------------------------

def solve_schedule_gurobi(tasks, commitments, alpha=1.0, beta=0.1, gamma=0.05,
                          daily_limit_slots=None, time_limit_sec=30,
                          hard_task_threshold=4, start_hour=8, end_hour=22,
                          leisure_slot_weights=None, stress_slot_multipliers=None):
    """
    Solves the scheduling problem using Gurobi with contextual objective terms
    and a reward for contiguous leisure time.
    Implements Pi-based condition as a pre-filter and schedules all eligible tasks (Constraint 6.1).
    Maximizes weighted leisure, minimizes context-dependent stress, and rewards adjacent leisure slots.

    Args:
        tasks (list): List of task dictionaries (T_all).
        commitments (dict): Dictionary mapping blocked GLOBAL slots to 15 (or any value). (Set C)
        alpha (float): Weight for maximizing *weighted* leisure time (per 15 min slot).
        beta (float): Weight for minimizing *context-dependent* stress (per task slot).
        gamma (float): Weight for maximizing *contiguous* leisure (reward per adjacent pair of leisure slots).
        daily_limit_slots (int, optional): Maximum task slots per day (Limit_daily).
        time_limit_sec (int): Solver time limit in seconds.
        hard_task_threshold (int): Difficulty level threshold above which a task is considered hard (inclusive).
        start_hour (int): The starting hour for the daily schedule (0-23).
        end_hour (int): The ending hour for the daily schedule (1-24), exclusive.
        leisure_slot_weights (dict, optional): Dict mapping slot index `s` to a leisure value weight `W_s`.
                                                If None, defaults are generated (e.g., higher evening value).
        stress_slot_multipliers (dict, optional): Dict mapping slot index `s` to a stress multiplier `M_s`.
                                                  If None, defaults are generated (e.g., higher during core hours).

    Returns:
        dict: Optimization status and results, including objective value, raw leisure, weighted scores, contiguous pairs.
    """
    # --- Validate and Calculate Dynamic Configuration ---
    try:
        slots_per_day, total_slots = calculate_dynamic_config(start_hour, end_hour)
    except ValueError as e:
         # Provide a dictionary with expected keys, even on config error
         return {
             "status": "Configuration Error",
             "message": f"Invalid start/end hours: {e}",
             "schedule": [],
             "raw_total_leisure_minutes": 0.0,
             "weighted_leisure_score": 0.0,
             "weighted_stress_score": 0.0,
             "contiguous_leisure_pairs": 0,
             "final_objective_value": None,
             "solve_time_seconds": 0.0,
             "completion_rate": 0.0,
             "filtered_tasks_info": []
        }

    # Handle edge case of zero slots
    if total_slots <= 0:
         return {
             'status': 'Configuration Error',
             'schedule': [],
             'raw_total_leisure_minutes': 0,
             'weighted_leisure_score': 0.0,
             'weighted_stress_score': 0.0,
             'contiguous_leisure_pairs': 0,
             'final_objective_value': None,
             'solve_time_seconds': 0.0,
             'completion_rate': 0.0,
             'message': f'Invalid time window {start_hour}:00 - {end_hour}:00 results in zero schedulable slots.',
             'filtered_tasks_info': []
        }

    # print(f"Gurobi Solver (Dynamic {start_hour}-{end_hour}, Contextual Objective, Contiguous Leisure) received {len(tasks)} total tasks.")
    # print(f"Gurobi Solver: {slots_per_day} slots/day, {total_slots} total slots.")
    # print(f"Gurobi Solver: received {len(commitments)} commitment slots.")
    # print(f"Gurobi Solver params: Alpha={alpha}, Beta={beta}, Gamma={gamma}, DailyLimitSlots={daily_limit_slots}, TimeLimit={time_limit_sec}s")
    # print(f"Hard task threshold: {hard_task_threshold}")

    # --- Generate/Validate Weights and Multipliers ---
    if leisure_slot_weights is None:
        W = generate_default_leisure_weights(total_slots, start_hour, slots_per_day)
        # print("Using default leisure weights (higher evening value).")
    else:
        W = leisure_slot_weights
        # print("Using provided leisure weights.")
        # Basic validation: ensure all slots 0..total_slots-1 are covered
        if not all(s in W for s in range(total_slots)):
             return {"status": "Error", "message": "Provided leisure_slot_weights missing entries for some slots.", "filtered_tasks_info": [], 'raw_total_leisure_minutes': 0,'weighted_leisure_score': 0, 'weighted_stress_score': 0, 'final_objective_value': None, 'completion_rate': 0, 'schedule': [], 'solve_time_seconds':0, 'contiguous_leisure_pairs': 0}

    if stress_slot_multipliers is None:
        M_stress = generate_default_stress_multipliers(total_slots, start_hour, slots_per_day)
        # print("Using default stress multipliers (higher during core hours).")
    else:
        M_stress = stress_slot_multipliers
        # print("Using provided stress multipliers.")
        if not all(s in M_stress for s in range(total_slots)):
             return {"status": "Error", "message": "Provided stress_slot_multipliers missing entries for some slots.", "filtered_tasks_info": [], 'raw_total_leisure_minutes': 0,'weighted_leisure_score': 0, 'weighted_stress_score': 0, 'final_objective_value': None, 'completion_rate': 0, 'schedule': [], 'solve_time_seconds':0, 'contiguous_leisure_pairs': 0}

    # --- Dynamically Build Preference Map ---
    # (Same as before)
    morning_slots = []
    afternoon_slots = []
    evening_slots = []
    for day in range(TOTAL_DAYS):
        base_global_slot = day * slots_per_day
        for slot_in_day in range(slots_per_day):
            global_slot_index = base_global_slot + slot_in_day
            try:
                slot_start_dt = slot_to_datetime(global_slot_index, start_hour, slots_per_day, total_slots)
                hour_of_slot = slot_start_dt.hour

                if 8 <= hour_of_slot < 12:
                    morning_slots.append(global_slot_index)
                if 12 <= hour_of_slot < 16:
                    afternoon_slots.append(global_slot_index)
                if 16 <= hour_of_slot < 22: # Evening still defined as 4pm-10pm
                    evening_slots.append(global_slot_index)
            except ValueError:
                 # print(f"Warning: Could not convert slot {global_slot_index} to datetime for preference map generation.")
                 continue # Skip this slot if conversion fails

    preference_map = {
        "any": set(range(total_slots)),
        "morning": set(morning_slots),
        "afternoon": set(afternoon_slots),
        "evening": set(evening_slots)
    }
    # print(f"Dynamic Pref Map Sizes: Any={len(preference_map['any'])}, M={len(preference_map['morning'])}, A={len(preference_map['afternoon'])}, E={len(preference_map['evening'])}")


    # --- Pre-filter tasks based on Pi condition (Section 3 in model.tex) ---
    LN_10_OVER_3 = math.log(10/3) # Approx 1.204

    schedulable_tasks = [] # This becomes Set T in the model
    unschedulable_tasks_info = []
    original_task_count = len(tasks) # |T_all|

    for i, task in enumerate(tasks):
        duration_slots = task.get("duration_slots", 1) # Use pre-calculated slots
        difficulty = task.get("difficulty", 1) # d_i
        priority = task.get("priority", 1) # p_i
        task_id = task.get('id', f"task-orig-{i}")
        task_name = task.get('name', f"Task {i}")
        deadline_slot = task.get("deadline_slot", total_slots - 1) # Use pre-calculated slot

        # Calculate duration_min from duration_slots for Pi check consistency
        duration_min = duration_slots * 15

        if difficulty <= 0 or priority <= 0:
             # print(f"Warning: Task '{task_name}' ({task_id}) has non-positive difficulty ({difficulty}) or priority ({priority}). Excluding from Pi check and scheduling.")
             unschedulable_tasks_info.append({
                 "id": task_id,
                 "name": task_name,
                 "reason": "Non-positive difficulty or priority",
                 "required_duration_min": None,
                 "current_duration_min": duration_min,
             })
             continue

        stress_factor = difficulty * priority
        required_duration_min_float = stress_factor * LN_10_OVER_3
        required_duration_min_int = math.ceil(required_duration_min_float)

        if duration_min >= required_duration_min_float:
            # Task already processed, just add it if it meets Pi condition
            # Double-check deadline feasibility again here, as total_slots might affect it
             if deadline_slot < duration_slots - 1:
                 reason_str = f"Deadline (slot {deadline_slot}) is too early for duration ({duration_slots} slots)."
                 # print(f"Task '{task_name}' ({task_id}) filtered out post-preprocessing: {reason_str}")
                 unschedulable_tasks_info.append({
                     "id": task_id, "name": task_name, "reason": reason_str,
                     "required_duration_min": required_duration_min_int,
                     "current_duration_min": duration_min,
                 })
             else:
                 schedulable_tasks.append(task) # Add the already processed task dict
        else:
            reason_str = (
                f"Pi condition not met. Required duration: "
                f"~{required_duration_min_int} min, Actual: {duration_min} min "
                f"(based on Difficulty: {difficulty}, Priority: {priority})"
            )
            # print(f"Task '{task_name}' ({task_id}) filtered out: {reason_str}")
            unschedulable_tasks_info.append({
                 "id": task_id,
                 "name": task_name,
                 "reason": reason_str,
                 "required_duration_min": required_duration_min_int,
                 "current_duration_min": duration_min,
            })

    n_tasks = len(schedulable_tasks) # |T|
    # print(f"Filtered tasks: {n_tasks} tasks are schedulable (meet Pi condition), {len(unschedulable_tasks_info)} tasks filtered out.")

    if n_tasks == 0:
        # print("Gurobi Solver: No schedulable tasks remaining after Pi filter.")
        total_possible_minutes = total_slots * 15
        # Calculate committed minutes accurately based on the commitment dict keys
        committed_minutes = len(commitments) * 15
        initial_leisure_minutes = max(0, total_possible_minutes - committed_minutes)
        # Calculate initial weighted leisure score (assuming W=1 for simplicity or using actual W if needed)
        initial_weighted_leisure = sum(W.get(s, 1.0) * 15 for s in range(total_slots) if s not in commitments)
        # No tasks means no contiguous leisure to reward
        initial_contiguous_pairs = 0
        for s in range(total_slots - 1):
            if s not in commitments and (s + 1) not in commitments:
                initial_contiguous_pairs += 1

        message = "No tasks provided or all tasks were filtered out by Pi condition or deadline constraints."
        if unschedulable_tasks_info:
             filtered_reasons = [f"{t['name']}: {t['reason']}" for t in unschedulable_tasks_info]
             message += f" Filtered tasks: {'; '.join(filtered_reasons)}."

        # Objective value if no tasks: alpha * leisure + gamma * contiguity
        initial_obj_val = (alpha * initial_weighted_leisure) + (gamma * initial_contiguous_pairs)

        return {
            'status': 'No Schedulable Tasks',
            'schedule': [],
            'raw_total_leisure_minutes': initial_leisure_minutes,
            'weighted_leisure_score': round(alpha * initial_weighted_leisure, 2), # Apply alpha
            'weighted_stress_score': 0.0,
            'contiguous_leisure_pairs': initial_contiguous_pairs,
            'final_objective_value': round(initial_obj_val, 3),
            'solve_time_seconds': 0.0,
            'completion_rate': 0.0, # No tasks scheduled / original_task_count
            'message': message,
            'filtered_tasks_info': unschedulable_tasks_info
        }

    # --- Create Gurobi Model ---
    try:
        # Use a context manager for the Gurobi environment
        with gp.Env(empty=True) as env:
            # Suppress Gurobi license message by setting LogToConsole
            env.setParam('LogToConsole', 0)
            env.start()
            with gp.Model("Weekly_Scheduler_Contextual_Contiguous", env=env) as m:
                # Control Gurobi verbosity
                m.setParam('OutputFlag', 0)
                m.setParam(GRB.Param.TimeLimit, time_limit_sec)

                # --- Decision Variables (Section 4 in model.tex, extended) ---
                X = m.addVars(n_tasks, total_slots, vtype=GRB.BINARY, name="X") # X_is: Task i starts at slot s
                L_var = m.addVars(total_slots, vtype=GRB.CONTINUOUS, lb=0, ub=15, name="L") # L_s: Leisure minutes in slot s
                Y = m.addVars(total_slots, vtype=GRB.BINARY, name="IsLeisure") # Y_s: 1 if slot s is leisure, 0 otherwise
                Z = m.addVars(total_slots - 1, vtype=GRB.BINARY, name="IsContiguousLeisurePair") # Z_s: 1 if s and s+1 are leisure

                # --- Objective Function (MODIFIED Section 5) ---
                obj_weighted_leisure = alpha * gp.quicksum(W.get(s, 1.0) * L_var[s] for s in range(total_slots))
                obj_contextual_stress = beta * gp.quicksum(X[i, s] * M_stress.get(s, 1.0) * (schedulable_tasks[i]["priority"] * schedulable_tasks[i]["difficulty"])
                                               for i in range(n_tasks) for s in range(total_slots))
                obj_contiguous_leisure = gamma * Z.sum() # Sum over all Z_s (s = 0 to total_slots-2)

                m.setObjective(obj_weighted_leisure - obj_contextual_stress + obj_contiguous_leisure, GRB.MAXIMIZE)
                # print(f"Objective: Maximize {alpha}*WeightedLeisure - {beta}*ContextualStress + {gamma}*ContiguousLeisurePairs")

                # --- Constraints (Section 6 in model.tex, extended) ---

                # 6.1: Mandatory Task Assignment
                for i in range(n_tasks):
                    m.addConstr(X.sum(i, '*') == 1, name=f"TaskMustStart_{i}")

                # 6.2: Hard Task Limitation
                hard_tasks_indices = [i for i in range(n_tasks) if schedulable_tasks[i]["difficulty"] >= hard_task_threshold]
                # print(f"Identified {len(hard_tasks_indices)} schedulable hard tasks (difficulty >= {hard_task_threshold})")
                for d in range(TOTAL_DAYS):
                    day_start_slot = d * slots_per_day
                    day_end_slot = day_start_slot + slots_per_day
                    if day_end_slot <= day_start_slot: continue

                    hard_task_vars_for_day = gp.quicksum(X[i, s] for i in hard_tasks_indices
                                               for s in range(day_start_slot, day_end_slot) if s < total_slots)
                    if hard_tasks_indices: # Only add if there are hard tasks
                        m.addConstr(hard_task_vars_for_day <= 1, name=f"MaxOneHardTask_Day_{d}")

                # 6.3: Deadlines and Horizon
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"]
                    dl = task_data["deadline_slot"] # Already clamped during preprocessing
                    task_key = task_data.get('id', i)

                    for s in range(total_slots):
                        # Deadline check: last slot occupied (s + dur - 1) must be <= dl
                        if s + dur - 1 > dl:
                            m.addConstr(X[i, s] == 0, name=f"Deadline_{task_key}_s{s}")
                        # Horizon check: task must end within horizon (last occupied slot < total_slots)
                        # task ends strictly *before* slot index 's + dur'
                        if s + dur > total_slots:
                             m.addConstr(X[i, s] == 0, name=f"HorizonEnd_{task_key}_s{s}")

                # 6.4: No Overlap
                slot_occupation_expr = {}
                for t in range(total_slots):
                    occupying_tasks_vars = gp.LinExpr()
                    for i in range(n_tasks):
                        dur = schedulable_tasks[i]["duration_slots"]
                        start_range_min = max(0, t - dur + 1)
                        start_range_max = t + 1
                        for start_slot in range(start_range_min, start_range_max):
                             if start_slot < total_slots and start_slot + dur <= total_slots:
                                 occupying_tasks_vars.add(X[i, start_slot])

                    slot_occupation_expr[t] = occupying_tasks_vars
                    if occupying_tasks_vars.size() > 0:
                         m.addConstr(occupying_tasks_vars <= 1, name=f"NoOverlap_s{t}")

                # 6.5: Preferences
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    pref = task_data.get("preference", "any")
                    task_key = task_data.get('id', i)
                    if pref not in preference_map: pref = "any"
                    allowed_slots = preference_map.get(pref, preference_map.get("any", set()))

                    for s in range(total_slots):
                        if s not in allowed_slots:
                            m.addConstr(X[i, s] == 0, name=f"PrefWin_{task_key}_s{s}")

                # 6.6: Commitments
                committed_slots = set(commitments.keys()) # Set C
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"]
                    task_key = task_data.get('id', i)
                    for s in range(total_slots):
                        task_occupies = set(range(s, min(s + dur, total_slots)))
                        valid_committed_slots = {cs for cs in committed_slots if 0 <= cs < total_slots}
                        if task_occupies.intersection(valid_committed_slots):
                            m.addConstr(X[i, s] == 0, name=f"CommitOverlap_{task_key}_s{s}")

                # 6.7: Leisure Calculation (Linking L_var and Y)
                for s in range(total_slots):
                    is_committed = 1 if s in committed_slots else 0
                    occupation_sum = slot_occupation_expr.get(s, 0)
                    if not isinstance(occupation_sum, (gp.LinExpr, int, float)): occupation_sum = 0

                    # If committed, L_var must be 0, Y must be 0
                    if is_committed:
                        m.addConstr(L_var[s] == 0, name=f"NoLeisure_Committed_L_{s}")
                        m.addConstr(Y[s] == 0, name=f"NoLeisure_Committed_Y_{s}")
                    else:
                        # If not committed, L_var can be up to 15 * (1 - occupation)
                        # Y indicates if L_var is actually 15 (i.e., the slot is fully leisure)
                        # L_var = 15 * Y[s] forces L_var to be 0 if Y=0, and 15 if Y=1
                        m.addConstr(L_var[s] == 15 * Y[s], name=f"Link_L_Y_{s}")
                        # Ensure slot is not occupied if it's leisure (Y=1)
                        # Y[s] = 1 implies occupation_sum must be 0
                        # Y[s] = 0 allows occupation_sum to be 0 or 1
                        # This is equivalent to: occupation_sum <= 1 - Y[s]
                        m.addConstr(occupation_sum <= 1 - Y[s], name=f"LeisureImpliesNotOccupied_{s}")


                # 6.8: Daily Limits (Optional)
                if daily_limit_slots is not None and daily_limit_slots >= 0:
                    # print(f"Applying daily limit of {daily_limit_slots} slots ({daily_limit_slots * 15} minutes)")
                    for d in range(TOTAL_DAYS):
                        daily_slots_occupied_expr = gp.LinExpr()
                        day_start_slot = d * slots_per_day
                        day_end_slot = day_start_slot + slots_per_day
                        if day_end_slot <= day_start_slot: continue

                        for i in range(n_tasks):
                            dur = schedulable_tasks[i]["duration_slots"]
                            for start_slot in range(total_slots):
                                task_end_slot_excl = start_slot + dur
                                intersect_start = max(start_slot, day_start_slot)
                                intersect_end = min(task_end_slot_excl, day_end_slot)
                                slots_in_day = max(0, intersect_end - intersect_start)

                                if slots_in_day > 0:
                                     if start_slot < total_slots and start_slot + dur <= total_slots:
                                         daily_slots_occupied_expr.add(X[i, start_slot] * slots_in_day)

                        if daily_slots_occupied_expr.size() > 0:
                           m.addConstr(daily_slots_occupied_expr <= daily_limit_slots, name=f"DailyLimit_Day_{d}")

                # 6.9: Contiguous Leisure Definition (Linking Z and Y)
                if total_slots > 1: # Only possible if there are at least 2 slots
                    for s in range(total_slots - 1):
                        # Z[s] = 1 iff Y[s]=1 and Y[s+1]=1
                        m.addConstr(Z[s] <= Y[s], name=f"Contig_Z_le_Y_s_{s}")
                        m.addConstr(Z[s] <= Y[s+1], name=f"Contig_Z_le_Y_s+1_{s}")
                        m.addConstr(Z[s] >= Y[s] + Y[s+1] - 1, name=f"Contig_Z_ge_Y_sum_{s}")


                # --- Solve ---
                # print(f"Gurobi Solver (Contextual+Contiguous {start_hour}-{end_hour}): Solving model for {n_tasks} schedulable tasks...")
                m.optimize()
                solve_time = m.Runtime

                # --- Process Results ---
                status = m.Status
                status_map = { GRB.OPTIMAL: "Optimal", GRB.INFEASIBLE: "Infeasible", GRB.UNBOUNDED: "Unbounded", GRB.INF_OR_UNBD: "Infeasible or Unbounded", GRB.TIME_LIMIT: "Time Limit Reached", GRB.SUBOPTIMAL: "Suboptimal", }
                gurobi_status_str = status_map.get(status, f"Gurobi Status Code {status}")
                # print(f"Gurobi Solver status: {gurobi_status_str} (solved in {solve_time:.2f}s)")

                final_schedule = []
                raw_leisure_minutes = 0.0
                weighted_leisure_contrib = 0.0 # Sum W_s*L_s
                weighted_stress_score = 0.0    # Sum X*M*p*d
                contiguous_leisure_pairs = 0   # Sum Z_s
                objective_value = None
                scheduled_task_count = 0
                message = f"Solver status: {gurobi_status_str} for {start_hour}:00-{end_hour}:00 window."
                filtered_tasks_msg = f" {len(unschedulable_tasks_info)} tasks were filtered out before optimization." if unschedulable_tasks_info else ""

                if status in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.TIME_LIMIT]:
                    if m.SolCount > 0:
                        # print("Gurobi Solver: Solution found!")
                        try:
                            objective_value = m.ObjVal
                        except gp.GurobiError:
                             objective_value = None # Can happen if TL hit before feasible found

                        schedule_records = []
                        solution_threshold = 0.5
                        scheduled_task_indices_in_solver = set()

                        # Calculate result metrics safely
                        try:
                            # Access solution values if they exist
                            if total_slots > 0 and hasattr(L_var[0], 'X'):
                                raw_leisure_minutes = sum(L_var[s].X for s in range(total_slots))
                                weighted_leisure_contrib = sum(W.get(s, 1.0) * L_var[s].X for s in range(total_slots))
                            if total_slots > 1 and hasattr(Z[0], 'X'):
                                contiguous_leisure_pairs = int(round(sum(Z[s].X for s in range(total_slots - 1))))
                        except (gp.GurobiError, AttributeError) as e:
                             # print(f"Warning: Could not access L_var/Z solution values: {e}")
                             raw_leisure_minutes = 0.0 # Fallback
                             weighted_leisure_contrib = 0.0
                             contiguous_leisure_pairs = 0

                        try:
                            if n_tasks > 0 and total_slots > 0 and hasattr(X[0,0],'X'):
                               weighted_stress_score = sum(X[i, s].X * M_stress.get(s, 1.0) * (schedulable_tasks[i]["priority"] * schedulable_tasks[i]["difficulty"])
                                                                 for i in range(n_tasks) for s in range(total_slots)
                                                                 if X[i, s].X > solution_threshold)
                        except (gp.GurobiError, AttributeError) as e:
                            # print(f"Warning: Could not access X solution values for stress calc: {e}")
                            weighted_stress_score = 0.0 # Fallback


                        for i in range(n_tasks):
                            task_data = schedulable_tasks[i]
                            task_scheduled_this_iter = False
                            for s in range(total_slots):
                                try:
                                    if (i, s) in X and X[i, s].X > solution_threshold:
                                        start_slot = s
                                        dur_slots = task_data["duration_slots"]
                                        end_slot = s + dur_slots - 1

                                        if end_slot >= total_slots: continue # Should be prevented by constraints

                                        start_dt = slot_to_datetime(start_slot, start_hour, slots_per_day, total_slots)
                                        output_end_dt = start_dt + timedelta(minutes=dur_slots * 15) # Natural end time

                                        record = {
                                            "id": task_data.get('id', f"task-result-{i}"),
                                            "name": task_data["name"], "priority": task_data["priority"],
                                            "difficulty": task_data["difficulty"], "start_slot": start_slot,
                                            "end_slot": end_slot, "startTime": start_dt.isoformat(),
                                            "endTime": output_end_dt.isoformat(), "duration_min": dur_slots * 15,
                                            "preference": task_data.get("preference", "any"),
                                            "stress_multiplier_at_start": M_stress.get(s, 1.0)
                                        }
                                        schedule_records.append(record)
                                        scheduled_task_indices_in_solver.add(i)
                                        task_scheduled_this_iter = True
                                        break
                                except (AttributeError, gp.GurobiError, ValueError) as e:
                                    # print(f"Error processing solution for X[{i},{s}]: {e}")
                                    continue

                        scheduled_task_count = len(scheduled_task_indices_in_solver)
                        if scheduled_task_count != n_tasks:
                             # print(f"CRITICAL WARNING: Expected {n_tasks} tasks, found {scheduled_task_count}. Check model constraints/feasibility.")
                             message += f" Warning: Mismatch in scheduled tasks ({scheduled_task_count}/{n_tasks})."

                        schedule_records.sort(key=lambda x: x["start_slot"])
                        final_schedule = schedule_records

                        # print(f"Gurobi Solver: Scheduled {scheduled_task_count} tasks (from set T).")
                        # print(f"Gurobi Solver: Calculated Raw Total Leisure = {raw_leisure_minutes:.1f} minutes")
                        # print(f"Gurobi Solver: Calculated Weighted Leisure Contribution (Sum W_s*L_s) = {weighted_leisure_contrib:.2f}")
                        # print(f"Gurobi Solver: Calculated Weighted Stress Score (Sum X*M*p*d) = {weighted_stress_score:.2f}")
                        # print(f"Gurobi Solver: Calculated Contiguous Leisure Pairs = {contiguous_leisure_pairs}")
                        # print(f"Gurobi Solver: Final Objective Value = {objective_value:.3f}" if objective_value is not None else "N/A")

                        message = f"Successfully scheduled {scheduled_task_count} tasks ({gurobi_status_str}). Total original tasks: {original_task_count}." + filtered_tasks_msg

                    else: # Status OK, but SolCount is 0
                        # print(f"Gurobi Solver: Status is {gurobi_status_str} but no solution found (SolCount=0).")
                        message = f"Solver finished with status {gurobi_status_str} but reported no feasible solution."
                        if status == GRB.TIME_LIMIT:
                             message = "Time limit reached before a feasible solution could be found."
                             try: objective_value = m.ObjBound # Get bound if TL hit
                             except: pass
                        message += filtered_tasks_msg

                elif status == GRB.INFEASIBLE:
                    # print("Gurobi Solver: Model is infeasible.")
                    message = "Could not find feasible schedule. Check constraints: deadlines, commitments, daily/hard task limits, window size?" + filtered_tasks_msg
                    # Optional: Compute and print IIS
                    # try:
                    #     m.computeIIS(); m.write("model_iis.ilp")
                    #     message += f" IIS written to model_iis.ilp."
                    # except: pass

                else: # Handle other Gurobi statuses
                     message = f"Solver finished with unhandled status: {gurobi_status_str}." + filtered_tasks_msg

                # Calculate completion rate based on original number of tasks
                completion_rate = scheduled_task_count / original_task_count if original_task_count > 0 else 0

                # Final results dictionary structure
                final_result = {
                    "status": gurobi_status_str,
                    "schedule": final_schedule,
                    "raw_total_leisure_minutes": round(raw_leisure_minutes, 1),
                    # This is the alpha * Sum(W_s * L_s) term from the objective
                    "weighted_leisure_score": round(alpha * weighted_leisure_contrib, 2),
                    # This is the Sum(X_is * M_s * p_i * d_i) term (beta is handled by objective)
                    "weighted_stress_score": round(weighted_stress_score, 2),
                    # Number of adjacent leisure slot pairs found
                    "contiguous_leisure_pairs": contiguous_leisure_pairs,
                    # This is the actual objective value achieved by the solver
                    "final_objective_value": round(objective_value, 3) if objective_value is not None else None,
                    "solve_time_seconds": round(solve_time, 2),
                    "completion_rate": round(completion_rate, 2),
                    "message": message,
                    "filtered_tasks_info": unschedulable_tasks_info
                }
                return final_result

    except gp.GurobiError as e:
        # print(f"Gurobi Error code {e.errno}: {e}")
        # Return structure consistent with other returns
        return {
            "status": "Gurobi Error", "message": f"Gurobi Error {e.errno}: {e}", "schedule": [],
            "raw_total_leisure_minutes": 0.0, "weighted_leisure_score": 0.0, "weighted_stress_score": 0.0,
            "contiguous_leisure_pairs": 0, "final_objective_value": None, "solve_time_seconds": 0.0,
            "completion_rate": 0.0, "filtered_tasks_info": unschedulable_tasks_info # Include filtered tasks if available before error
        }
    except Exception as e:
        # print(f"An unexpected error occurred during Gurobi optimization: {e}")
        # traceback.print_exc()
        return {
            "status": "Exception", "message": f"Unexpected error: {e}", "schedule": [],
            "raw_total_leisure_minutes": 0.0, "weighted_leisure_score": 0.0, "weighted_stress_score": 0.0,
            "contiguous_leisure_pairs": 0, "final_objective_value": None, "solve_time_seconds": 0.0,
            "completion_rate": 0.0, "filtered_tasks_info": unschedulable_tasks_info
        }
