# bc2411/allocation_logic.py
import numpy as np
from datetime import datetime, timedelta, timezone
import math
import traceback # Keep for potential debugging in helpers
# --- Import Gurobi ---
import gurobipy as gp
from gurobipy import GRB

# ------------------------------------------------------------
# CONFIG: 7 days, each day has 56 slots => 392 total slots
# Each slot = 15 minutes from 08:00 to 22:00 (exclusive end) LOCAL TIME
# ------------------------------------------------------------
SLOTS_PER_DAY = 56 # (22 - 8) hours * 4 slots/hour = 14 * 4 = 56
TOTAL_DAYS = 7
TOTAL_SLOTS = SLOTS_PER_DAY * TOTAL_DAYS  # 392
GRID_END_HOUR = 22 # Define the scheduling end hour (exclusive)

# We'll define "day 0" as "today at 08:00 local time."
# Store as naive local time. Calculations will be relative to this.
_day0_naive_local = None
def get_day0():
    global _day0_naive_local
    if _day0_naive_local is None:
        # Ensure it gets initialized only once, even if called multiple times before 8am
        now = datetime.now()
        start_of_today = now.replace(hour=8, minute=0, second=0, microsecond=0)
        # If current time is before 8am today, day0 should be 8am today.
        # If current time is after 8am today, day0 should still be 8am today.
        _day0_naive_local = start_of_today
        print(f"Initialized DAY0 (naive local): {_day0_naive_local}")
    return _day0_naive_local

# ------------------------------------------------------------
# HELPER FUNCTIONS (Unchanged from original)
# ------------------------------------------------------------

def slot_to_datetime(slot):
    """
    Convert a global slot index [0..TOTAL_SLOTS-1] back to a naive local datetime object.
    Represents the START time of the slot.
    """
    day0 = get_day0()
    if not (0 <= slot < TOTAL_SLOTS):
        # Allow slight flexibility for end time calculation (slot = TOTAL_SLOTS)
        if slot == TOTAL_SLOTS:
            # Represents the theoretical end of the last slot (e.g., 22:00 on the last day)
            # OR 8:00 on the day after the last scheduling day
            return day0 + timedelta(days=TOTAL_DAYS)
        raise ValueError(f"Slot index {slot} is out of valid range [0, {TOTAL_SLOTS-1}]")

    day_index = slot // SLOTS_PER_DAY
    slot_in_day = slot % SLOTS_PER_DAY # Slot index within the 8am-10pm window (0 to 55)

    # Calculate minutes from the start of the 8am window for that day
    total_minutes_from_8am = slot_in_day * 15

    # Calculate the target datetime by adding days and minutes to day0
    target_datetime = day0 + timedelta(days=day_index, minutes=total_minutes_from_8am)
    return target_datetime # Returns naive local datetime

def datetime_to_slot(dt):
    """
    Convert a NAIVE LOCAL datetime object 'dt' to a global slot index [0..TOTAL_SLOTS-1].
    Clamps times outside the 7-day horizon and the daily 8am-10pm window.
    """
    day0 = get_day0()

    # --- 1. Clamp to 7-day Horizon ---
    horizon_end = day0 + timedelta(days=TOTAL_DAYS) # This is effectively 8am on day 7
    # The last valid *start* time is the beginning of the last slot
    last_slot_start_dt = slot_to_datetime(TOTAL_SLOTS - 1)

    if dt < day0:
        dt_clamped = day0
    elif dt >= horizon_end:
        # If dt is exactly or after the end horizon (8am day 7), map it to the last slot index
        dt_clamped = last_slot_start_dt
    else:
        dt_clamped = dt

    # --- 2. Calculate Day Index and Time within Day ---
    time_since_day0 = dt_clamped - day0
    total_minutes_from_day0_start = time_since_day0.total_seconds() / 60.0

    day_index = int(total_minutes_from_day0_start // (24 * 60))
    day_index = max(0, min(day_index, TOTAL_DAYS - 1))

    hour = dt_clamped.hour
    minute = dt_clamped.minute
    minutes_into_day = hour * 60 + minute

    # --- 3. Map to 8am-10pm Window (slots 0-55 within the day) ---
    start_minute_of_window = 8 * 60  # 480
    end_minute_of_window = GRID_END_HOUR * 60 # 22 * 60 = 1320

    if minutes_into_day < start_minute_of_window:
        slot_in_day = 0
    elif minutes_into_day >= end_minute_of_window:
        # Map times from 22:00 onwards to the last slot of the day (index 55)
        slot_in_day = SLOTS_PER_DAY - 1
    else:
        minutes_from_8am = minutes_into_day - start_minute_of_window
        slot_in_day = int(minutes_from_8am // 15)

    slot_in_day = max(0, min(slot_in_day, SLOTS_PER_DAY - 1))

    # --- 4. Calculate Global Slot ---
    global_slot = day_index * SLOTS_PER_DAY + slot_in_day

    return max(0, min(global_slot, TOTAL_SLOTS - 1))


# Build sets of valid slots for "morning", "afternoon", "evening" (Unchanged)
morning_slots = []
afternoon_slots = []
evening_slots = []
for day in range(TOTAL_DAYS):
    base = day * SLOTS_PER_DAY
    morning_slots.extend(range(base, base + 16)) # 8am..<12pm
    afternoon_slots.extend(range(base + 16, base + 32)) # 12pm..<4pm
    evening_slots.extend(range(base + 32, base + SLOTS_PER_DAY)) # 4pm..<10pm

PREFERENCE_MAP = {
    "any": set(range(TOTAL_SLOTS)),
    "morning": set(morning_slots),
    "afternoon": set(afternoon_slots),
    "evening": set(evening_slots)
}

# ------------------------------------------------------------
# GUROBI SCHEDULER FUNCTION (NO Y VARIABLE)
# ------------------------------------------------------------

def solve_schedule_gurobi(tasks, commitments, alpha=1.0, beta=0.1, daily_limit_slots=None, time_limit_sec=30, hard_task_threshold=4):
    """
    Solves the scheduling problem using Gurobi. Implements Pi-based condition as a pre-filter
    and schedules all eligible tasks. This version does NOT use the auxiliary Y variable.

    Args:
        tasks (list): List of task dictionaries (T_all).
        commitments (dict): Dictionary mapping blocked GLOBAL slots to 15. (Set C)
        alpha (float): Weight for maximizing leisure time.
        beta (float): Weight for minimizing stress.
        daily_limit_slots (int, optional): Maximum task slots per day (Limit_daily).
        time_limit_sec (int): Solver time limit in seconds.
        hard_task_threshold (int): Difficulty level threshold above which a task is considered hard (inclusive).

    Returns:
        dict: Optimization status and results.
    """

    print(f"Gurobi Solver (No Y var) received {len(tasks)} total tasks.")
    print(f"Gurobi Solver (No Y var) received {len(commitments)} commitment slots.")
    print(f"Gurobi Solver (No Y var) params: Alpha={alpha}, Beta={beta}, DailyLimitSlots={daily_limit_slots}, TimeLimit={time_limit_sec}s")
    print(f"Hard task threshold: {hard_task_threshold}")

    # --- Pre-filter tasks based on Pi condition (Section 3 in model.tex) ---
    LN_10_OVER_3 = math.log(10/3) # Approx 1.204

    schedulable_tasks = [] # This becomes Set T in the model
    unschedulable_tasks_info = []
    original_task_count = len(tasks) # |T_all|

    for i, task in enumerate(tasks):
        duration_min = task["duration_slots"] * 15
        difficulty = task.get("difficulty", 1) # d_i
        priority = task.get("priority", 1) # p_i
        task_id = task.get('id', f"task-orig-{i}")
        task_name = task.get('name', f"Task {i}")

        if difficulty <= 0 or priority <= 0:
             print(f"Warning: Task '{task_name}' ({task_id}) has non-positive difficulty ({difficulty}) or priority ({priority}). Excluding from Pi check and scheduling.")
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
            schedulable_tasks.append(task.copy()) # Add to set T
        else:
            reason_str = (
                f"Pi condition not met. Required duration: "
                f"~{required_duration_min_int} min, Actual: {duration_min} min "
                f"(based on Difficulty: {difficulty}, Priority: {priority})"
            )
            print(f"Task '{task_name}' ({task_id}) filtered out: {reason_str}")
            unschedulable_tasks_info.append({
                 "id": task_id,
                 "name": task_name,
                 "reason": reason_str,
                 "required_duration_min": required_duration_min_int,
                 "current_duration_min": duration_min,
            })

    n_tasks = len(schedulable_tasks) # |T|
    print(f"Filtered tasks: {n_tasks} tasks are schedulable (meet Pi condition), {len(unschedulable_tasks_info)} tasks filtered out.")

    if n_tasks == 0:
        print("Gurobi Solver (No Y var): No schedulable tasks remaining after Pi filter.")
        total_possible_minutes = TOTAL_SLOTS * 15
        committed_minutes = len(commitments) * 15
        initial_leisure = total_possible_minutes - committed_minutes
        message = "No tasks provided or all tasks were filtered out by the Pi condition."
        if unschedulable_tasks_info:
             filtered_names = [f"{t['name']} (needs {t['required_duration_min']}m)" for t in unschedulable_tasks_info if t['required_duration_min'] is not None]
             if filtered_names:
                  message += f" Filtered tasks needing more time: {', '.join(filtered_names)}."
             else:
                  message += " Some tasks filtered due to non-positive difficulty/priority."

        return {'status': 'No Schedulable Tasks', 'schedule': [], 'total_leisure': initial_leisure, 'total_stress': 0.0, 'message': message, 'filtered_tasks_info': unschedulable_tasks_info}

    # --- Create Gurobi Model ---
    try:
        with gp.Env(empty=True) as env:
            env.start()
            with gp.Model("Weekly_Scheduler_NoY", env=env) as m:
                m.setParam('OutputFlag', 0)
                m.setParam(GRB.Param.TimeLimit, time_limit_sec)

                # --- Decision Variables (Section 4 in model.tex) ---
                # X[i, s] = 1 if schedulable task i (from T) starts at slot s, 0 otherwise
                X = m.addVars(n_tasks, TOTAL_SLOTS, vtype=GRB.BINARY, name="X")

                # L_var[s] = amount of leisure time (in minutes) in slot s
                L_var = m.addVars(TOTAL_SLOTS, vtype=GRB.CONTINUOUS, lb=0, ub=15, name="L")

                # --- Objective Function (Section 5 in model.tex) ---
                # Maximize alpha * Leisure - beta * Stress
                obj_leisure = alpha * gp.quicksum(L_var[s] for s in range(TOTAL_SLOTS))
                # Stress is calculated for scheduled tasks (which are all tasks in T due to Constraint 6.1)
                obj_stress = beta * gp.quicksum(X[i, s] * (schedulable_tasks[i]["priority"] * schedulable_tasks[i]["difficulty"])
                                               for i in range(n_tasks) for s in range(TOTAL_SLOTS))
                m.setObjective(obj_leisure - obj_stress, GRB.MAXIMIZE)

                # --- Constraints (Section 6 in model.tex) ---

                # 6.1: Mandatory Task Assignment
                # Ensures every task i in T (schedulable_tasks) is scheduled exactly once.
                for i in range(n_tasks):
                    m.addConstr(X.sum(i, '*') == 1, name=f"TaskMustStart_{i}")

                # 6.2: Hard Task Limitation
                # At most one hard task (difficulty >= threshold) can start per day. Applies to tasks in T.
                hard_tasks_indices = [i for i in range(n_tasks) if schedulable_tasks[i]["difficulty"] >= hard_task_threshold]
                print(f"Identified {len(hard_tasks_indices)} schedulable hard tasks (difficulty >= {hard_task_threshold})")
                for d in range(TOTAL_DAYS):
                    day_start_slot = d * SLOTS_PER_DAY
                    day_end_slot = day_start_slot + SLOTS_PER_DAY
                    # Sum starts of hard tasks within this day
                    hard_task_vars_for_day = gp.quicksum(X[i, s] for i in hard_tasks_indices
                                               for s in range(day_start_slot, day_end_slot))
                    if hard_tasks_indices:
                        m.addConstr(hard_task_vars_for_day <= 1, name=f"MaxOneHardTask_Day_{d}")
                        print(f"  Constraint Day {d}: Max 1 hard task (from T) start (diff >= {hard_task_threshold})")

                # 6.3: Deadlines and Horizon
                # Task i (in T) cannot start at s if it finishes after its deadline (dl_i) or after the horizon (S_total).
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"] # dur_slots_i
                    dl = task_data["deadline_slot"] # dl_i
                    task_key = task_data.get('id', i)
                    for s in range(TOTAL_SLOTS):
                        # Deadline check: last slot (s + dur - 1) must be <= dl_i
                        if s + dur - 1 > dl:
                            m.addConstr(X[i, s] == 0, name=f"Deadline_{task_key}_s{s}")
                        # Horizon check: task must end within horizon (last slot < S_total)
                        # Equivalent to: s + dur <= S_total, or s <= S_total - dur
                        if s > TOTAL_SLOTS - dur:
                             m.addConstr(X[i, s] == 0, name=f"HorizonEnd_{task_key}_s{s}")

                # 6.4: No Overlap
                # Sum of tasks i (in T) occupying slot t must be <= 1.
                # This calculation is reused for Leisure and Daily Limits.
                # Cache the expressions for slot occupation to avoid redundant calculations.
                slot_occupation_expr = {}
                for t in range(TOTAL_SLOTS):
                    # Sum X[i, start] for tasks i active during slot t
                    # Task i is active at t if it started at 'start' where: t - dur_slots_i + 1 <= start <= t
                    occupying_tasks_vars = gp.LinExpr()
                    for i in range(n_tasks):
                        dur = schedulable_tasks[i]["duration_slots"]
                        for start_slot in range(max(0, t - dur + 1), t + 1):
                             # Ensure start_slot is valid and task does not exceed horizon if starting here
                             if start_slot < TOTAL_SLOTS and start_slot + dur <= TOTAL_SLOTS:
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
                    if pref not in PREFERENCE_MAP:
                        print(f"Warning: Invalid preference '{pref}' for task {task_key}. Defaulting to 'any'.")
                        pref = "any"
                    allowed_slots = PREFERENCE_MAP.get(pref, PREFERENCE_MAP["any"]) # AllowedSlots_i

                    for s in range(TOTAL_SLOTS):
                        if s not in allowed_slots:
                            m.addConstr(X[i, s] == 0, name=f"PrefWin_{task_key}_s{s}")

                # 6.6: Commitments
                # Task i (in T) cannot start at s if it would occupy any slot in C.
                committed_slots = set(commitments.keys()) # Set C
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"]
                    task_key = task_data.get('id', i)
                    for s in range(TOTAL_SLOTS):
                        # Slots task *would* occupy if it starts at s: {s, s+1, ..., s + dur - 1}
                        task_occupies = set(range(s, min(s + dur, TOTAL_SLOTS)))
                        # Check intersection with committed slots C
                        if task_occupies.intersection(committed_slots):
                            m.addConstr(X[i, s] == 0, name=f"CommitOverlap_{task_key}_s{s}")

                # 6.7: Leisure Calculation (No Y)
                # Defines L_s based on commitments and direct task occupation (from X).
                for s in range(TOTAL_SLOTS):
                    # Equation (6.7.1): L_s = 0 if s is committed (s in C)
                    is_committed = 1 if s in commitments else 0
                    if is_committed:
                        m.addConstr(L_var[s] == 0, name=f"NoLeisure_Committed_{s}")
                    # Equation (6.7.2): L_s <= 15 * (1 - Occupation) if s is not committed
                    else:
                        # Retrieve the pre-calculated occupation expression for slot s
                        occupation_sum = slot_occupation_expr.get(s, 0) # Use 0 if no tasks can occupy slot s
                        m.addConstr(L_var[s] <= 15 * (1 - occupation_sum), name=f"LeisureBound_NotCommitted_{s}")
                    # Equation (6.7.3) L_s >= 0 is implicitly handled by variable definition lb=0

                # 6.8: Daily Limits (Optional, No Y)
                # Sum of slots occupied by tasks within a day d must be <= Limit_daily.
                if daily_limit_slots is not None and daily_limit_slots >= 0:
                    print(f"Applying daily limit of {daily_limit_slots} slots ({daily_limit_slots * 15} minutes)")
                    for d in range(TOTAL_DAYS):
                        daily_slots_occupied_expr = gp.LinExpr()
                        day_start_slot = d * SLOTS_PER_DAY
                        day_end_slot = day_start_slot + SLOTS_PER_DAY

                        for i in range(n_tasks):
                            dur = schedulable_tasks[i]["duration_slots"]
                            for start_slot in range(TOTAL_SLOTS):
                                # Calculate slots occupied by task i (starting at start_slot) *within day d*
                                task_end_slot_excl = start_slot + dur # Exclusive end slot index + 1

                                # Intersection calculation: [max(start, day_start), min(task_end, day_end))
                                intersect_start = max(start_slot, day_start_slot)
                                intersect_end = min(task_end_slot_excl, day_end_slot) # Use exclusive end for comparison

                                slots_in_day = max(0, intersect_end - intersect_start)

                                if slots_in_day > 0:
                                     # Add term X[i, start_slot] * slots_in_day to the expression
                                     # Ensure variable X[i, start_slot] is valid (used in other constraints)
                                     if start_slot < TOTAL_SLOTS and start_slot + dur <= TOTAL_SLOTS:
                                         daily_slots_occupied_expr.add(X[i, start_slot] * slots_in_day)

                        m.addConstr(daily_slots_occupied_expr <= daily_limit_slots, name=f"DailyLimit_Day_{d}")
                        print(f"  Constraint Day {d}: Sum(slots_in_day * X[i,start]) <= {daily_limit_slots}")


                # --- Solve ---
                print(f"Gurobi Solver (No Y var): Solving the model for {n_tasks} schedulable tasks...")
                m.optimize()
                solve_time = m.Runtime

                # --- Process Results ---
                status = m.Status
                status_map = { GRB.OPTIMAL: "Optimal", GRB.INFEASIBLE: "Infeasible", GRB.UNBOUNDED: "Unbounded", GRB.INF_OR_UNBD: "Infeasible or Unbounded", GRB.TIME_LIMIT: "Time Limit Reached", GRB.SUBOPTIMAL: "Suboptimal", }
                gurobi_status_str = status_map.get(status, f"Gurobi Status Code {status}")
                print(f"Gurobi Solver (No Y var) status: {gurobi_status_str} (solved in {solve_time:.2f}s)")

                final_schedule = []
                final_total_leisure = 0.0
                final_total_stress = 0.0
                scheduled_task_count = 0
                message = f"Solver status: {gurobi_status_str}."
                filtered_tasks_msg = f" {len(unschedulable_tasks_info)} tasks were filtered out before optimization due to the Pi condition." if unschedulable_tasks_info else ""

                if status in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.TIME_LIMIT]:
                    if m.SolCount > 0:
                        print("Gurobi Solver (No Y var): Solution found!")
                        schedule_records = []
                        solution_threshold = 0.5
                        scheduled_task_indices_in_solver = set() # Track indices (0 to n_tasks-1) scheduled

                        for i in range(n_tasks):
                            task_data = schedulable_tasks[i] # Get data for the i-th schedulable task
                            task_scheduled_this_iter = False
                            for s in range(TOTAL_SLOTS):
                                try:
                                    if X[i, s].X > solution_threshold:
                                        start_slot = s
                                        dur_slots = task_data["duration_slots"]
                                        end_slot = s + dur_slots - 1

                                        if end_slot >= TOTAL_SLOTS:
                                             print(f"Error: Task {task_data['id']} starts at {s} but calculated end_slot {end_slot} exceeds limit {TOTAL_SLOTS-1}. Skipping.")
                                             continue

                                        start_dt = slot_to_datetime(start_slot)
                                        # Calculate end time carefully to avoid crossing day boundary if not intended
                                        end_dt = start_dt + timedelta(minutes=dur_slots * 15)
                                        day_of_task = start_dt.date()
                                        # Calculate the theoretical end of the grid for that specific day
                                        day_end_limit_dt = get_day0() + timedelta(days=start_dt.date().toordinal() - get_day0().date().toordinal()) # Get 8am on the task's day
                                        day_end_limit_dt = day_end_limit_dt.replace(hour=GRID_END_HOUR, minute=0, second=0, microsecond=0)


                                        # Check if calculated end time exceeds the grid's end hour for that day
                                        if end_dt > day_end_limit_dt:
                                            print(f"WARNING: Task {task_data['id']} (Start: {start_dt}, Duration: {dur_slots*15}m) calculated end time {end_dt} exceeds day grid limit {day_end_limit_dt}. Using day end limit {day_end_limit_dt} for output endTime.")
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
                                    print(f"Error accessing solution value for X[{i},{s}]: {e}")
                                    continue # Try next slot for this task

                        # Verify all schedulable tasks were indeed scheduled
                        scheduled_task_count = len(scheduled_task_indices_in_solver)
                        if scheduled_task_count != n_tasks:
                             print(f"CRITICAL WARNING: Expected {n_tasks} schedulable tasks (set T) to be scheduled due to Constraint 6.1, but only found {scheduled_task_count} in the solution variables. Model might be infeasible or have conflicting constraints not caught earlier.")
                             message += f" Warning: Mismatch in expected ({n_tasks}) vs found ({scheduled_task_count}) scheduled tasks (from T)."

                        schedule_records.sort(key=lambda x: x["start_slot"])
                        final_schedule = schedule_records

                        # Calculate total leisure from L_var values
                        final_total_leisure = gp.quicksum(L_var[s].X for s in range(TOTAL_SLOTS)).getValue()

                        # Recalculate stress based on the actual scheduled tasks
                        # This sum should match the objective term if all tasks in T were scheduled
                        final_total_stress = gp.quicksum(X[i, s].X * (schedulable_tasks[i]["priority"] * schedulable_tasks[i]["difficulty"])
                                                         for i in range(n_tasks) for s in range(TOTAL_SLOTS)
                                                         if (i, s) in X and X[i,s].X > solution_threshold).getValue()

                        print(f"Gurobi Solver (No Y var): Scheduled {scheduled_task_count} tasks (from set T).")
                        print(f"Gurobi Solver (No Y var): Calculated Total Leisure = {final_total_leisure:.1f} minutes")
                        print(f"Gurobi Solver (No Y var): Calculated Total Stress Score = {final_total_stress:.1f}")

                        message = f"Successfully scheduled {scheduled_task_count} tasks meeting the Pi condition ({gurobi_status_str}). Total original tasks: {original_task_count}." + filtered_tasks_msg

                    else: # Status indicated solution possible, but SolCount is 0
                        print(f"Gurobi Solver (No Y var): Status is {gurobi_status_str} but no solution found (SolCount=0).")
                        message = f"Solver finished with status {gurobi_status_str} but reported no feasible solution."
                        if status == GRB.TIME_LIMIT:
                             message = "Time limit reached before a feasible solution could be found."
                        message += filtered_tasks_msg

                elif status == GRB.INFEASIBLE:
                    print("Gurobi Solver (No Y var): Model is infeasible.")
                    message = "Could not find a feasible schedule for the tasks meeting the Pi condition. Check constraints: deadlines too tight? Too many commitments? Daily limits too strict? Hard task limits conflicting? Insufficient time slots available to schedule all mandatory (Pi-filtered) tasks?" + filtered_tasks_msg
                    # Optional: Compute and print IIS for debugging
                    # try:
                    #     print("Computing IIS to identify conflicting constraints...")
                    #     m.computeIIS()
                    #     m.write("model_iis.ilp") # Write IIS to a file
                    #     print("IIS written to model_iis.ilp. Infeasible constraints/bounds identified.")
                    #     # You can inspect the .ilp file or iterate through IIS constraints/vars here
                    # except Exception as iis_e:
                    #     print(f"Could not compute or print IIS: {iis_e}")


                else: # Handle other Gurobi statuses
                     message = f"Solver finished with unhandled status: {gurobi_status_str}." + filtered_tasks_msg

                # Calculate completion rate based on original number of tasks
                completion_rate = scheduled_task_count / original_task_count if original_task_count > 0 else 0

                return {
                    "status": gurobi_status_str,
                    "schedule": final_schedule,
                    "total_leisure": round(final_total_leisure, 1),
                    "total_stress": round(final_total_stress, 1), # This is the sum(p*d*X) term from objective
                    "solve_time_seconds": round(solve_time, 2),
                    "completion_rate": round(completion_rate, 2), # Ratio of scheduled tasks (from T) to original tasks (T_all)
                    "message": message,
                    "filtered_tasks_info": unschedulable_tasks_info # Contains reasons for filtering
                }

    except gp.GurobiError as e:
        print(f"Gurobi Error code {e.errno}: {e}")
        return {"status": "Error", "message": f"Gurobi Error: {e}", "filtered_tasks_info": unschedulable_tasks_info}
    except Exception as e:
        print(f"An unexpected error occurred during Gurobi optimization: {e}")
        print(traceback.format_exc())
        return {"status": "Error", "message": f"Unexpected error during optimization: {e}", "filtered_tasks_info": unschedulable_tasks_info}
