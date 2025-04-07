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
from datetime import datetime, timedelta

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
    day0 = get_day0() # Get reference date

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
        # Set time to 21:59:59 on that day
        deadline_dt = deadline_date.replace(hour=21, minute=59, second=59, microsecond=999999)
        deadline_iso = deadline_dt.isoformat() + "Z" # Add Z for UTC indication, easier parsing

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
            "deadline": deadline_iso, # Send ISO string to frontend
            "preference": pref
        })
    print(f"Generated {len(tasks)} tasks.")
    return tasks

def auto_generate_blocked(n_intervals=8):
    """
    Randomly block out intervals in the 7-day horizon.
    Returns commitments in the format expected by the Frontend (start/end times).
    """
    print(f"--- Running auto_generate_blocked (n_intervals={n_intervals}) ---")
    blocked_intervals = []
    day0 = get_day0() # Get reference date
    interval_id_counter = 1

    # Function to add an interval
    def add_block(start_dt, end_dt, activity_name):
        nonlocal interval_id_counter
        # Ensure start is before end
        if end_dt <= start_dt:
            return
        # Ensure times are within the 7-day horizon (basic check)
        if start_dt >= day0 + timedelta(days=TOTAL_DAYS) or end_dt <= day0:
            return

        blocked_intervals.append({
            "id": f"block-gen-{interval_id_counter}",
            "startTime": start_dt.isoformat() + "Z",
            "endTime": end_dt.isoformat() + "Z",
            "activity": activity_name
        })
        interval_id_counter += 1

    # 1. Generate fixed class schedule (M/W/F and T/Th)
    class_times_mwf = [
        (9, 0, 50, "Math 101"), (11, 0, 50, "Physics 150"), (14, 0, 50, "English 105")
    ]
    class_times_tth = [
        (9, 30, 75, "CS 202"), (13, 0, 75, "History 201")
    ]

    for day_offset in [0, 2, 4]: # M/W/F
        base_date = day0 + timedelta(days=day_offset)
        for h, m, dur, name in class_times_mwf:
            start = base_date.replace(hour=h, minute=m, second=0, microsecond=0)
            end = start + timedelta(minutes=dur)
            add_block(start, end, f"Class: {name}")

    for day_offset in [1, 3]: # T/Th
        base_date = day0 + timedelta(days=day_offset)
        for h, m, dur, name in class_times_tth:
            start = base_date.replace(hour=h, minute=m, second=0, microsecond=0)
            end = start + timedelta(minutes=dur)
            add_block(start, end, f"Class: {name}")

    # 2. Add daily meals (consistent times)
    for day in range(TOTAL_DAYS):
        base_date = day0 + timedelta(days=day)
        # Breakfast: 8:00 - 8:30
        add_block(base_date.replace(hour=8, minute=0), base_date.replace(hour=8, minute=30), "Breakfast")
        # Lunch: 12:00 - 12:45
        add_block(base_date.replace(hour=12, minute=0), base_date.replace(hour=12, minute=45), "Lunch")
        # Dinner: 18:00 - 19:00
        add_block(base_date.replace(hour=18, minute=0), base_date.replace(hour=19, minute=0), "Dinner")

    # 3. Add some semi-fixed weekly activities
    # Monday: Club meeting 16:00-17:30
    add_block(day0.replace(hour=16, minute=0), day0.replace(hour=17, minute=30), "Club Meeting")
    # Wednesday: Study group 17:00-18:30
    add_block((day0 + timedelta(days=2)).replace(hour=17, minute=0), (day0 + timedelta(days=2)).replace(hour=18, minute=30), "Study Group")
    # Friday: Social activity 19:00-22:00
    add_block((day0 + timedelta(days=4)).replace(hour=19, minute=0), (day0 + timedelta(days=4)).replace(hour=22, minute=0), "Social Activity")
    # Saturday: Errands 10:00-13:00
    add_block((day0 + timedelta(days=5)).replace(hour=10, minute=0), (day0 + timedelta(days=5)).replace(hour=13, minute=0), "Errands")

    # 4. Add a few random commitments
    random_events = ["Doctor Appointment", "Meeting", "Phone Call", "Gym", "Commute", "Volunteering"]
    num_random = max(0, n_intervals - 8) # How many more to generate
    for _ in range(num_random):
        day = random.randint(0, TOTAL_DAYS - 1)
        hour = random.randint(8, 20) # Start hour between 8am and 8pm
        minute = random.choice([0, 15, 30, 45])
        duration_min = random.choice([30, 45, 60, 75, 90, 120])
        event_name = random.choice(random_events)

        start = (day0 + timedelta(days=day)).replace(hour=hour, minute=minute)
        end = start + timedelta(minutes=duration_min)
        # Clamp end time to 10 PM
        end_limit = start.replace(hour=22, minute=0)
        if end > end_limit:
            end = end_limit

        add_block(start, end, event_name)

    print(f"Generated {len(blocked_intervals)} blocked intervals.")
    return blocked_intervals

# ------------------------------------------------------------
# API ENDPOINTS
# ------------------------------------------------------------

# Helper to parse datetime strings, returning None on failure
def parse_datetime_safe(dt_str):
    if not dt_str:
        return None
    try:
        # Handle timezone info (Z means UTC, +HH:MM offset)
        if dt_str.endswith('Z'):
            # Replace Z with +00:00 for fromisoformat
            dt_str = dt_str[:-1] + '+00:00'
        # Handle potential '+HH:MM' offsets (Python 3.7+ for fromisoformat)
        # Handle simple 'YYYY-MM-DD HH:MM' by adding dummy offset if needed
        if 'T' not in dt_str and len(dt_str) == 16: # Likely 'YYYY-MM-DD HH:MM'
             dt_str += ':00+00:00' # Assume UTC if no T and no offset

        # Remove fractional seconds if present, as fromisoformat might struggle depending on Python version
        if '.' in dt_str:
             time_part = dt_str.split('T')[1] if 'T' in dt_str else dt_str.split(' ')[1]
             if '.' in time_part:
                 dt_str = dt_str.split('.')[0] + dt_str.split('.')[-1][-6:] # Keep offset if present


        parsed_dt = datetime.fromisoformat(dt_str)
        # If timezone aware, convert to local system time for consistency
        # If naive, assume it's local time (adjust if backend/frontend timezone mismatch)
        # For simplicity, let's assume datetimes are meant for the server's local context for now.
        # If the datetime has timezone info, we might want to convert it or handle it carefully.
        # Let's make it naive but keep the time relative to UTC if provided
        if parsed_dt.tzinfo:
            # Example: Convert UTC to local system time
            # parsed_dt = parsed_dt.astimezone(None)
            # OR just make it naive for slot calculation (relative to DAY0 which is local)
            parsed_dt = parsed_dt.replace(tzinfo=None)

        return parsed_dt
    except Exception as e:
        print(f"Error parsing datetime string '{dt_str}': {e}")
        return None

@app.route('/api/auto-generate', methods=['GET'])
def auto_generate_data():
    """Generates sample tasks and blocked intervals."""
    _ = get_day0() # Ensure DAY0 is initialized
    print(f"\n--- Received request for /api/auto-generate at {datetime.now()} ---")
    print(f"Reference DAY0: {get_day0()}")
    try:
        tasks = auto_generate_tasks(num_tasks=random.randint(5, 8)) # Generate 5-8 tasks
        blocked = auto_generate_blocked(n_intervals=random.randint(8, 12)) # Generate 8-12 blocks
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
    print(f"Reference DAY0: {get_day0()}")

    try:
        data = request.get_json()
        if not data:
            print("Error: Invalid or empty JSON payload received.")
            return jsonify({"error": "Invalid JSON payload"}), 400

        print("Received data:", data)

        tasks_input = data.get('tasks', [])
        blocked_input = data.get('blockedIntervals', []) # Renamed from commitments_input
        # settings_input = data.get('settings', {}) # Keep for future use
        # Extract start/end hour from frontend data if available
        # start_hour_fe = data.get('startHour', 8)
        # end_hour_fe = data.get('endHour', 22)
        # TODO: Use start_hour_fe and end_hour_fe if needed by allocation_logic

        # --- 1. Parse and Validate Tasks ---
        parsed_tasks = []
        task_errors = []
        day0_ref = get_day0() # Use consistent reference

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
            deadline_dt = None
            deadline_slot = TOTAL_SLOTS - 1 # Default to very end if parsing fails

            if isinstance(deadline_input, (int, float)): # Assume relative days if number
                relative_days = int(deadline_input)
                if relative_days >= 0:
                    # Calculate date relative to DAY0 (end of that day)
                    deadline_date = day0_ref + timedelta(days=relative_days)
                    deadline_dt = deadline_date.replace(hour=21, minute=59, second=59, microsecond=999999)
                    print(f"Task '{name}': Relative deadline {relative_days} days -> {deadline_dt}")
                else:
                    task_errors.append(f"Task '{name}': Relative deadline days must be non-negative.")
                    continue
            elif isinstance(deadline_input, str): # Assume ISO string
                deadline_dt = parse_datetime_safe(deadline_input)
                if not deadline_dt:
                    task_errors.append(f"Task '{name}': Invalid deadline format (should be ISO string like YYYY-MM-DDTHH:MM:SSZ or relative days).")
                    continue
                print(f"Task '{name}': Parsed deadline string -> {deadline_dt}")
            else: # Missing or invalid type
                task_errors.append(f"Task '{name}': Deadline is missing or has invalid type.")
                continue

            # Convert deadline datetime to slot
            if deadline_dt:
                # Ensure deadline isn't before DAY0 for slot calculation
                if deadline_dt < day0_ref:
                     task_errors.append(f"Task '{name}': Deadline ({deadline_dt.strftime('%Y-%m-%d %H:%M')}) cannot be in the past.")
                     continue # Skip task if deadline is before reference start
                deadline_slot = datetime_to_slot(deadline_dt)
                print(f"  Converted deadline to slot: {deadline_slot}")


            # Convert duration to slots
            duration_slots = math.ceil(duration_min / 15.0)
            if duration_slots == 0: duration_slots = 1

            # Check feasibility: deadline vs duration
            min_required_end_slot = duration_slots - 1
            if deadline_slot < min_required_end_slot:
                 effective_deadline_time = slot_to_datetime(deadline_slot) + timedelta(minutes=15)
                 task_errors.append(f"Task '{name}': Deadline ({effective_deadline_time.strftime('%Y-%m-%d %H:%M')}, slot {deadline_slot}) is too early for the duration ({duration_min} min / {duration_slots} slots). Minimum required end slot: {min_required_end_slot}")
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
        parsed_commitments = {} # Map slot -> 15 (blocked)
        commitment_errors = []
        for idx, block in enumerate(blocked_input):
            block_id = block.get('id', f'block-input-{idx+1}')
            start_str = block.get('startTime')
            end_str = block.get('endTime')
            activity = block.get('activity', f'Blocked {idx+1}')

            if not start_str or not end_str:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Start and end times are required.")
                continue

            start_dt = parse_datetime_safe(start_str)
            end_dt = parse_datetime_safe(end_str)

            if not start_dt or not end_dt:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): Invalid time format.")
                continue

            if end_dt <= start_dt:
                commitment_errors.append(f"Blocked Interval '{activity}' ({block_id}): End time must be after start time.")
                continue

            # Convert to slots
            start_slot = datetime_to_slot(start_dt)
            # End slot is tricky. We want to include all slots that *overlap* with the interval.
            # Find the slot containing the time *just before* the end time.
            end_slot_inclusive = datetime_to_slot(end_dt - timedelta(microseconds=1))

             # Ensure the range is valid and within bounds
            effective_start_slot = max(0, start_slot)
            effective_end_slot = min(TOTAL_SLOTS - 1, end_slot_inclusive)

            if effective_start_slot <= effective_end_slot:
                print(f"Blocking slots for '{activity}': {effective_start_slot} to {effective_end_slot}")
                for s in range(effective_start_slot, effective_end_slot + 1):
                    parsed_commitments[s] = 15 # Mark slot as blocked
            else:
                 print(f"Warning: Blocked Interval '{activity}' ({block_id}) resulted in invalid slot range ({start_slot} to {end_slot_inclusive}). Might be outside the schedulable window.")
                 # This is usually not an error, just info.

        # --- 3. Parse Settings (Placeholder) ---
        settings_errors = []
        alpha=1.0 # Default leisure weight
        beta=0.1  # Default stress weight (lower means less penalty for stress)
        daily_limit_slots = None # Default no limit
        # Example: If settings were passed
        # settings_input = data.get('settings', {})
        # objective_slider = float(settings_input.get('objective_slider', 5))
        # alpha = 0.1 + (objective_slider / 10.0) * 0.9
        # beta = 1.0 - (objective_slider / 10.0) * 0.9
        # daily_limit_minutes = settings_input.get('daily_limit_minutes')
        # if daily_limit_minutes is not None: daily_limit_slots = ...

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
                 # Pass start_hour/end_hour if solver uses them
                 # start_hour=start_hour_fe,
                 # end_hour=end_hour_fe
             )

        # Add non-blocking errors as warnings to the response
        warnings = commitment_errors + settings_errors
        if warnings:
            results['warnings'] = warnings

        # Add task IDs back to the schedule results for frontend mapping
        if results.get("schedule"):
            output_schedule = []
            task_map = {task["name"]: task.get("id", task["name"]) for task in parsed_tasks}
            for scheduled_item in results["schedule"]:
                item_copy = scheduled_item.copy()
                # Try to find the original task ID based on name
                item_copy["id"] = task_map.get(item_copy["name"], item_copy["name"])
                output_schedule.append(item_copy)
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
    print(f"Reference Day 0 (Today 8am): {get_day0()}")
    # Run on port 5001, enable debug for development
    # Use host='0.0.0.0' to make it accessible on the network
    app.run(host='0.0.0.0', port=5001, debug=True)
