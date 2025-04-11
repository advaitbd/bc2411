# bc2411/allocation_logic.py
import numpy as np
from datetime import datetime, timedelta, timezone
import math
import traceback # Keep for potential debugging in helpers
from pulp import (
    LpProblem, LpMaximize, LpVariable, LpBinary, LpContinuous,
    lpSum, LpStatus, PULP_CBC_CMD # Import solver if needed explicitly
)
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
# GUROBI SCHEDULER FUNCTION
# ------------------------------------------------------------

def solve_schedule_gurobi(tasks, commitments, alpha=1.0, beta=0.1, daily_limit_slots=None, time_limit_sec=30, hard_task_threshold=4): # Removed target_completion_rate
    """
    Solves the scheduling problem using Gurobi. Implements Pi >= 0.7 as a pre-filter
    and schedules all eligible tasks.

    Args:
        tasks (list): List of task dictionaries.
        commitments (dict): Dictionary mapping blocked GLOBAL slots to 15.
        alpha (float): Weight for maximizing leisure time.
        beta (float): Weight for minimizing stress.
        daily_limit_slots (int, optional): Maximum task slots per day.
        time_limit_sec (int): Solver time limit in seconds.
        hard_task_threshold (int): Difficulty level threshold above which a task is considered hard (inclusive).

    Returns:
        dict: Optimization status and results.
    """

    print(f"Gurobi Solver received {len(tasks)} total tasks.")
    print(f"Gurobi Solver received {len(commitments)} commitment slots.")
    print(f"Gurobi Solver params: Alpha={alpha}, Beta={beta}, DailyLimitSlots={daily_limit_slots}, TimeLimit={time_limit_sec}s")
    print(f"Hard task threshold: {hard_task_threshold}")

    # --- Pre-filter tasks based on Pi >= 0.7 derived condition ---
    # Pi >= 0.7  =>  1 - exp(-(Duration_min / (Diff * Prio))) >= 0.7
    # => exp(-(Duration_min / (Diff * Prio))) <= 0.3
    # => -(Duration_min / (Diff * Prio)) <= ln(0.3)
    # => Duration_min / (Diff * Prio) >= -ln(0.3) = ln(1/0.3) = ln(10/3)
    # => Duration_min >= (Diff * Prio) * ln(10/3)
    # We assume difficulty and priority are >= 1. Handle potential Prio=0 or Diff=0 if necessary.
    LN_10_OVER_3 = math.log(10/3) # Approx 1.204

    schedulable_tasks = []
    unschedulable_tasks_info = [] # Changed field name for clarity
    original_task_count = len(tasks)

    for i, task in enumerate(tasks):
        duration_min = task["duration_slots"] * 15
        difficulty = task.get("difficulty", 1)
        priority = task.get("priority", 1)
        task_id = task.get('id', f"task-orig-{i}")
        task_name = task.get('name', f"Task {i}")

        if difficulty <= 0 or priority <= 0:
             print(f"Warning: Task '{task_name}' ({task_id}) has non-positive difficulty ({difficulty}) or priority ({priority}). Excluding from Pi check and scheduling.")
             unschedulable_tasks_info.append({
                 "id": task_id,
                 "name": task_name,
                 "reason": "Non-positive difficulty or priority",
                 "required_duration_min": None, # Indicate not applicable
                 "current_duration_min": duration_min,
             })
             continue

        stress_factor = difficulty * priority
        required_duration_min_float = stress_factor * LN_10_OVER_3
        # Round up to nearest minute for requirement
        required_duration_min_int = math.ceil(required_duration_min_float)

        if duration_min >= required_duration_min_float: # Use float for comparison accuracy
            schedulable_tasks.append(task.copy())
        else:
            reason_str = (
                f"Pi < 0.7 condition not met. Required duration: "
                f"~{required_duration_min_int} min, Actual: {duration_min} min "
                f"(based on Difficulty: {difficulty}, Priority: {priority})"
            )
            print(f"Task '{task_name}' ({task_id}) filtered out: {reason_str}")
            unschedulable_tasks_info.append({
                 "id": task_id,
                 "name": task_name,
                 "reason": reason_str,
                 "required_duration_min": required_duration_min_int, # Provide the calculated requirement
                 "current_duration_min": duration_min,
            })

    n_tasks = len(schedulable_tasks) # Number of tasks to actually schedule
    print(f"Filtered tasks: {n_tasks} tasks are schedulable (meet Pi>=0.7 condition), {len(unschedulable_tasks_info)} tasks filtered out.")

    if n_tasks == 0:
        print("Gurobi Solver: No schedulable tasks remaining after Pi filter.")
        total_possible_minutes = TOTAL_SLOTS * 15
        committed_minutes = len(commitments) * 15
        initial_leisure = total_possible_minutes - committed_minutes
        message = "No tasks provided or all tasks were filtered out."
        if unschedulable_tasks_info:
             # Example of constructing a more detailed message if needed
             filtered_names = [f"{t['name']} (needs {t['required_duration_min']}m)" for t in unschedulable_tasks_info if t['required_duration_min'] is not None]
             if filtered_names:
                  message += f" Filtered tasks needing more time: {', '.join(filtered_names)}."
             else: # Only non-positive diff/prio tasks
                  message += " Some tasks filtered due to non-positive difficulty/priority."

        return {'status': 'No Schedulable Tasks', 'schedule': [], 'total_leisure': initial_leisure, 'total_stress': 0.0, 'message': message, 'filtered_tasks_info': unschedulable_tasks_info}

    # --- Create Gurobi Model ---
    try:
        with gp.Env(empty=True) as env:
            # env.setParam('OutputFlag', 0) # Suppress Gurobi console output (optional)
            env.start()
            with gp.Model("Weekly_Scheduler", env=env) as m:
                m.setParam('OutputFlag', 0) # Suppress console output for this model
                m.setParam(GRB.Param.TimeLimit, time_limit_sec) # Set time limit

                # --- Decision variables ---
                # X[i, s] = 1 if schedulable task i starts at slot s, 0 otherwise
                X = m.addVars(n_tasks, TOTAL_SLOTS, vtype=GRB.BINARY, name="X")

                # Y[s] = 1 if slot s is occupied by *any* task, 0 otherwise
                Y = m.addVars(TOTAL_SLOTS, vtype=GRB.BINARY, name="Y")

                # L_var[s] = amount of leisure time (in minutes) in slot s
                L_var = m.addVars(TOTAL_SLOTS, vtype=GRB.CONTINUOUS, lb=0, ub=15, name="L")

                # --- Objective Function ---
                # Maximize leisure, minimize stress (using properties of schedulable tasks)
                obj_leisure = alpha * gp.quicksum(L_var[s] for s in range(TOTAL_SLOTS))
                obj_stress = beta * gp.quicksum(X[i, s] * (schedulable_tasks[i]["priority"] * schedulable_tasks[i]["difficulty"])
                                               for i in range(n_tasks) for s in range(TOTAL_SLOTS))
                m.setObjective(obj_leisure - obj_stress, GRB.MAXIMIZE)

                # --- Constraints ---
                # (a.1) Each schedulable task MUST be scheduled and have exactly one start slot
                for i in range(n_tasks):
                    m.addConstr(X.sum(i, '*') == 1, name=f"TaskMustStart_{i}")

                # (a.2) REMOVED: Target completion rate constraint (replaced by Pi filter and TaskMustStart)

                # (a.3) Hard task limitation - at most one hard task per day (among schedulable tasks)
                hard_tasks_indices = [i for i in range(n_tasks) if schedulable_tasks[i]["difficulty"] >= hard_task_threshold]
                print(f"Identified {len(hard_tasks_indices)} schedulable hard tasks with difficulty >= {hard_task_threshold}")

                for d in range(TOTAL_DAYS):
                    day_start_slot = d * SLOTS_PER_DAY
                    day_end_slot = day_start_slot + SLOTS_PER_DAY

                    # Sum of scheduled hard tasks starting within this day
                    hard_task_vars_for_day = gp.quicksum(X[i, s] for i in hard_tasks_indices
                                               for s in range(day_start_slot, day_end_slot))

                    if hard_tasks_indices:  # Only add constraint if there are hard tasks
                        m.addConstr(hard_task_vars_for_day <= 1, name=f"MaxOneHardTask_Day_{d}")
                        print(f"  Constraint Day {d}: Max 1 hard task (difficulty >= {hard_task_threshold})")

                # (a.4) REMOVED: TaskHasExactlyOneStartIfScheduled (replaced by TaskMustStart)

                # (b) Deadlines & Horizon: Task must finish by deadline and fit within horizon
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"]
                    dl = task_data["deadline_slot"]
                    task_key = task_data.get('id', i)
                    for s in range(TOTAL_SLOTS):
                        # Deadline check: last slot (s+dur-1) must be <= dl
                        if s + dur - 1 > dl:
                            m.addConstr(X[i, s] == 0, name=f"Deadline_{task_key}_s{s}")
                        # Horizon check: last slot (s+dur-1) must be < TOTAL_SLOTS
                        if s > TOTAL_SLOTS - dur:
                             m.addConstr(X[i, s] == 0, name=f"HorizonEnd_{task_key}_s{s}")

                # (c) No Overlap: At most one task can *occupy* any given slot t
                for t in range(TOTAL_SLOTS):
                    occupying_tasks_vars = []
                    for i in range(n_tasks):
                        task_data = schedulable_tasks[i]
                        dur = task_data["duration_slots"]
                        # Task i occupies slot t if it starts in s such that: s <= t < s + dur
                        for s in range(max(0, t - dur + 1), t + 1):
                             if s + dur <= TOTAL_SLOTS:
                                 occupying_tasks_vars.append(X[i, s])

                    if occupying_tasks_vars:
                         m.addConstr(gp.quicksum(occupying_tasks_vars) <= 1, name=f"NoOverlap_s{t}")

                # (d) Preferences: Task i can only start in a slot matching its preference
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    pref = task_data.get("preference", "any")
                    task_key = task_data.get('id', i)
                    if pref not in PREFERENCE_MAP:
                        print(f"Warning: Invalid preference '{pref}' for task {task_key}. Defaulting to 'any'.")
                        pref = "any"
                    allowed_slots = PREFERENCE_MAP.get(pref, PREFERENCE_MAP["any"])

                    for s in range(TOTAL_SLOTS):
                        if s not in allowed_slots:
                            m.addConstr(X[i, s] == 0, name=f"PrefWin_{task_key}_s{s}")

                # (e) Commitments: No task can start if it would overlap with a committed slot
                committed_slots = set(commitments.keys())
                for i in range(n_tasks):
                    task_data = schedulable_tasks[i]
                    dur = task_data["duration_slots"]
                    task_key = task_data.get('id', i)
                    for s in range(TOTAL_SLOTS):
                        # Slots task *would* occupy: s to s+dur-1
                        task_occupies = set(range(s, min(s + dur, TOTAL_SLOTS)))
                        if task_occupies.intersection(committed_slots):
                            m.addConstr(X[i, s] == 0, name=f"CommitOverlap_{task_key}_s{s}")

                # (f) Leisure Calculation: Link L_var with Y (task occupation) and commitments
                for s in range(TOTAL_SLOTS):
                    occupying_task_vars_sum = gp.LinExpr()
                    for i in range(n_tasks):
                        task_data = schedulable_tasks[i]
                        dur = task_data["duration_slots"]
                        for start_slot in range(max(0, s - dur + 1), s + 1):
                            if start_slot + dur <= TOTAL_SLOTS:
                                occupying_task_vars_sum.add(X[i, start_slot])

                    m.addConstr(Y[s] == occupying_task_vars_sum, name=f"Link_Y_Exact_{s}")

                    is_committed = 1 if s in commitments else 0
                    if is_committed:
                        m.addConstr(L_var[s] == 0, name=f"NoLeisure_Committed_{s}")
                    else:
                        m.addConstr(L_var[s] <= 15 * (1 - Y[s]), name=f"LeisureBound_NotCommitted_{s}")

                # (g) Daily Limits (Optional)
                if daily_limit_slots is not None and daily_limit_slots >= 0:
                    print(f"Applying daily limit of {daily_limit_slots} slots ({daily_limit_slots * 15} minutes)")
                    for d in range(TOTAL_DAYS):
                        day_start_slot = d * SLOTS_PER_DAY
                        day_end_slot = day_start_slot + SLOTS_PER_DAY
                        daily_task_slots_sum = gp.quicksum(Y[s] for s in range(day_start_slot, day_end_slot))
                        m.addConstr(daily_task_slots_sum <= daily_limit_slots, name=f"DailyLimit_Day_{d}")
                        print(f"  Constraint Day {d}: sum(Y[{day_start_slot}...{day_end_slot-1}]) <= {daily_limit_slots}")

                # --- Solve ---
                print(f"Gurobi Solver: Solving the model for {n_tasks} schedulable tasks...")
                m.optimize()
                solve_time = m.Runtime

                # --- Process Results ---
                status = m.Status
                status_map = { GRB.OPTIMAL: "Optimal", GRB.INFEASIBLE: "Infeasible", GRB.UNBOUNDED: "Unbounded", GRB.INF_OR_UNBD: "Infeasible or Unbounded", GRB.TIME_LIMIT: "Time Limit Reached", GRB.SUBOPTIMAL: "Suboptimal", }
                gurobi_status_str = status_map.get(status, f"Gurobi Status Code {status}")
                print(f"Gurobi Solver status: {gurobi_status_str} (solved in {solve_time:.2f}s)")

                final_schedule = []
                final_total_leisure = 0.0
                final_total_stress = 0.0
                scheduled_task_count = 0
                message = f"Solver status: {gurobi_status_str}."
                filtered_tasks_msg = f" {len(unschedulable_tasks_info)} tasks were filtered out before optimization due to the Pi<0.7 condition." if unschedulable_tasks_info else ""

                if status in [GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.TIME_LIMIT]:
                    if m.SolCount > 0:
                        print("Gurobi Solver: Solution found!")
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
                                        end_dt = start_dt + timedelta(minutes=dur_slots * 15)
                                        day_of_task = start_dt.date()
                                        day_end_limit = datetime.combine(day_of_task, datetime.min.time()).replace(hour=GRID_END_HOUR)

                                        if end_dt > day_end_limit:
                                            print(f"CRITICAL WARNING: Task {task_data['id']} (Start: {start_dt}, Duration: {dur_slots*15}m) calculated end time {end_dt} exceeds day limit {day_end_limit}. Clamping end time to {day_end_limit} for output. REVIEW CONSTRAINTS.")
                                            end_dt = day_end_limit

                                        record = {
                                            "id": task_data.get('id', f"task-result-{i}"),
                                            "name": task_data["name"],
                                            "priority": task_data["priority"],
                                            "difficulty": task_data["difficulty"],
                                            "start_slot": start_slot,
                                            "end_slot": end_slot,
                                            "startTime": start_dt.isoformat(),
                                            "endTime": end_dt.isoformat(),
                                            "duration_min": dur_slots * 15,
                                            "preference": task_data.get("preference", "any")
                                        }
                                        schedule_records.append(record)
                                        scheduled_task_indices_in_solver.add(i)
                                        task_scheduled_this_iter = True
                                        break # Move to next task (i)
                                except (AttributeError, gp.GurobiError) as e:
                                    print(f"Error accessing solution value for X[{i},{s}]: {e}")
                                    continue # Try next slot for this task? Or break? Let's continue

                        # Verify all schedulable tasks were indeed scheduled
                        scheduled_task_count = len(scheduled_task_indices_in_solver)
                        if scheduled_task_count != n_tasks:
                             print(f"CRITICAL WARNING: Expected {n_tasks} schedulable tasks to be scheduled, but only found {scheduled_task_count} in the solution variables. Constraint 'TaskMustStart' might conflict with others, or solution reading error.")
                             # If infeasible earlier, this part might not run anyway
                             message += f" Warning: Mismatch in expected ({n_tasks}) vs found ({scheduled_task_count}) scheduled tasks."


                        schedule_records.sort(key=lambda x: x["start_slot"])
                        final_schedule = schedule_records

                        # Calculate total leisure from L_var values
                        final_total_leisure = gp.quicksum(L_var[s].X for s in range(TOTAL_SLOTS)).getValue()

                        # Recalculate stress based on the actual scheduled tasks and their start slots
                        final_total_stress = gp.quicksum(X[i, s].X * (schedulable_tasks[i]["priority"] * schedulable_tasks[i]["difficulty"])
                                                         for i in range(n_tasks) for s in range(TOTAL_SLOTS)
                                                         if (i, s) in X and X[i,s].X > solution_threshold).getValue()

                        print(f"Gurobi Solver: Scheduled {scheduled_task_count} tasks.")
                        print(f"Gurobi Solver: Calculated Total Leisure = {final_total_leisure:.1f} minutes")
                        print(f"Gurobi Solver: Calculated Total Stress Score = {final_total_stress:.1f}")

                        message = f"Successfully scheduled {scheduled_task_count} out of {original_task_count} tasks ({gurobi_status_str})." + filtered_tasks_msg

                    else: # Status indicated solution possible, but SolCount is 0
                        print(f"Gurobi Solver: Status is {gurobi_status_str} but no solution found (SolCount=0).")
                        message = f"Solver finished with status {gurobi_status_str} but reported no feasible solution."
                        if status == GRB.TIME_LIMIT:
                             message = "Time limit reached before a feasible solution could be found."
                        message += filtered_tasks_msg


                elif status == GRB.INFEASIBLE:
                    print("Gurobi Solver: Model is infeasible.")
                    message = "Could not find a feasible schedule for the tasks meeting the Pi>=0.7 condition. Check constraints: deadlines too tight? Too many commitments? Daily limits too strict? Hard task limits conflicting? Insufficient time for mandatory tasks?" + filtered_tasks_msg
                    # Compute IIS (optional, uncomment if needed for debugging)
                    # try:
                    #     print("Computing IIS...")
                    #     m.computeIIS()
                    #     m.write("infeasible_model.ilp")
                    #     print("Wrote IIS to infeasible_model.ilp")
                    # except Exception as iis_e:
                    #     print(f"Could not compute IIS: {iis_e}")

                else: # Handle other Gurobi statuses
                     message = f"Solver finished with unhandled status: {gurobi_status_str}." + filtered_tasks_msg

                # Calculate completion rate based on original number of tasks
                completion_rate = scheduled_task_count / original_task_count if original_task_count > 0 else 0

                return {
                    "status": gurobi_status_str,
                    "schedule": final_schedule,
                    "total_leisure": round(final_total_leisure, 1),
                    "total_stress": round(final_total_stress, 1),
                    "solve_time_seconds": round(solve_time, 2),
                    "completion_rate": round(completion_rate, 2),
                    "message": message,
                    "filtered_tasks_info": unschedulable_tasks_info # Ensure this is returned
                }

    except gp.GurobiError as e:
        print(f"Gurobi Error code {e.errno}: {e}")
        # Ensure filtered_tasks_info is included even on Gurobi error
        return {"status": "Error", "message": f"Gurobi Error: {e}", "filtered_tasks_info": unschedulable_tasks_info}
    except Exception as e:
        print(f"An unexpected error occurred during Gurobi optimization: {e}")
        print(traceback.format_exc())
        # Ensure filtered_tasks_info is included even on unexpected error
        return {"status": "Error", "message": f"Unexpected error during optimization: {e}", "filtered_tasks_info": unschedulable_tasks_info}
