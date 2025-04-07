# bc2411/app.py
# Add imports for random generation logic if not already present
import random
import math
import traceback # For detailed error logging

# Add the generation functions from test.py (or import if moved to a separate file)
from allocation_logic import (
    solve_schedule_pulp,
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
# Enable CORS for all origins (development only)
# Specify the frontend origin if known, e.g., "http://localhost:5173"
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# ------------------------------------------------------------
# AUTO-GENERATION LOGIC (Moved from test.py)
# ------------------------------------------------------------

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
        # Breakfast: 8:00 - 8:30 local
        add_block(base_date.replace(hour=8, minute=0), base_date.replace(hour=8, minute=30), "Breakfast")
        # Lunch: 12:00 - 12:45 local
        add_block(base_date.replace(hour=12, minute=0), base_date.replace(hour=12, minute=45), "Lunch")
        # Dinner: 18:00 - 19:00 local
        add_block(base_date.replace(hour=18, minute=0), base_date.replace(hour=19, minute=0), "Dinner")

    # 3. Add some semi-fixed weekly activities (local times)
    # Monday: Club meeting 16:00-17:30 local
    add_block(day0.replace(hour=16, minute=0), day0.replace(hour=17, minute=30), "Club Meeting")
    # Wednesday: Study group 17:00-18:30 local
    add_block((day0 + timedelta(days=2)).replace(hour=17, minute=0), (day0 + timedelta(days=2)).replace(hour=18, minute=30), "Study Group")
    # Friday: Social activity 19:00-22:00 local
    add_block((day0 + timedelta(days=4)).replace(hour=19, minute=0), (day0 + timedelta(days=4)).replace(hour=22, minute=0), "Social Activity")
    # Saturday: Errands 10:00-13:00 local
    add_block((day0 + timedelta(days=5)).replace(hour=10, minute=0), (day0 + timedelta(days=5)).replace(hour=13, minute=0), "Errands")

    # 4. Add a few random commitments (local times)
    random_events = ["Doctor Appointment", "Meeting", "Phone Call", "Gym", "Commute", "Volunteering"]
    num_random = max(0, n_intervals - 8) # How many more to generate
    for _ in range(num_random):
        day = random.randint(0, TOTAL_DAYS - 1)
        hour = random.randint(8, 20) # Start hour between 8am and 8pm local
        minute = random.choice([0, 15, 30, 45])
        duration_min = random.choice([30, 45, 60, 75, 90, 120])
        event_name = random.choice(random_events)

        start_local = (day0 + timedelta(days=day)).replace(hour=hour, minute=minute)
        end_local = start_local + timedelta(minutes=duration_min)
        # Clamp end time to 10 PM local
        end_limit = start_local.replace(hour=22, minute=0)
        if end_local > end_limit:
            end_local = end_limit

        add_block(start_local, end_local, event_name)

    print(f"Generated {len(blocked_intervals)} blocked intervals.")
    return blocked_intervals

# ------------------------------------------------------------
# API ENDPOINTS
# ------------------------------------------------------------

# Helper to parse datetime strings from frontend, returning NAIVE LOCAL datetime
def parse_datetime_to_naive_local(dt_str):
    """
    Parses various ISO-like string formats from frontend into naive local datetime.
    Handles 'Z' and offsets by converting to local time first.
    """
    if not dt_str:
        return None
    try:
        # Handle 'Z' correctly - parse as UTC then convert to local naive
        if dt_str.endswith('Z'):
            dt_aware = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            # Convert to system's local time AND make naive
            dt_naive_local = dt_aware.astimezone(None).replace(tzinfo=None)
            # print(f"  Parsed '{dt_str}' (UTC) -> Aware Local {dt_aware.astimezone(None)} -> Naive Local {dt_naive_local}")
            return dt_naive_local

        # Handle potential '+HH:MM' or '-HH:MM' offsets
        # Python 3.7+ fromisoformat handles basic offsets
        if '+' in dt_str[10:] or '-' in dt_str[10:]: # Check for offset after date part
             try:
                 # Attempt direct parsing of aware string
                 dt_aware = datetime.fromisoformat(dt_str)
                 dt_naive_local = dt_aware.astimezone(None).replace(tzinfo=None)
                 # print(f"  Parsed '{dt_str}' (aware) -> Naive Local {dt_naive_local}")
                 return dt_naive_local
             except ValueError:
                 # Fallback if direct parsing fails (e.g., format issue)
                 print(f"  Warning: Direct parsing failed for offset string '{dt_str}', attempting fallback.")
                 pass # Continue to naive parsing attempt

        # If no timezone info, assume it's already naive local time
        # Remove fractional seconds for broader compatibility if present
        if '.' in dt_str:
             dt_str_no_ms = dt_str.split('.')[0]
             # print(f"  Removed fractional seconds: '{dt_str}' -> '{dt_str_no_ms}'")
             dt_str = dt_str_no_ms

        # Parse as naive datetime
        dt_naive_local = datetime.fromisoformat(dt_str)
        # print(f"  Parsed '{dt_str}' as Naive Local: {dt_naive_local}")
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
        tasks = auto_generate_tasks(num_tasks=random.randint(5, 8)) # Generate 5-8 tasks
        blocked = auto_generate_blocked(n_intervals=random.randint(8, 12)) # Generate 8-12 blocks
        # Returns naive local ISO strings
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
        settings_input = data.get('settings', {}) # Get settings from frontend
        start_hour_pref = settings_input.get('startHour', 8) # Use frontend prefs if sent
        end_hour_pref = settings_input.get('endHour', 22)   # Use frontend prefs if sent
        print(f"Frontend Time Window Preference: {start_hour_pref:02d}:00 - {end_hour_pref:02d}:00")
        # TODO: Currently allocation_logic doesn't use these preferences directly,
        # but they could be used to modify PREFERENCE_MAP or add constraints if needed.

        # --- 1. Parse and Validate Tasks ---
        parsed_tasks = []
        task_errors = []
        day0_ref = get_day0() # Use consistent naive local reference

        for idx, t in enumerate(tasks_input):
            task_id = t.get('id', f'task-input-{idx+1}') # Use provided ID or generate one
            name = t.get('name')
            priority = t.get('priority')
            difficulty = 1 # Default difficulty if not provided by frontend
            duration_min = t.get('duration') # Frontend sends 'duration'
            deadline_input = t.get('deadline') # Frontend sends 'deadline' (days or ISO string)
            preference = t.get('preference', 'any')

            if not name:
                task_errors.append(f"Task {idx+1}: Name is missing.")
                continue

            try:
                priority = int(priority) if priority is not None else 1
                duration_min = int(duration_min) if duration_min is not None else 15
                if duration_min <= 0:
                    task_errors.append(f"Task '{name}': Duration must be positive.")
                    continue
                priority = max(1, min(priority, 5)) # Clamp priority

            except (ValueError, TypeError):
                task_errors.append(f"Task '{name}': Priority and duration must be numbers.")
                continue

            # --- Deadline Parsing ---
            deadline_dt_local = None
            deadline_slot = TOTAL_SLOTS - 1 # Default to very end if parsing fails

            if isinstance(deadline_input, (int, float)): # Assume relative days if number
                relative_days = int(deadline_input)
                if relative_days >= 0:
                    # Calculate date relative to DAY0 (end of that day, naive local)
                    deadline_date = day0_ref + timedelta(days=relative_days)
                    # Use 21:59:59 local time as the effective end of the day for scheduling
                    deadline_dt_local = deadline_date.replace(hour=21, minute=59, second=59, microsecond=999999)
                    print(f"Task '{name}': Relative deadline {relative_days} days -> Local Deadline DT: {deadline_dt_local}")
                else:
                    task_errors.append(f"Task '{name}': Relative deadline days must be non-negative.")
                    continue
            elif isinstance(deadline_input, str): # Assume ISO string (could be local or UTC)
                deadline_dt_local = parse_datetime_to_naive_local(deadline_input)
                if not deadline_dt_local:
                    task_errors.append(f"Task '{name}': Invalid deadline format '{deadline_input}'.")
                    continue
                print(f"Task '{name}': Parsed deadline string '{deadline_input}' -> Local Deadline DT: {deadline_dt_local}")
            else: # Missing or invalid type
                task_errors.append(f"Task '{name}': Deadline is missing or has invalid type.")
                continue

            # Convert deadline datetime (naive local) to slot
            if deadline_dt_local:
                # Ensure deadline isn't before DAY0 (naive local comparison)
                if deadline_dt_local < day0_ref:
                     task_errors.append(f"Task '{name}': Deadline ({deadline_dt_local.strftime('%Y-%m-%d %H:%M')}) cannot be in the past relative to DAY0 ({day0_ref.strftime('%Y-%m-%d %H:%M')}).")
                     continue # Skip task if deadline is before reference start
                deadline_slot = datetime_to_slot(deadline_dt_local)
                print(f"  Converted local deadline to slot: {deadline_slot}")

            # Convert duration to slots
            duration_slots = math.ceil(duration_min / 15.0)
            if duration_slots <= 0: duration_slots = 1 # Ensure at least 1 slot

            # Check feasibility: deadline vs duration
            # Task must finish by deadline_slot, meaning last occupied slot <= deadline_slot
            # last occupied slot = start_slot + duration_slots - 1
            # Therefore, latest possible start = deadline_slot - duration_slots + 1
            # Check if *any* valid start slot exists (earliest start is slot 0)
            if deadline_slot < duration_slots - 1: # Equivalent to latest_start < 0
                 effective_deadline_time = slot_to_datetime(deadline_slot) + timedelta(minutes=15) # End time of deadline slot
                 task_errors.append(f"Task '{name}': Deadline ({effective_deadline_time.strftime('%Y-%m-%d %H:%M')}, slot {deadline_slot}) is too early for the duration ({duration_min} min / {duration_slots} slots). Minimum required end slot: {duration_slots - 1}")
                 continue

            parsed_tasks.append({
                "id": task_id, # Pass ID through
                "name": name,
                "priority": priority,
                "difficulty": difficulty, # Add difficulty
                "duration_slots": duration_slots,
                "deadline_slot": deadline_slot,
                "preference": preference.lower() if preference else 'any'
            })

        # --- 2. Parse Blocked Intervals ---
        parsed_commitments = {} # Map GLOBAL slot -> 15 (blocked)
        commitment_errors = []
        for idx, block in enumerate(blocked_input):
            block_id = block.get('id', f'block-input-{idx+1}')
            start_str = block.get('startTime')
            end_str = block.get('endTime')
            activity = block.get('activity', f'Blocked {idx+1}')

            if not start_str or not end_str:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Start and end times are required.")
                continue

            # Parse to naive local times
            start_dt_local = parse_datetime_to_naive_local(start_str)
            end_dt_local = parse_datetime_to_naive_local(end_str)

            if not start_dt_local or not end_dt_local:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Invalid time format (Start: '{start_str}', End: '{end_str}').")
                continue

            if end_dt_local <= start_dt_local:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): End time ({end_dt_local}) must be after start time ({start_dt_local}).")
                continue

            # Convert to slots
            start_slot = datetime_to_slot(start_dt_local)
            # End slot is tricky. We want to include all slots that *overlap* with the interval.
            # Find the slot containing the time *just before* the end time.
            # If end time is exactly on a slot boundary (e.g., 09:00), it should NOT block slot starting at 09:00.
            end_slot_inclusive = datetime_to_slot(end_dt_local - timedelta(microseconds=1))

            # Ensure the range is valid and within bounds
            effective_start_slot = max(0, start_slot)
            effective_end_slot = min(TOTAL_SLOTS - 1, end_slot_inclusive)

            if effective_start_slot <= effective_end_slot:
                print(f"Blocking slots for '{activity}': Local {start_dt_local.strftime('%H:%M')}-{end_dt_local.strftime('%H:%M')} -> Slots {effective_start_slot} to {effective_end_slot}")
                for s in range(effective_start_slot, effective_end_slot + 1):
                    parsed_commitments[s] = 15 # Mark slot as blocked
            else:
                 print(f"Warning: Blocked Interval '{activity}' ({block_id}) resulted in invalid slot range ({start_slot} to {end_slot_inclusive}) after conversion. Local Times: {start_dt_local} to {end_dt_local}. May be outside the 8am-10pm window or 7-day horizon.")
                 # This is usually not an error, just info.

        # --- 3. Parse Settings (Placeholder for now) ---
        settings_errors = []
        alpha=1.0 # Default leisure weight
        beta=0.1  # Default stress weight (lower means less penalty for stress)
        daily_limit_slots = None # Default no limit

        # --- Combine Errors and Check ---
        all_errors = task_errors + commitment_errors + settings_errors
        if task_errors:
             print(f"Error: Found {len(task_errors)} errors in task definitions. Aborting.")
             # Return specific errors to frontend
             return jsonify({"error": "Errors found in task definitions.", "details": task_errors}), 400

        if commitment_errors: # Log warnings, but proceed
             print(f"Warning: Found {len(commitment_errors)} issues processing blocked intervals:")
             for err in commitment_errors: print(f"  - {err}")
        if settings_errors:
             print(f"Warning: Found {len(settings_errors)} issues processing settings:")
             for err in settings_errors: print(f"  - {err}")

        # --- Call Solver ---
        if not parsed_tasks:
             # Calculate baseline leisure if no tasks
             total_possible_minutes = TOTAL_SLOTS * 15
             committed_minutes = len(parsed_commitments) * 15
             initial_leisure = total_possible_minutes - committed_minutes
             results = {'status': 'Optimal', 'schedule': [], 'total_leisure': initial_leisure, 'total_stress': 0.0, 'message': 'No valid tasks provided to schedule.'}
             print("No valid tasks provided. Returning baseline leisure.")
        else:
             print(f"\nCalling solver with {len(parsed_tasks)} tasks, {len(parsed_commitments)} commitment slots...")
             results = solve_schedule_pulp(
                 tasks=parsed_tasks,
                 commitments=parsed_commitments,
                 alpha=alpha,
                 beta=beta,
                 daily_limit_slots=daily_limit_slots
             )

        # Add non-blocking errors as warnings to the response
        warnings = commitment_errors + settings_errors
        if warnings:
            results['warnings'] = results.get('warnings', []) + warnings # Append if warnings already exist

        # Add task IDs back to the schedule results for frontend mapping (already done in solver)
        # Ensure results["schedule"] exists before iterating
        if results.get("schedule"):
             # The solver should already be adding the correct ID now.
             # Double-check if needed:
             task_map = {task["id"]: task for task in tasks_input} # Map original input task IDs
             output_schedule = []
             for scheduled_item in results["schedule"]:
                  original_task = task_map.get(scheduled_item["id"])
                  if original_task:
                      # Optionally copy other fields if needed, but solver returns most
                      item_copy = scheduled_item.copy()
                      # Ensure the ID matches the input exactly
                      item_copy["id"] = original_task["id"]
                      output_schedule.append(item_copy)
                  else:
                      print(f"Warning: Could not find original task input for scheduled item ID '{scheduled_item['id']}' (Name: '{scheduled_item['name']}'). Using solver-returned data.")
                      output_schedule.append(scheduled_item) # Keep solver data if map fails

             results["schedule"] = output_schedule

        # --- Return Results ---
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
    # Run on port 5001, enable debug for development
    # Use host='0.0.0.0' to make it accessible on the network
    app.run(host='0.0.0.0', port=5001, debug=True)
