# bc2411/allocation_logic_new.py
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
        # print(f"Initialized DAY0 Reference Midnight (naive local): {_day0_naive_local_ref_midnight}")
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
    return slots_per_day, total_slots

def slot_to_datetime(slot, start_hour, slots_per_day, total_slots):
    """
    Convert a global slot index [0..total_slots-1] back to a naive local datetime object.
    Represents the START time of the slot, based on dynamic hours.
    """
    day0_ref_midnight = get_day0_ref_midnight()
    day0_actual_start = day0_ref_midnight.replace(hour=start_hour, minute=0)

    if not (0 <= slot < total_slots):
        # Allow flexibility for end time calculation (slot = total_slots)
        if slot == total_slots:
            # Represents the theoretical end of the last slot (e.g., end_hour on the last day)
             # OR start_hour on the day after the last scheduling day
            return day0_actual_start + timedelta(days=TOTAL_DAYS)
        raise ValueError(f"Slot index {slot} is out of valid range [0, {total_slots-1}] for {slots_per_day} slots/day")

    day_index = slot // slots_per_day
    slot_in_day = slot % slots_per_day # Slot index within the start_hour to end_hour window

    # Calculate minutes from the start_hour window for that day
    total_minutes_from_start_hour = slot_in_day * 15

    # Calculate the target datetime by adding days and minutes to the actual day 0 start time
    target_datetime = day0_actual_start + timedelta(days=day_index, minutes=total_minutes_from_start_hour)
    return target_datetime # Returns naive local datetime

def datetime_to_slot(dt, start_hour, end_hour, slots_per_day, total_slots):
    """
    Convert a NAIVE LOCAL datetime object 'dt' to a global slot index [0..total_slots-1].
    Clamps times outside the 7-day horizon and the daily start_hour-end_hour window.
    """
    day0_ref_midnight = get_day0_ref_midnight()
    day0_actual_start = day0_ref_midnight.replace(hour=start_hour, minute=0)

    # --- 1. Clamp to 7-day Horizon ---
    horizon_end = day0_actual_start + timedelta(days=TOTAL_DAYS) # This is effectively start_hour on day 7
    # The last valid *start* time is the beginning of the last slot
    # Need to calculate the end slot index correctly
    last_slot_index = total_slots - 1
    if last_slot_index < 0: # Handle case where hours result in 0 slots
        return 0

    last_slot_start_dt = slot_to_datetime(last_slot_index, start_hour, slots_per_day, total_slots)

    if dt < day0_actual_start:
        dt_clamped = day0_actual_start
    elif dt >= horizon_end:
        # If dt is exactly or after the end horizon (start_hour day 7), map it to the last slot index
        dt_clamped = last_slot_start_dt
    else:
        dt_clamped = dt

    # --- 2. Calculate Day Index and Time within Day ---
    time_since_day0_start = dt_clamped - day0_actual_start
    # Need total minutes since midnight of day 0 for accurate day index calculation
    time_since_day0_midnight = dt_clamped - day0_ref_midnight
    total_minutes_from_day0_midnight = time_since_day0_midnight.total_seconds() / 60.0

    day_index = int(total_minutes_from_day0_midnight // (24 * 60))
    day_index = max(0, min(day_index, TOTAL_DAYS - 1))

    hour = dt_clamped.hour
    minute = dt_clamped.minute
    minutes_into_day_from_midnight = hour * 60 + minute

    # --- 3. Map to start_hour - end_hour Window (slots 0 to slots_per_day-1 within the day) ---
    start_minute_of_window = start_hour * 60
    end_minute_of_window = end_hour * 60 # Exclusive end

    if minutes_into_day_from_midnight < start_minute_of_window:
        slot_in_day = 0
    elif minutes_into_day_from_midnight >= end_minute_of_window:
        # Map times from end_hour onwards to the last slot of the day
        slot_in_day = slots_per_day - 1
    else:
        minutes_from_window_start = minutes_into_day_from_midnight - start_minute_of_window
        slot_in_day = int(minutes_from_window_start // 15)

    # Ensure slot_in_day is valid, especially if slots_per_day is 0
    if slots_per_day > 0:
        slot_in_day = max(0, min(slot_in_day, slots_per_day - 1))
    else:
        slot_in_day = 0 # Or handle as error? For now, clamp to 0

    # --- 4. Calculate Global Slot ---
    global_slot = day_index * slots_per_day + slot_in_day

    # Final clamping, considering potential zero slots
    if total_slots > 0:
         return max(0, min(global_slot, total_slots - 1))
    else:
         return 0


# --- Helper for Deadline Penalty ---
def calculate_deadline_penalty_factor(start_slot, task):
    """
    Calculates a factor [0, 1] based on how late the start_slot is compared
    to the latest possible start slot allowed by the deadline.
    Factor = start_slot / latest_possible_start_slot.
    Assumes start_slot is valid w.r.t. deadline (enforced by constraints).
    """
    duration_slots = task["duration_slots"]
    deadline_slot = task["deadline_slot"] # Already clamped

    # Latest possible start slot to meet the deadline
    latest_possible_start = deadline_slot - duration_slots + 1

    # Ensure latest_possible_start is non-negative (it should be due to deadline constraints)
    latest_possible_start = max(0, latest_possible_start)

    if latest_possible_start == 0:
        # If the latest possible start is slot 0, any valid start (only s=0) isn't "late".
        # Also handles cases where duration equals deadline+1, making latest_possible_start 0.
        return 0.0
    else:
        # start_slot is guaranteed by constraints to be <= latest_possible_start
        # Factor will be between 0 and 1.
        factor = start_slot / latest_possible_start
        return max(0.0, min(1.0, factor)) # Clamp just in case of float issues


# ------------------------------------------------------------
# GUROBI SCHEDULER FUNCTION (MODIFIED FOR DYNAMIC HOURS & DEADLINE PENALTY)
# ------------------------------------------------------------

def solve_schedule_gurobi(tasks, commitments, alpha=1.0, beta=0.1, gamma=1, # Added gamma for deadline penalty
                           daily_limit_slots=None, time_limit_sec=30, hard_task_threshold=4,
                           start_hour=8, end_hour=22):
    """
    Solves the scheduling problem using Gurobi. Implements Pi-based condition as a pre-filter
    and schedules all eligible tasks. Uses dynamic start/end hours and adds a stress penalty
    for scheduling tasks close to their deadline.

    Args:
        tasks (list): List of task dictionaries (T_all).
        commitments (dict): Dictionary mapping blocked GLOBAL slots to 15. (Set C)
        alpha (float): Weight for maximizing leisure time.
        beta (float): Weight for minimizing base stress (p*d).
        gamma (float): Weight multiplier for deadline proximity penalty in stress term.
        daily_limit_slots (int, optional): Maximum task slots per day (Limit_daily).
        time_limit_sec (int): Solver time limit in seconds.
        hard_task_threshold (int): Difficulty level threshold above which a task is considered hard (inclusive).
        start_hour (int): The starting hour for the daily schedule (0-23).
        end_hour (int): The ending hour for the daily schedule (1-24), exclusive.

    Returns:
        dict: Optimization status and results, including the objective value and components.
    """
    # --- Validate and Calculate Dynamic Configuration ---
    try:
        slots_per_day, total_slots = calculate_dynamic_config(start_hour, end_hour)
    except ValueError as e:
         return {"status": "Error", "message": f"Configuration Error: {e}", "filtered_tasks_info": [], "objective_value": None}

    # Handle edge case of zero slots
    if total_slots <= 0:
         return {'status': 'Configuration Error', 'schedule': [], 'total_leisure': 0, 'total_stress': 0.0, 'message': f'Invalid time window {start_hour}:00 - {end_hour}:00 results in zero schedulable slots.', 'filtered_tasks_info': [], 'objective_value': None}


    # print(f"Gurobi Solver (Dynamic {start_hour}-{end_hour}) received {len(tasks)} total tasks.")
    # print(f"Gurobi Solver: {slots_per_day} slots/day, {total_slots} total slots.")
    # print(f"Gurobi Solver: received {len(commitments)} commitment slots.")
    # print(f"Gurobi Solver params: Alpha={alpha}, Beta={beta}, Gamma={gamma}, DailyLimitSlots={daily_limit_slots}, TimeLimit={time_limit_sec}s") # Added Gamma
    # print(f"Hard task threshold: {hard_task_threshold}")

    # --- Dynamically Build Preference Map ---
    # Assumes standard definitions relative to 24h clock, then filters by start/end hour
    morning_slots = []
    afternoon_slots = []
    evening_slots = []
    for day in range(TOTAL_DAYS):
        base_global_slot = day * slots_per_day
        for slot_in_day in range(slots_per_day):
            global_slot_index = base_global_slot + slot_in_day
            # Find the actual time for this slot
            slot_start_dt = slot_to_datetime(global_slot_index, start_hour, slots_per_day, total_slots)
            hour_of_slot = slot_start_dt.hour

            if 8 <= hour_of_slot < 12:
                 morning_slots.append(global_slot_index)
            if 12 <= hour_of_slot < 16:
                 afternoon_slots.append(global_slot_index)
            if 16 <= hour_of_slot < 22: # Evening still defined as 4pm-10pm
                 evening_slots.append(global_slot_index)

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
        duration_min = task["duration_slots"] * 15 # Duration based on task input, not slots directly
        difficulty = task.get("difficulty", 1) # d_i
        priority = task.get("priority", 1) # p_i
        task_id = task.get('id', f"task-orig-{i}")
        task_name = task.get('name', f"Task {i}")

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
            # Add task copy, ensuring deadline_slot is valid for the *current* dynamic config
            task_copy = task.copy()
            task_copy["deadline_slot"] = min(task_copy["deadline_slot"], total_slots - 1) # Clamp deadline to new total slots
            # Also ensure duration doesn't exceed total slots (needed for deadline penalty calc)
            task_copy["duration_slots"] = min(task_copy["duration_slots"], total_slots)
            schedulable_tasks.append(task_copy) # Add to set T
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
        committed_minutes = len(commitments) * 15
        initial_leisure = total_possible_minutes - committed_minutes
        message = "No tasks provided or all tasks were filtered out by the Pi condition."
        if unschedulable_tasks_info:
             filtered_names = [f"{t['name']} (needs {t['required_duration_min']}m)" for t in unschedulable_tasks_info if t['required_duration_min'] is not None]
             if filtered_names:
                  message += f" Filtered tasks needing more time: {', '.join(filtered_names)}."
             else:
                  message += " Some tasks filtered due to non-positive difficulty/priority."

        return {'status': 'No Schedulable Tasks', 'schedule': [], 'total_leisure': initial_leisure, 'total_stress': 0.0, 'message': message, 'filtered_tasks_info': unschedulable_tasks_info, 'objective_value': alpha * initial_leisure} # Obj = alpha*Leisure - 0

    # --- Create Gurobi Model ---
    try:
        with gp.Env(empty=True) as env:
            # Suppress Gurobi license output by setting GRB.Param.OutputFlag here if possible,
            # or rely on OutputFlag=0 later. Setting it globally might require license details.
            # env.setParam('OutputFlag', 0)
            env.start()
            with gp.Model("Weekly_Scheduler_Dynamic", env=env) as m:
                m.setParam('OutputFlag', 0) # Suppress Gurobi console output
                m.setParam(GRB.Param.TimeLimit, time_limit_sec)

                # --- Decision Variables (Section 4 in model.tex) ---
                # X[i, s] = 1 if schedulable task i (from T) starts at slot s, 0 otherwise
                X = m.addVars(n_tasks, total_slots, vtype=GRB.BINARY, name="X")

                # L_var[s] = amount of leisure time (in minutes) in slot s
                L_var = m.addVars(total_slots, vtype=GRB.CONTINUOUS, lb=0, ub=15, name="L")

                # --- Objective Function (Section 5 in model.tex) ---
                # Maximize alpha * Leisure - beta * Stress
                # Stress includes base stress (p*d) + deadline penalty (gamma * p*d * lateness_factor)
                obj_leisure = alpha * gp.quicksum(L_var[s] for s in range(total_slots))

                # Calculate Stress Component with Deadline Penalty
                obj_stress_terms = gp.LinExpr()
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    priority = task_data["priority"]
                    difficulty = task_data["difficulty"]
                    base_stress_factor = priority * difficulty

                    # Ensure duration is positive before calculating penalty
                    if task_data["duration_slots"] <= 0: continue

                    for s in range(total_slots):
                        # Calculate the deadline penalty factor for starting task i at slot s
                        # This factor is 0 if task cannot start at s due to deadline (handled by constraints)
                        # It is non-zero only for potentially valid start slots.
                        deadline_penalty_factor = calculate_deadline_penalty_factor(s, task_data)

                        # Total stress multiplier for starting task i at s: p*d*(1 + gamma*factor)
                        total_stress_multiplier = base_stress_factor * (1 + gamma * deadline_penalty_factor)

                        # Add term X[i, s] * total_stress_multiplier to the objective's stress part
                        # Only add if X[i, s] exists (which it should here)
                        obj_stress_terms.add(X[i, s] * total_stress_multiplier)

                obj_stress = beta * obj_stress_terms # Multiply the sum of stress terms by beta

                m.setObjective(obj_leisure - obj_stress, GRB.MAXIMIZE)


                # --- Constraints (Section 6 in model.tex) ---

                # 6.1: Mandatory Task Assignment
                # Ensures every task i in T (schedulable_tasks) is scheduled exactly once.
                for i in range(n_tasks):
                    m.addConstr(X.sum(i, '*') == 1, name=f"TaskMustStart_{i}")

                # 6.2: Hard Task Limitation
                # At most one hard task (difficulty >= threshold) can start per day. Applies to tasks in T.
                hard_tasks_indices = [i for i in range(n_tasks) if schedulable_tasks[i]["difficulty"] >= hard_task_threshold]
                # print(f"Identified {len(hard_tasks_indices)} schedulable hard tasks (difficulty >= {hard_task_threshold})")
                for d in range(TOTAL_DAYS):
                    day_start_slot = d * slots_per_day
                    day_end_slot = day_start_slot + slots_per_day # Exclusive end slot index for range
                    # Sum starts of hard tasks within this day
                    hard_task_vars_for_day = gp.quicksum(X[i, s] for i in hard_tasks_indices
                                               for s in range(day_start_slot, day_end_slot)) # Range up to, but not including, end slot
                    if hard_tasks_indices and day_end_slot > day_start_slot: # Check if day has slots
                        m.addConstr(hard_task_vars_for_day <= 1, name=f"MaxOneHardTask_Day_{d}")
                        # print(f"  Constraint Day {d} (Slots {day_start_slot}-{day_end_slot-1}): Max 1 hard task (from T) start (diff >= {hard_task_threshold})")

                # 6.3: Deadlines and Horizon
                # Task i (in T) cannot start at s if it finishes after its deadline (dl_i) or after the horizon (total_slots).
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"] # dur_slots_i
                    dl = task_data["deadline_slot"] # dl_i (already clamped)
                    task_key = task_data.get('id', i)
                    # Ensure duration is positive before adding constraints based on it
                    if dur <= 0: continue
                    for s in range(total_slots):
                        # Deadline check: last slot (s + dur - 1) must be <= dl_i
                        if s + dur - 1 > dl:
                            m.addConstr(X[i, s] == 0, name=f"Deadline_{task_key}_s{s}")
                        # Horizon check: task must end within horizon (last slot < total_slots)
                        # Equivalent to: s + dur <= total_slots, or s <= total_slots - dur
                        if s > total_slots - dur:
                             m.addConstr(X[i, s] == 0, name=f"HorizonEnd_{task_key}_s{s}")

                # 6.4: No Overlap
                # Sum of tasks i (in T) occupying slot t must be <= 1.
                slot_occupation_expr = {}
                for t in range(total_slots):
                    # Sum X[i, start] for tasks i active during slot t
                    # Task i is active at t if it started at 'start' where: t - dur_slots_i + 1 <= start <= t
                    occupying_tasks_vars = gp.LinExpr()
                    for i in range(n_tasks):
                        dur = schedulable_tasks[i]["duration_slots"]
                        if dur <= 0: continue # Skip tasks with no duration
                        for start_slot in range(max(0, t - dur + 1), t + 1):
                             # Ensure start_slot is valid and task does not exceed horizon if starting here
                             if start_slot < total_slots and start_slot + dur <= total_slots:
                                 # Make sure variable exists before adding
                                 if (i, start_slot) in X:
                                     occupying_tasks_vars.add(X[i, start_slot])

                    slot_occupation_expr[t] = occupying_tasks_vars
                    if occupying_tasks_vars.size() > 0: # Only add constraint if there are variables involved
                         m.addConstr(occupying_tasks_vars <= 1, name=f"NoOverlap_s{t}")

                # 6.5: Preferences
                # Task i (in T) cannot start at s if s is not in its AllowedSlots_i.
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    pref = task_data.get("preference", "any")
                    task_key = task_data.get('id', i)
                    if pref not in preference_map:
                        # print(f"Warning: Invalid preference '{pref}' for task {task_key}. Defaulting to 'any'.")
                        pref = "any"
                    allowed_slots = preference_map.get(pref, preference_map["any"]) # AllowedSlots_i

                    for s in range(total_slots):
                        if s not in allowed_slots:
                             if (i, s) in X: # Check var exists
                                m.addConstr(X[i, s] == 0, name=f"PrefWin_{task_key}_s{s}")

                # 6.6: Commitments
                # Task i (in T) cannot start at s if it would occupy any slot in C.
                committed_slots = set(commitments.keys()) # Set C
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"]
                    if dur <= 0: continue # Skip tasks with no duration
                    task_key = task_data.get('id', i)
                    for s in range(total_slots):
                        # Slots task *would* occupy if it starts at s: {s, s+1, ..., s + dur - 1}
                        task_occupies = set(range(s, min(s + dur, total_slots)))
                        # Check intersection with committed slots C
                        # Ensure committed slot index is within the current dynamic range
                        valid_committed_slots = {cs for cs in committed_slots if 0 <= cs < total_slots}
                        if task_occupies.intersection(valid_committed_slots):
                            if (i, s) in X: # Check var exists
                                m.addConstr(X[i, s] == 0, name=f"CommitOverlap_{task_key}_s{s}")

                # 6.7: Leisure Calculation (No Y)
                # Defines L_s based on commitments and direct task occupation (from X).
                for s in range(total_slots):
                    # Equation (6.7.1): L_s = 0 if s is committed (s in C)
                    is_committed = 1 if s in committed_slots else 0
                    if is_committed:
                        if s in L_var: # Check var exists
                            m.addConstr(L_var[s] == 0, name=f"NoLeisure_Committed_{s}")
                    # Equation (6.7.2): L_s <= 15 * (1 - Occupation) if s is not committed
                    else:
                        # Retrieve the pre-calculated occupation expression for slot s
                        occupation_sum = slot_occupation_expr.get(s, 0) # Use 0 if no tasks can occupy slot s
                        if s in L_var: # Check var exists
                            m.addConstr(L_var[s] <= 15 * (1 - occupation_sum), name=f"LeisureBound_NotCommitted_{s}")
                    # Equation (6.7.3) L_s >= 0 is implicitly handled by variable definition lb=0

                # 6.8: Daily Limits (Optional, No Y)
                # Sum of slots occupied by tasks within a day d must be <= Limit_daily.
                if daily_limit_slots is not None and daily_limit_slots >= 0:
                    # print(f"Applying daily limit of {daily_limit_slots} slots ({daily_limit_slots * 15} minutes)")
                    for d in range(TOTAL_DAYS):
                        daily_slots_occupied_expr = gp.LinExpr()
                        day_start_slot = d * slots_per_day
                        day_end_slot = day_start_slot + slots_per_day # Exclusive end

                        if day_end_slot <= day_start_slot: continue # Skip if no slots in day

                        for i in range(n_tasks):
                            dur = schedulable_tasks[i]["duration_slots"]
                            if dur <= 0: continue # Skip tasks with no duration
                            for start_slot in range(total_slots):
                                # Calculate slots occupied by task i (starting at start_slot) *within day d*
                                task_end_slot_excl = start_slot + dur # Exclusive end slot index + 1

                                # Intersection calculation: [max(start, day_start), min(task_end, day_end))
                                intersect_start = max(start_slot, day_start_slot)
                                intersect_end = min(task_end_slot_excl, day_end_slot) # Use exclusive end for comparison

                                slots_in_day = max(0, intersect_end - intersect_start)

                                if slots_in_day > 0:
                                     # Add term X[i, start_slot] * slots_in_day to the expression
                                     # Ensure variable X[i, start_slot] is valid (used in other constraints)
                                     if start_slot < total_slots and start_slot + dur <= total_slots:
                                         if (i, start_slot) in X: # Check var exists
                                             daily_slots_occupied_expr.add(X[i, start_slot] * slots_in_day)

                        m.addConstr(daily_slots_occupied_expr <= daily_limit_slots, name=f"DailyLimit_Day_{d}")
                        # print(f"  Constraint Day {d} (Slots {day_start_slot}-{day_end_slot-1}): Sum(slots_in_day * X[i,start]) <= {daily_limit_slots}")


                # --- Solve ---
                # print(f"Gurobi Solver (Dynamic {start_hour}-{end_hour}): Solving model for {n_tasks} schedulable tasks...")
                m.optimize()
                solve_time = m.Runtime

                # --- Process Results ---
                status = m.Status
                status_map = { GRB.OPTIMAL: "Optimal", GRB.INFEASIBLE: "Infeasible", GRB.UNBOUNDED: "Unbounded", GRB.INF_OR_UNBD: "Infeasible or Unbounded", GRB.TIME_LIMIT: "Time Limit Reached", GRB.SUBOPTIMAL: "Suboptimal", }
                gurobi_status_str = status_map.get(status, f"Gurobi Status Code {status}")
                # print(f"Gurobi Solver status: {gurobi_status_str} (solved in {solve_time:.2f}s)")

                final_schedule = []
                final_total_leisure = 0.0
                final_total_stress = 0.0 # This now represents the full stress term from the objective
                final_objective_value = None # Initialize objective value
                scheduled_task_count = 0
                message = f"Solver status: {gurobi_status_str} for {start_hour}:00-{end_hour}:00 window."
                filtered_tasks_msg = f" {len(unschedulable_tasks_info)} tasks were filtered out before optimization due to the Pi condition." if unschedulable_tasks_info else ""

                if status in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.TIME_LIMIT]:
                    if m.SolCount > 0:
                        # print("Gurobi Solver: Solution found!")
                        schedule_records = []
                        solution_threshold = 0.5
                        scheduled_task_indices_in_solver = set() # Track indices (0 to n_tasks-1) scheduled
                        final_objective_value = m.ObjVal # Get objective value from the solution

                        for i in range(n_tasks):
                            task_data = schedulable_tasks[i] # Get data for the i-th schedulable task
                            dur_slots = task_data["duration_slots"]
                            if dur_slots <= 0: continue # Skip tasks with no duration

                            task_scheduled_this_iter = False
                            for s in range(total_slots):
                                try:
                                    if (i, s) in X and hasattr(X[i, s], 'X') and X[i, s].X > solution_threshold:
                                        start_slot = s
                                        end_slot = s + dur_slots - 1 # Inclusive end slot

                                        if end_slot >= total_slots:
                                             # print(f"Error: Task {task_data['id']} starts at {s} but calculated end_slot {end_slot} exceeds limit {total_slots-1}. Skipping.")
                                             continue

                                        # Use dynamic helpers for datetime conversion
                                        start_dt = slot_to_datetime(start_slot, start_hour, slots_per_day, total_slots)
                                        # Calculate end time carefully
                                        end_dt = start_dt + timedelta(minutes=dur_slots * 15)

                                        # Calculate the grid end time for that specific day
                                        day_ref_midnight = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                                        day_end_limit_dt = day_ref_midnight.replace(hour=end_hour, minute=0) # End hour is exclusive boundary

                                        # Check if calculated end time exceeds the grid's end hour for that day
                                        # Use ">=" because end_hour is exclusive boundary (e.g. 22:00 is outside if end_hour=22)
                                        if end_dt > day_end_limit_dt:
                                            # print(f"WARNING: Task {task_data['id']} (Start: {start_dt}, Duration: {dur_slots*15}m) calculated end time {end_dt} exceeds day grid limit {day_end_limit_dt}. Using day end limit {day_end_limit_dt} for output endTime.")
                                            output_end_dt = day_end_limit_dt
                                        else:
                                            output_end_dt = end_dt


                                        record = {
                                            "id": task_data.get('id', f"task-result-{i}"),
                                            "name": task_data["name"],
                                            "priority": task_data["priority"],
                                            "difficulty": task_data["difficulty"],
                                            "start_slot": start_slot,
                                            "end_slot": end_slot, # Slot index of the last slot occupied
                                            "startTime": start_dt.isoformat(),
                                            "endTime": output_end_dt.isoformat(), # Represents the actual end time, potentially clamped to grid end hour
                                            "duration_min": dur_slots * 15,
                                            "preference": task_data.get("preference", "any")
                                        }
                                        schedule_records.append(record)
                                        scheduled_task_indices_in_solver.add(i)
                                        task_scheduled_this_iter = True
                                        break # Move to next task (i) once start slot found
                                except (AttributeError, gp.GurobiError) as e:
                                    # print(f"Error accessing solution value for X[{i},{s}]: {e}")
                                    continue # Try next slot for this task

                        # Verify all schedulable tasks were indeed scheduled
                        scheduled_task_count = len(scheduled_task_indices_in_solver)
                        if scheduled_task_count != n_tasks:
                             # print(f"CRITICAL WARNING: Expected {n_tasks} schedulable tasks (set T) to be scheduled due to Constraint 6.1, but only found {scheduled_task_count} in the solution variables. Model might be infeasible or have conflicting constraints not caught earlier.")
                             message += f" Warning: Mismatch in expected ({n_tasks}) vs found ({scheduled_task_count}) scheduled tasks (from T)."

                        schedule_records.sort(key=lambda x: x["start_slot"])
                        final_schedule = schedule_records

                        # Calculate total leisure from L_var values
                        if total_slots > 0:
                             try:
                                 # Check if L_var exists and has values before summing
                                 if L_var:
                                     final_total_leisure = sum(L_var[s].X for s in range(total_slots) if s in L_var and hasattr(L_var[s], 'X'))
                                 else:
                                     final_total_leisure = 0.0
                             except gp.GurobiError: # Handle cases where solution exists but variables might not be accessible
                                 final_total_leisure = sum(L_var[s].X for s in range(total_slots) if s in L_var and hasattr(L_var[s], 'X')) # Safer summation


                        # Recalculate total stress based on the actual scheduled tasks using the objective's formula
                        calculated_obj_stress_value = 0.0
                        if n_tasks > 0 and total_slots > 0:
                            try:
                                # Recompute using the same expression structure as the objective
                                current_obj_stress_terms = gp.LinExpr()
                                for i in range(n_tasks):
                                    task_data = schedulable_tasks[i]
                                    priority = task_data["priority"]
                                    difficulty = task_data["difficulty"]
                                    base_stress_factor = priority * difficulty
                                    dur_slots = task_data["duration_slots"]
                                    if dur_slots <= 0: continue # Skip tasks with no duration

                                    for s in range(total_slots):
                                        # Check if this task was scheduled at this slot
                                        if (i, s) in X and hasattr(X[i, s], 'X') and X[i, s].X > solution_threshold:
                                            deadline_penalty_factor = calculate_deadline_penalty_factor(s, task_data)
                                            total_stress_multiplier = base_stress_factor * (1 + gamma * deadline_penalty_factor)
                                            current_obj_stress_terms.add(X[i, s].X * total_stress_multiplier) # Use .X value
                                            break # Task found, move to next task i

                                calculated_obj_stress_value = beta * current_obj_stress_terms.getValue()
                                final_total_stress = calculated_obj_stress_value # Use the value consistent with objective
                            except gp.GurobiError:
                                 # Fallback if getValue fails (e.g., time limit) - less precise but better than nothing
                                 final_total_stress = sum(
                                     X[i, s].X * beta * (
                                         schedulable_tasks[i]["priority"] * schedulable_tasks[i]["difficulty"] *
                                         (1 + gamma * calculate_deadline_penalty_factor(s, schedulable_tasks[i]))
                                     )
                                     for i in range(n_tasks)
                                     if schedulable_tasks[i]["duration_slots"] > 0
                                     for s in range(total_slots)
                                     if (i, s) in X and hasattr(X[i,s], 'X') and X[i,s].X > solution_threshold
                                 )


                        # print(f"Gurobi Solver: Scheduled {scheduled_task_count} tasks (from set T).")
                        # print(f"Gurobi Solver: Calculated Total Leisure = {final_total_leisure:.1f} minutes")
                        # print(f"Gurobi Solver: Calculated Total Stress Score (including deadline penalty) = {final_total_stress:.1f}")
                        # print(f"Gurobi Solver: Final Objective Value = {final_objective_value:.1f}")

                        message = f"Successfully scheduled {scheduled_task_count} tasks meeting the Pi condition ({gurobi_status_str}). Total original tasks: {original_task_count}." + filtered_tasks_msg

                    else: # Status indicated solution possible, but SolCount is 0
                        # print(f"Gurobi Solver: Status is {gurobi_status_str} but no solution found (SolCount=0).")
                        message = f"Solver finished with status {gurobi_status_str} but reported no feasible solution."
                        if status == GRB.TIME_LIMIT:
                             message = "Time limit reached before a feasible solution could be found."
                             # Still try to get ObjBound if available for TL results
                             try: final_objective_value = m.ObjBound
                             except: pass
                        message += filtered_tasks_msg

                elif status == GRB.INFEASIBLE:
                    # print("Gurobi Solver: Model is infeasible.")
                    message = "Could not find a feasible schedule for the tasks meeting the Pi condition. Check constraints: deadlines too tight? Too many commitments? Daily limits too strict? Hard task limits conflicting? Insufficient time slots available in the selected window?" + filtered_tasks_msg
                    # Objective value is not meaningful for infeasible models
                    final_objective_value = None
                    # Optional: Compute and print IIS for debugging
                    # try:
                    #     print("Computing IIS...")
                    #     m.computeIIS()
                    #     m.write("model_iis.ilp")
                    #     print("IIS written to model_iis.ilp.")
                    # except Exception as iis_e:
                    #     print(f"Could not compute IIS: {iis_e}")

                else: # Handle other Gurobi statuses
                     message = f"Solver finished with unhandled status: {gurobi_status_str}." + filtered_tasks_msg
                     final_objective_value = None # No meaningful objective value

                # Calculate completion rate based on original number of tasks
                completion_rate = scheduled_task_count / original_task_count if original_task_count > 0 else 0

                return {
                    "status": gurobi_status_str,
                    "schedule": final_schedule,
                    "total_leisure": round(final_total_leisure, 1),
                    "total_stress": round(final_total_stress, 1), # This now includes the deadline penalty component
                    "objective_value": round(final_objective_value, 2) if final_objective_value is not None else None, # Return the objective value
                    "solve_time_seconds": round(solve_time, 2),
                    "completion_rate": round(completion_rate, 2), # Ratio of scheduled tasks (from T) to original tasks (T_all)
                    "message": message,
                    "filtered_tasks_info": unschedulable_tasks_info # Contains reasons for filtering
                }

    except gp.GurobiError as e:
        print(f"Gurobi Error code {e.errno}: {e}")
        filtered_tasks_info_on_error = unschedulable_tasks_info if 'unschedulable_tasks_info' in locals() else []
        return {"status": "Error", "message": f"Gurobi Error: {e}", "filtered_tasks_info": filtered_tasks_info_on_error, "objective_value": None}
    except Exception as e:
        print(f"An unexpected error occurred during Gurobi optimization: {e}")
        print(traceback.format_exc())
        filtered_tasks_info_on_error = unschedulable_tasks_info if 'unschedulable_tasks_info' in locals() else []
        return {"status": "Error", "message": f"Unexpected error during optimization: {e}", "filtered_tasks_info": filtered_tasks_info_on_error, "objective_value": None}
