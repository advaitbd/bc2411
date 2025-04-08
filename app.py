# bc2411/app.py
# Add imports for random generation logic if not already present
import random
import math
import traceback # For detailed error logging

# --- CHANGE HERE: Import the Gurobi solver function ---
from allocation_logic import (
    # solve_schedule_pulp, # Remove or comment out PuLP import
    solve_schedule_gurobi,  # Import the new Gurobi function
    datetime_to_slot,
    slot_to_datetime,
    get_day0,
    TOTAL_SLOTS,
    SLOTS_PER_DAY,
    PREFERENCE_MAP, # Needed for generation
    TOTAL_DAYS # Needed for generation
)

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta, timezone # Make sure timezone is imported

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# ------------------------------------------------------------
# AUTO-GENERATION LOGIC (Unchanged)
# ------------------------------------------------------------
# ... (auto_generate_tasks and auto_generate_blocked functions remain the same) ...
def auto_generate_tasks(num_tasks=10):
    """
    Generate student-specific tasks within the next 7 days.
    Returns tasks in the format expected by the API/Solver.
    Deadlines are returned as naive local ISO strings.
    """
    print(f"--- Running auto_generate_tasks (num_tasks={num_tasks}) ---")
    task_types = [
        ("Assignment", 3, 5, 60),           # (type, avg priority, avg difficulty, avg duration_min)
        ("Study Session", 2, 2, 45),
        ("Group Project", 4, 4, 60),
        ("Reading", 2, 2, 30),
        ("Homework", 3, 3, 30),
        ("Essay", 4, 4, 90),
        ("Lab Report", 4, 5, 60),
        ("Exam Prep", 5, 4, 75),
        ("Research", 3, 3, 45),
        ("Presentation Prep", 4, 3, 45)
    ]
    courses = [
        "Math 101", "Computer Science 202", "Physics 150", "English 105",
        "History 201", "Chemistry 110", "Economics 230", "Psychology 120"
    ]
    pref_choices = ["morning", "afternoon", "evening", "any"] # Added 'any'

    tasks = []
    day0 = get_day0() # Get reference date (naive local)

    for i in range(num_tasks):
        task_type, base_prio, base_diff, base_dur_min = random.choice(task_types)
        course = random.choice(courses)
        name = f"{task_type} - {course}"

        prio = max(1, min(5, int(base_prio + random.randint(-1, 1))))
        diff = max(1, min(5, int(base_diff + random.randint(-1, 1))))
        # Duration variation: +/- 15 mins, minimum 15 mins
        duration_min = max(15, int(base_dur_min + random.choice([-15, 0, 15])))

        # Determine deadline day (relative to day0)
        if task_type in ["Group Project", "Essay", "Research"]:
            deadline_day_relative = random.randint(4, TOTAL_DAYS - 1) # Day index 4, 5, or 6
        elif task_type in ["Exam Prep", "Lab Report"]:
            deadline_day_relative = random.randint(1, 3) # Day index 1, 2, or 3
        else:
            deadline_day_relative = random.randint(2, 5) # Day index 2, 3, 4, or 5

        # Calculate absolute deadline date (end of that day)
        deadline_date = day0 + timedelta(days=deadline_day_relative)
        # Set time to 21:59:59 on that day (local naive)
        deadline_dt = deadline_date.replace(hour=21, minute=59, second=59, microsecond=999999)
        deadline_iso_local = deadline_dt.isoformat() # NO 'Z'

        # Set Preference
        if task_type in ["Study Session", "Reading", "Research"]:
            pref = random.choice(pref_choices)
        elif task_type in ["Exam Prep", "Presentation Prep"]:
            pref = random.choice(["morning", "morning", "afternoon", "any"])
        else: # Assignments, Homework, etc.
            pref = random.choice(["afternoon", "evening", "any", "any"])

        tasks.append({
            "id": f"task-gen-{i+1}", # Add an ID for frontend keys
            "name": name,
            "priority": prio,
            "difficulty": diff,
            "duration_min": duration_min,
            "deadline": deadline_iso_local, # Send naive local ISO string
            "preference": pref
        })
    print(f"Generated {len(tasks)} tasks.")
    return tasks

def auto_generate_blocked(n_intervals=8):
    """
    Randomly block out intervals in the 7-day horizon.
    Returns commitments in the format expected by the Frontend (naive local ISO start/end times).
    """
    print(f"--- Running auto_generate_blocked (n_intervals={n_intervals}) ---")
    blocked_intervals = []
    day0 = get_day0() # Get reference date (naive local)
    interval_id_counter = 1

    # Function to add an interval
    def add_block(start_dt_local, end_dt_local, activity_name):
        nonlocal interval_id_counter
        # Ensure start is before end
        if end_dt_local <= start_dt_local:
            return
        # Ensure times are within the 7-day horizon (basic check using naive local times)
        horizon_end = day0 + timedelta(days=TOTAL_DAYS)
        if start_dt_local >= horizon_end or end_dt_local <= day0:
            return

        blocked_intervals.append({
            "id": f"block-gen-{interval_id_counter}",
            "startTime": start_dt_local.isoformat(), # NO 'Z'
            "endTime": end_dt_local.isoformat(),   # NO 'Z'
            "activity": activity_name
        })
        interval_id_counter += 1

    # 1. Generate fixed class schedule (M/W/F and T/Th) - Times are local
    class_times_mwf = [
        (9, 0, 50, "Math 101"), (11, 0, 50, "Physics 150"), (14, 0, 50, "English 105")
    ]
    class_times_tth = [
        (9, 30, 75, "CS 202"), (13, 0, 75, "History 201")
    ]

    for day_offset in [0, 2, 4]: # M/W/F
        base_date = day0 + timedelta(days=day_offset)
        for h, m, dur, name in class_times_mwf:
            start_local = base_date.replace(hour=h, minute=m, second=0, microsecond=0)
            end_local = start_local + timedelta(minutes=dur)
            add_block(start_local, end_local, f"Class: {name}")

    for day_offset in [1, 3]: # T/Th
        base_date = day0 + timedelta(days=day_offset)
        for h, m, dur, name in class_times_tth:
            start_local = base_date.replace(hour=h, minute=m, second=0, microsecond=0)
            end_local = start_local + timedelta(minutes=dur)
            add_block(start_local, end_local, f"Class: {name}")

    # 2. Add daily meals (consistent local times)
    for day in range(TOTAL_DAYS):
        base_date = day0 + timedelta(days=day)
        add_block(base_date.replace(hour=8, minute=0), base_date.replace(hour=8, minute=30), "Breakfast")
        add_block(base_date.replace(hour=12, minute=0), base_date.replace(hour=12, minute=45), "Lunch")
        add_block(base_date.replace(hour=18, minute=0), base_date.replace(hour=19, minute=0), "Dinner")

    # 3. Add some semi-fixed weekly activities (local times)
    add_block(day0.replace(hour=16, minute=0), day0.replace(hour=17, minute=30), "Club Meeting") # Mon
    add_block((day0 + timedelta(days=2)).replace(hour=17, minute=0), (day0 + timedelta(days=2)).replace(hour=18, minute=30), "Study Group") # Wed
    add_block((day0 + timedelta(days=4)).replace(hour=19, minute=0), (day0 + timedelta(days=4)).replace(hour=22, minute=0), "Social Activity") # Fri
    add_block((day0 + timedelta(days=5)).replace(hour=10, minute=0), (day0 + timedelta(days=5)).replace(hour=13, minute=0), "Errands") # Sat

    # 4. Add a few random commitments (local times)
    random_events = ["Doctor Appointment", "Meeting", "Phone Call", "Gym", "Commute", "Volunteering"]
    num_random = max(0, n_intervals - 8)
    for _ in range(num_random):
        day = random.randint(0, TOTAL_DAYS - 1)
        hour = random.randint(8, 20)
        minute = random.choice([0, 15, 30, 45])
        duration_min = random.choice([30, 45, 60, 75, 90, 120])
        event_name = random.choice(random_events)

        start_local = (day0 + timedelta(days=day)).replace(hour=hour, minute=minute)
        end_local = start_local + timedelta(minutes=duration_min)
        end_limit = start_local.replace(hour=22, minute=0)
        if end_local > end_limit:
            end_local = end_limit
        add_block(start_local, end_local, event_name)

    print(f"Generated {len(blocked_intervals)} blocked intervals.")
    return blocked_intervals

# ------------------------------------------------------------
# API ENDPOINTS
# ------------------------------------------------------------

# Helper function parse_datetime_to_naive_local (Unchanged)
def parse_datetime_to_naive_local(dt_str):
    """
    Parses various ISO-like string formats from frontend into naive local datetime.
    Handles 'Z' and offsets by converting to local time first.
    """
    if not dt_str:
        return None
    try:
        if dt_str.endswith('Z'):
            dt_aware = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            dt_naive_local = dt_aware.astimezone(None).replace(tzinfo=None)
            return dt_naive_local
        if '+' in dt_str[10:] or '-' in dt_str[10:]:
             try:
                 dt_aware = datetime.fromisoformat(dt_str)
                 dt_naive_local = dt_aware.astimezone(None).replace(tzinfo=None)
                 return dt_naive_local
             except ValueError:
                 print(f"  Warning: Direct parsing failed for offset string '{dt_str}', attempting fallback.")
                 pass
        if '.' in dt_str:
             dt_str = dt_str.split('.')[0]
        dt_naive_local = datetime.fromisoformat(dt_str)
        return dt_naive_local
    except Exception as e:
        print(f"Error parsing datetime string '{dt_str}' to naive local: {e}")
        return None


@app.route('/api/auto-generate', methods=['GET'])
def auto_generate_data():
    """Generates sample tasks and blocked intervals."""
    _ = get_day0() # Ensure DAY0 is initialized
    print(f"\n--- Received request for /api/auto-generate at {datetime.now()} ---")
    print(f"Reference DAY0 (naive local): {get_day0()}")
    try:
        tasks = auto_generate_tasks(num_tasks=random.randint(5, 8))
        blocked = auto_generate_blocked(n_intervals=random.randint(8, 12))
        return jsonify({
            "tasks": tasks,
            "blockedIntervals": blocked
        })
    except Exception as e:
        print(f"Error in /api/auto-generate: {e}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to auto-generate data."}), 500


@app.route('/api/optimize', methods=['POST'])
def optimize_schedule():
    _ = get_day0() # Ensure DAY0 is initialized
    print(f"\n--- Received request for /api/optimize at {datetime.now()} ---")
    print(f"Reference DAY0 (naive local): {get_day0()}")

    try:
        data = request.get_json()
        if not data:
            print("Error: Invalid or empty JSON payload received.")
            return jsonify({"error": "Invalid JSON payload"}), 400

        print("Received data:", data)

        tasks_input = data.get('tasks', [])
        blocked_input = data.get('blockedIntervals', [])
        settings_input = data.get('settings', {})
        start_hour_pref = settings_input.get('startHour', 8)
        end_hour_pref = settings_input.get('endHour', 22)
        # Note: start/end hour prefs are not used by the solver directly yet
        print(f"Frontend Time Window Preference: {start_hour_pref:02d}:00 - {end_hour_pref:02d}:00")

        # --- 1. Parse and Validate Tasks (Logic Unchanged) ---
        parsed_tasks = []
        task_errors = []
        day0_ref = get_day0()

        for idx, t in enumerate(tasks_input):
            task_id = t.get('id', f'task-input-{idx+1}')
            name = t.get('name')
            priority = t.get('priority')
            difficulty = t.get('difficulty', 1) # Get difficulty from frontend if available
            duration_min = t.get('duration')
            deadline_input = t.get('deadline')
            preference = t.get('preference', 'any')

            if not name:
                task_errors.append(f"Task {idx+1}: Name is missing.")
                continue
            try:
                priority = int(priority) if priority is not None else 1
                difficulty = int(difficulty) if difficulty is not None else 1
                duration_min = int(duration_min) if duration_min is not None else 15
                if duration_min <= 0:
                    task_errors.append(f"Task '{name}': Duration must be positive.")
                    continue
                priority = max(1, min(priority, 5))
                difficulty = max(1, min(difficulty, 5)) # Clamp difficulty too
            except (ValueError, TypeError):
                task_errors.append(f"Task '{name}': Priority, difficulty, and duration must be numbers.")
                continue

            # --- Deadline Parsing (Logic Unchanged) ---
            deadline_dt_local = None
            deadline_slot = TOTAL_SLOTS - 1
            if isinstance(deadline_input, (int, float)):
                relative_days = int(deadline_input)
                if relative_days >= 0:
                    deadline_date = day0_ref + timedelta(days=relative_days)
                    deadline_dt_local = deadline_date.replace(hour=21, minute=59, second=59, microsecond=999999)
                    print(f"Task '{name}': Relative deadline {relative_days} days -> Local Deadline DT: {deadline_dt_local}")
                else:
                    task_errors.append(f"Task '{name}': Relative deadline days must be non-negative.")
                    continue
            elif isinstance(deadline_input, str):
                deadline_dt_local = parse_datetime_to_naive_local(deadline_input)
                if not deadline_dt_local:
                    task_errors.append(f"Task '{name}': Invalid deadline format '{deadline_input}'.")
                    continue
                print(f"Task '{name}': Parsed deadline string '{deadline_input}' -> Local Deadline DT: {deadline_dt_local}")
            else:
                task_errors.append(f"Task '{name}': Deadline is missing or has invalid type.")
                continue

            if deadline_dt_local:
                if deadline_dt_local < day0_ref:
                     task_errors.append(f"Task '{name}': Deadline ({deadline_dt_local.strftime('%Y-%m-%d %H:%M')}) cannot be in the past relative to DAY0 ({day0_ref.strftime('%Y-%m-%d %H:%M')}).")
                     continue
                deadline_slot = datetime_to_slot(deadline_dt_local)
                print(f"  Converted local deadline to slot: {deadline_slot}")

            duration_slots = math.ceil(duration_min / 15.0)
            if duration_slots <= 0: duration_slots = 1

            if deadline_slot < duration_slots - 1:
                 effective_deadline_time = slot_to_datetime(deadline_slot) + timedelta(minutes=15)
                 task_errors.append(f"Task '{name}': Deadline ({effective_deadline_time.strftime('%Y-%m-%d %H:%M')}, slot {deadline_slot}) is too early for the duration ({duration_min} min / {duration_slots} slots). Minimum required end slot: {duration_slots - 1}")
                 continue

            parsed_tasks.append({
                "id": task_id,
                "name": name,
                "priority": priority,
                "difficulty": difficulty, # Pass difficulty to solver
                "duration_slots": duration_slots,
                "deadline_slot": deadline_slot,
                "preference": preference.lower() if preference else 'any'
            })

        # --- 2. Parse Blocked Intervals (Logic Unchanged) ---
        parsed_commitments = {}
        commitment_errors = []
        for idx, block in enumerate(blocked_input):
            block_id = block.get('id', f'block-input-{idx+1}')
            start_str = block.get('startTime')
            end_str = block.get('endTime')
            activity = block.get('activity', f'Blocked {idx+1}')

            if not start_str or not end_str:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Start and end times are required.")
                continue

            start_dt_local = parse_datetime_to_naive_local(start_str)
            end_dt_local = parse_datetime_to_naive_local(end_str)

            if not start_dt_local or not end_dt_local:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Invalid time format (Start: '{start_str}', End: '{end_str}').")
                continue

            if end_dt_local <= start_dt_local:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): End time ({end_dt_local}) must be after start time ({start_dt_local}).")
                continue

            start_slot = datetime_to_slot(start_dt_local)
            end_slot_inclusive = datetime_to_slot(end_dt_local - timedelta(microseconds=1))
            effective_start_slot = max(0, start_slot)
            effective_end_slot = min(TOTAL_SLOTS - 1, end_slot_inclusive)

            if effective_start_slot <= effective_end_slot:
                print(f"Blocking slots for '{activity}': Local {start_dt_local.strftime('%H:%M')}-{end_dt_local.strftime('%H:%M')} -> Slots {effective_start_slot} to {effective_end_slot}")
                for s in range(effective_start_slot, effective_end_slot + 1):
                    parsed_commitments[s] = 15 # Mark slot as blocked (value doesn't strictly matter, just existence)
            else:
                 print(f"Warning: Blocked Interval '{activity}' ({block_id}) resulted in invalid slot range ({start_slot} to {end_slot_inclusive}) after conversion. Local Times: {start_dt_local} to {end_dt_local}. May be outside the 8am-10pm window or 7-day horizon.")

        # --- 3. Parse Settings (Logic Unchanged) ---
        settings_errors = []
        alpha=1.0
        beta=0.1
        daily_limit_slots = None # Default no limit (can be overridden by settings if implemented)
        # Example: override daily limit from settings if provided
        # try:
        #    limit_input = settings_input.get('dailyTaskLimitHours')
        #    if limit_input is not None:
        #        daily_limit_slots = int(float(limit_input) * 4) # Convert hours to slots
        #        if daily_limit_slots < 0: daily_limit_slots = None # Ignore negative limits
        # except (ValueError, TypeError):
        #    settings_errors.append("Invalid format for daily task limit.")

        # --- Combine Errors and Check (Logic Unchanged) ---
        all_errors = task_errors + commitment_errors + settings_errors
        if task_errors:
             print(f"Error: Found {len(task_errors)} errors in task definitions. Aborting.")
             return jsonify({"error": "Errors found in task definitions.", "details": task_errors}), 400
        if commitment_errors:
             print(f"Warning: Found {len(commitment_errors)} issues processing blocked intervals:")
             for err in commitment_errors: print(f"  - {err}")
        if settings_errors:
             print(f"Warning: Found {len(settings_errors)} issues processing settings:")
             for err in settings_errors: print(f"  - {err}")

        # --- Call Solver ---
        # --- CHANGE HERE: Call the Gurobi function ---
        if not parsed_tasks:
             total_possible_minutes = TOTAL_SLOTS * 15
             committed_minutes = len(parsed_commitments) * 15
             initial_leisure = total_possible_minutes - committed_minutes
             results = {'status': 'Optimal', 'schedule': [], 'total_leisure': initial_leisure, 'total_stress': 0.0, 'message': 'No valid tasks provided to schedule.'}
             print("No valid tasks provided. Returning baseline leisure.")
        else:
             print(f"\nCalling Gurobi solver with {len(parsed_tasks)} tasks, {len(parsed_commitments)} commitment slots...")
             results = solve_schedule_gurobi( # Changed function name
                 tasks=parsed_tasks,
                 commitments=parsed_commitments,
                 alpha=alpha,
                 beta=beta,
                 daily_limit_slots=daily_limit_slots
                 # time_limit_sec=30 # Can pass time limit if needed
             )

        # --- Post-processing (Logic Unchanged) ---
        warnings = commitment_errors + settings_errors
        if warnings:
            results['warnings'] = results.get('warnings', []) + warnings

        # Add task IDs back (already handled within solve_schedule_gurobi)
        # Verify results format is okay
        if "schedule" not in results:
            results["schedule"] = [] # Ensure schedule key exists even on error/infeasibility

        print(f"\n--- Request completed. Solver status: {results.get('status', 'N/A')} ---")
        return jsonify(results)

    except Exception as e:
        print(f"Error processing /api/optimize request: {e}")
        print(traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred on the server."}), 500

if __name__ == '__main__':
    print("Starting Flask server for Schedule Optimizer API...")
    _ = get_day0() # Initialize DAY0 on startup
    print(f"Reference Day 0 (Naive Local 8am): {get_day0()}")
    print(f"Using Gurobi for optimization.") # Add note about solver
    app.run(host='0.0.0.0', port=5001, debug=True)
