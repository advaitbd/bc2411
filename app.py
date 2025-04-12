# bc2411/app.py
import random
import math
import traceback # For detailed error logging

# --- Import necessary functions ---
from allocation_logic_deadline_penalty import (
    solve_schedule_gurobi,
    datetime_to_slot,
    slot_to_datetime,
    get_day0_ref_midnight,
    TOTAL_DAYS, # Keep this global constant
    calculate_dynamic_config # Import the config calculator
)

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta, timezone # Make sure timezone is imported

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Define Default Hours (used for auto-generation and as fallback)
DEFAULT_START_HOUR = 8
DEFAULT_END_HOUR = 22

# ------------------------------------------------------------
# AUTO-GENERATION LOGIC (Modified to use default hours for helpers)
# ------------------------------------------------------------
def auto_generate_tasks(num_tasks=10):
    """
    Generate student-specific tasks within the next 7 days.
    Uses DEFAULT hours for deadline calculations.
    """
    print(f"--- Running auto_generate_tasks (num_tasks={num_tasks}) ---")
    task_types = [
        ("Assignment", 3, 5, 60), ("Study Session", 2, 2, 45),
        ("Group Project", 4, 4, 60), ("Reading", 2, 2, 30),
        ("Homework", 3, 3, 30), ("Essay", 4, 4, 90),
        ("Lab Report", 4, 5, 60), ("Exam Prep", 5, 4, 75),
        ("Research", 3, 3, 45), ("Presentation Prep", 4, 3, 45)
    ]
    courses = [
        "Math 101", "Computer Science 202", "Physics 150", "English 105",
        "History 201", "Chemistry 110", "Economics 230", "Psychology 120"
    ]
    pref_choices = ["morning", "afternoon", "evening", "any"]

    tasks = []
    # Use default hours for generation logic's date reference
    day0_ref_midnight = get_day0_ref_midnight()
    day0_default_start = day0_ref_midnight.replace(hour=DEFAULT_START_HOUR)

    for i in range(num_tasks):
        task_type, base_prio, base_diff, base_dur_min = random.choice(task_types)
        course = random.choice(courses)
        name = f"{task_type} - {course}"

        prio = max(1, min(5, int(base_prio + random.randint(-1, 1))))
        diff = max(1, min(5, int(base_diff + random.randint(-1, 1))))
        duration_min = max(15, int(base_dur_min + random.choice([-15, 0, 15])))

        if task_type in ["Group Project", "Essay", "Research"]:
            deadline_day_relative = random.randint(4, TOTAL_DAYS - 1)
        elif task_type in ["Exam Prep", "Lab Report"]:
            deadline_day_relative = random.randint(1, 3)
        else:
            deadline_day_relative = random.randint(2, 5)

        # Deadline relative to the start of Day 0 (using default start hour)
        deadline_date = day0_default_start + timedelta(days=deadline_day_relative)
        # Set deadline to a reasonable time like end of day
        deadline_dt = deadline_date.replace(hour=21, minute=59, second=59, microsecond=999999)
        deadline_iso_local = deadline_dt.isoformat()

        if task_type in ["Study Session", "Reading", "Research"]:
            pref = random.choice(pref_choices)
        elif task_type in ["Exam Prep", "Presentation Prep"]:
            pref = random.choice(["morning", "morning", "afternoon", "any"])
        else: # Assignments, Homework, etc.
            pref = random.choice(["afternoon", "evening", "any", "any"])

        tasks.append({
            "id": f"task-gen-{i+1}",
            "name": name,
            "priority": prio,
            "difficulty": diff,
            "duration": duration_min, # Use 'duration' field
            "deadline": deadline_iso_local,
            "preference": pref
        })
    print(f"Generated {len(tasks)} tasks.")
    return tasks

def auto_generate_blocked(n_intervals=8):
    """
    Randomly block out intervals in the 7-day horizon.
    Uses DEFAULT hours for date reference.
    """
    print(f"--- Running auto_generate_blocked (n_intervals={n_intervals}) ---")
    blocked_intervals = []
    day0_ref_midnight = get_day0_ref_midnight() # Use midnight ref
    day0_default_start = day0_ref_midnight.replace(hour=DEFAULT_START_HOUR)
    interval_id_counter = 1

    def add_block(start_dt_local, end_dt_local, activity_name):
        nonlocal interval_id_counter
        if end_dt_local <= start_dt_local: return
        horizon_end = day0_default_start + timedelta(days=TOTAL_DAYS)
        if start_dt_local >= horizon_end or end_dt_local <= day0_default_start: return

        blocked_intervals.append({
            "id": f"block-gen-{interval_id_counter}",
            "startTime": start_dt_local.isoformat(),
            "endTime": end_dt_local.isoformat(),
            "activity": activity_name
        })
        interval_id_counter += 1

    # Fixed schedule relative to Day 0 midnight
    class_times_mwf = [(9, 0, 50, "Math 101"), (11, 0, 50, "Physics 150"), (14, 0, 50, "English 105")]
    class_times_tth = [(9, 30, 75, "CS 202"), (13, 0, 75, "History 201")]

    for day_offset in [0, 2, 4]: # M/W/F relative to day 0 midnight
        base_date = day0_ref_midnight + timedelta(days=day_offset)
        for h, m, dur, name in class_times_mwf:
            start_local = base_date.replace(hour=h, minute=m)
            end_local = start_local + timedelta(minutes=dur)
            add_block(start_local, end_local, f"Class: {name}")

    for day_offset in [1, 3]: # T/Th relative to day 0 midnight
        base_date = day0_ref_midnight + timedelta(days=day_offset)
        for h, m, dur, name in class_times_tth:
            start_local = base_date.replace(hour=h, minute=m)
            end_local = start_local + timedelta(minutes=dur)
            add_block(start_local, end_local, f"Class: {name}")

    # Daily meals relative to Day 0 midnight
    for day in range(TOTAL_DAYS):
        base_date = day0_ref_midnight + timedelta(days=day)
        add_block(base_date.replace(hour=8, minute=0), base_date.replace(hour=8, minute=30), "Breakfast")
        add_block(base_date.replace(hour=12, minute=0), base_date.replace(hour=12, minute=45), "Lunch")
        add_block(base_date.replace(hour=18, minute=0), base_date.replace(hour=19, minute=0), "Dinner")

    # Semi-fixed relative to Day 0 midnight
    add_block(day0_ref_midnight.replace(hour=16, minute=0), day0_ref_midnight.replace(hour=17, minute=30), "Club Meeting") # Mon
    add_block((day0_ref_midnight + timedelta(days=2)).replace(hour=17, minute=0), (day0_ref_midnight + timedelta(days=2)).replace(hour=18, minute=30), "Study Group") # Wed
    add_block((day0_ref_midnight + timedelta(days=4)).replace(hour=19, minute=0), (day0_ref_midnight + timedelta(days=4)).replace(hour=22, minute=0), "Social Activity") # Fri
    add_block((day0_ref_midnight + timedelta(days=5)).replace(hour=10, minute=0), (day0_ref_midnight + timedelta(days=5)).replace(hour=13, minute=0), "Errands") # Sat

    # Random commitments relative to Day 0 midnight
    random_events = ["Doctor Appointment", "Meeting", "Phone Call", "Gym", "Commute", "Volunteering"]
    num_random = max(0, n_intervals - 8)
    for _ in range(num_random):
        day = random.randint(0, TOTAL_DAYS - 1)
        hour = random.randint(DEFAULT_START_HOUR, DEFAULT_END_HOUR - 2) # Ensure end time is possible
        minute = random.choice([0, 15, 30, 45])
        duration_min = random.choice([30, 45, 60, 75, 90, 120])
        event_name = random.choice(random_events)

        start_local = (day0_ref_midnight + timedelta(days=day)).replace(hour=hour, minute=minute)
        end_local = start_local + timedelta(minutes=duration_min)
        end_limit = start_local.replace(hour=DEFAULT_END_HOUR, minute=0) # Clamp to default end hour
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
    if not dt_str: return None
    try:
        if dt_str.endswith('Z'):
            dt_aware = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt_aware.astimezone(None).replace(tzinfo=None)
        if '+' in dt_str[10:] or '-' in dt_str[10:]:
             try:
                 dt_aware = datetime.fromisoformat(dt_str)
                 return dt_aware.astimezone(None).replace(tzinfo=None)
             except ValueError: pass
        if '.' in dt_str: dt_str = dt_str.split('.')[0]
        return datetime.fromisoformat(dt_str) # Assumes local if no offset/Z
    except Exception as e:
        print(f"Error parsing datetime string '{dt_str}' to naive local: {e}")
        return None

@app.route('/api/auto-generate', methods=['GET'])
def auto_generate_data():
    _ = get_day0_ref_midnight() # Ensure DAY0 ref is initialized
    print(f"\n--- Received request for /api/auto-generate at {datetime.now()} ---")
    print(f"Reference DAY0 Midnight (naive local): {get_day0_ref_midnight()}")
    try:
        tasks = auto_generate_tasks(num_tasks=random.randint(5, 8))
        blocked = auto_generate_blocked(n_intervals=random.randint(8, 12))
        return jsonify({ "tasks": tasks, "blockedIntervals": blocked })
    except Exception as e:
        print(f"Error in /api/auto-generate: {e}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to auto-generate data."}), 500

@app.route('/api/optimize', methods=['POST'])
def optimize_schedule():
    day0_ref = get_day0_ref_midnight() # Initialize if needed
    print(f"\n--- Received request for /api/optimize at {datetime.now()} ---")
    print(f"Reference DAY0 Midnight (naive local): {day0_ref}")

    try:
        data = request.get_json()
        if not data:
            print("Error: Invalid or empty JSON payload received.")
            return jsonify({"error": "Invalid JSON payload"}), 400

        print("Received data:", data)

        tasks_input = data.get('tasks', [])
        blocked_input = data.get('blockedIntervals', [])
        settings_input = data.get('settings', {})

        # --- Get Start/End Hours from Settings ---
        start_hour = settings_input.get('startHour', DEFAULT_START_HOUR)
        end_hour = settings_input.get('endHour', DEFAULT_END_HOUR)

        # --- Validate Hours and Calculate Dynamic Config ---
        try:
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            slots_per_day, total_slots = calculate_dynamic_config(start_hour, end_hour)
            print(f"Using dynamic window: {start_hour}:00 - {end_hour}:00 ({slots_per_day} slots/day, {total_slots} total)")
        except (ValueError, TypeError) as e:
            print(f"Error: Invalid start/end hours received: {start_hour}, {end_hour}. {e}")
            return jsonify({"error": f"Invalid start/end hours in settings: {e}"}), 400

        # Define actual start time based on dynamic start hour
        day0_actual_start = day0_ref.replace(hour=start_hour)

        parsed_tasks = []
        task_errors = []
        for idx, t in enumerate(tasks_input):
            task_id = t.get('id', f'task-input-{idx+1}')
            name = t.get('name')
            priority = t.get('priority')
            difficulty = t.get('difficulty')
            duration_min_input = t.get('duration')
            deadline_input = t.get('deadline')
            preference = t.get('preference', 'any')

            # Basic Validation
            if not name: task_errors.append(f"Task {idx+1}: Name is missing."); continue
            try:
                priority = int(priority) if priority is not None else 1
                difficulty = int(difficulty) if difficulty is not None else 1
                duration_min = int(duration_min_input) if duration_min_input is not None else 15
                if duration_min <= 0: task_errors.append(f"Task '{name}': Duration must be positive."); continue
                priority = max(1, min(priority, 5))
                difficulty = max(1, min(difficulty, 5))
            except (ValueError, TypeError):
                task_errors.append(f"Task '{name}': Priority, difficulty, or duration is not a valid number."); continue

            # --- Deadline Parsing ---
            deadline_dt_local = None
            # Default deadline slot is the last possible slot in the dynamic grid
            deadline_slot = total_slots - 1 if total_slots > 0 else 0
            if isinstance(deadline_input, (int, float)): # Relative days
                relative_days = int(deadline_input)
                if relative_days >= 0:
                    # Deadline relative to the *actual* start of the day0 schedule
                    deadline_date = day0_actual_start + timedelta(days=relative_days)
                    # Set deadline time to be the grid end hour on that day
                    deadline_dt_local = deadline_date.replace(hour=end_hour, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
                    print(f"Task '{name}': Relative deadline {relative_days} days -> Local Deadline DT: {deadline_dt_local}")
                else: task_errors.append(f"Task '{name}': Relative deadline days must be non-negative."); continue
            elif isinstance(deadline_input, str): # ISO string
                deadline_dt_local = parse_datetime_to_naive_local(deadline_input)
                if not deadline_dt_local: task_errors.append(f"Task '{name}': Invalid deadline format '{deadline_input}'."); continue
                print(f"Task '{name}': Parsed deadline string '{deadline_input}' -> Local Deadline DT: {deadline_dt_local}")
            else: task_errors.append(f"Task '{name}': Deadline is missing or has invalid type."); continue

            if deadline_dt_local:
                # Deadline cannot be before the actual start of the schedule
                if deadline_dt_local < day0_actual_start: task_errors.append(f"Task '{name}': Deadline cannot be before schedule start ({day0_actual_start})."); continue
                # Convert deadline to slot using dynamic config
                deadline_slot = datetime_to_slot(deadline_dt_local, start_hour, end_hour, slots_per_day, total_slots)
                print(f"  Converted local deadline to slot: {deadline_slot}")

            # --- Convert duration_min to duration_slots ---
            duration_slots = math.ceil(duration_min / 15.0)
            if duration_slots <= 0: duration_slots = 1

            # Check if deadline is feasible for duration
            if deadline_slot < duration_slots - 1:
                # Convert deadline slot back to time for user message
                try:
                     effective_deadline_time = slot_to_datetime(deadline_slot, start_hour, slots_per_day, total_slots) + timedelta(minutes=15) # End of the deadline slot
                     task_errors.append(f"Task '{name}': Deadline ({effective_deadline_time.strftime('%Y-%m-%d %H:%M')}, slot {deadline_slot}) is too early for the duration ({duration_min} min / {duration_slots} slots).")
                except ValueError: # Handle cases where slot might be invalid if total_slots=0
                     task_errors.append(f"Task '{name}': Deadline (slot {deadline_slot}) is too early for the duration ({duration_min} min / {duration_slots} slots). Error getting time.")
                continue

            parsed_tasks.append({
                "id": task_id,
                "name": name,
                "priority": priority,
                "difficulty": difficulty,
                "duration_slots": duration_slots, # Pass slots to solver
                "deadline_slot": deadline_slot,
                "preference": preference.lower() if preference else 'any'
            })

        # --- Parse Commitments ---
        parsed_commitments = {}
        commitment_errors = []
        for idx, block in enumerate(blocked_input):
            block_id = block.get('id', f'block-input-{idx+1}')
            start_str = block.get('startTime')
            end_str = block.get('endTime')
            activity = block.get('activity', f'Blocked {idx+1}')

            if not start_str or not end_str:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Start/end times required.")
                continue

            start_dt_local = parse_datetime_to_naive_local(start_str)
            end_dt_local = parse_datetime_to_naive_local(end_str)

            if not start_dt_local or not end_dt_local:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Invalid time format.")
                continue

            if end_dt_local <= start_dt_local:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): End time must be after start time.")
                continue

            # Convert commitment times to slots using dynamic config
            start_slot = datetime_to_slot(start_dt_local, start_hour, end_hour, slots_per_day, total_slots)
            # Subtract microsecond to get the slot containing the moment *just before* the end time
            end_slot_inclusive = datetime_to_slot(end_dt_local - timedelta(microseconds=1), start_hour, end_hour, slots_per_day, total_slots)

            # Clamp slots to the valid range for the dynamic grid
            effective_start_slot = max(0, start_slot)
            effective_end_slot = min(total_slots - 1, end_slot_inclusive) if total_slots > 0 else -1

            if effective_start_slot <= effective_end_slot:
                print(f"Blocking slots for '{activity}': Local {start_dt_local.strftime('%H:%M')}-{end_dt_local.strftime('%H:%M')} -> Slots {effective_start_slot} to {effective_end_slot}")
                for s in range(effective_start_slot, effective_end_slot + 1):
                    parsed_commitments[s] = 15 # Mark slot as blocked
            else:
                 print(f"Warning: Blocked Interval '{activity}' ({block_id}) resulted in invalid slot range ({start_slot} to {end_slot_inclusive}) after conversion. Local Times: {start_dt_local} to {end_dt_local}. May be outside the {start_hour}:00-{end_hour}:00 window or 7-day horizon.")

        # --- Parse Other Settings (e.g., Daily Limit - currently unused) ---
        settings_errors = []
        alpha = 1 # Default, could be overridden by settings
        beta = 0.1  # Default, could be overridden by settings
        daily_limit_slots = None # Default no limit

        # --- Combine Errors and Check ---
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

        # --- Call Solver with Dynamic Hours ---
        if not parsed_tasks:
             # Calculate initial leisure based on dynamic grid size
             total_possible_minutes = total_slots * 15
             committed_minutes = len(parsed_commitments) * 15
             initial_leisure = max(0, total_possible_minutes - committed_minutes)
             results = {'status': 'Optimal', 'schedule': [], 'total_leisure': initial_leisure, 'total_stress': 0.0, 'message': 'No valid tasks provided to schedule.'}
             print("No valid tasks provided. Returning baseline leisure.")
        else:
             print(f"\nCalling Gurobi solver with {len(parsed_tasks)} tasks, {len(parsed_commitments)} commitments...")
             results = solve_schedule_gurobi(
                 tasks=parsed_tasks,
                 commitments=parsed_commitments,
                 alpha=alpha,
                 beta=beta,
                 daily_limit_slots=daily_limit_slots,
                 start_hour=start_hour, # Pass dynamic hours
                 end_hour=end_hour      # Pass dynamic hours
             )

        # --- Post-processing (Add warnings) ---
        warnings = commitment_errors + settings_errors
        if warnings:
            results['warnings'] = results.get('warnings', []) + warnings

        if "schedule" not in results:
            results["schedule"] = [] # Ensure key exists

        print(f"\n--- Request completed. Solver status: {results.get('status', 'N/A')} ---")
        return jsonify(results)

    except Exception as e:
        print(f"Error processing /api/optimize request: {e}")
        print(traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred on the server."}), 500

if __name__ == '__main__':
    print("Starting Flask server for Schedule Optimizer API...")
    _ = get_day0_ref_midnight() # Initialize DAY0 reference on startup
    print(f"Reference Day 0 Midnight (Naive Local): {get_day0_ref_midnight()}")
    print(f"Using Gurobi for optimization. Default window: {DEFAULT_START_HOUR}:00-{DEFAULT_END_HOUR}:00")
    app.run(host='0.0.0.0', port=5001, debug=True)
