
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pulp import (
    LpProblem, LpMaximize, LpVariable, LpBinary, LpContinuous,
    lpSum, LpStatus
)

# ------------------------------------------------------------
# CONFIG: 7 days, each day has 56 slots => 392 total slots
# Each slot = 15 minutes from 08:00 to 22:00
# ------------------------------------------------------------
SLOTS_PER_DAY = 56
TOTAL_DAYS = 7
TOTAL_SLOTS = SLOTS_PER_DAY * TOTAL_DAYS  # 392

# We'll define "day 0" as "today at 08:00 local time."
DAY0 = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

# For coloring and formatting in the terminal (ANSI codes)
RESET = "\033[0m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_MAGENTA = "\033[95m"

# ------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------

def generate_html_visualization(schedule_df, commitments, blocked_labels, total_leisure, total_stress):
    """Generate an HTML visualization of the schedule."""
    # Convert schedule_df to a list of dictionaries for JSON
    schedule_data = []
    for _, row in schedule_df.iterrows():
        schedule_data.append({
            "name": row["Task"],
            "priority": int(row["Priority"]),
            "difficulty": int(row["Difficulty"]),
            "startTime": row["StartTime"].isoformat(),
            "endTime": row["EndTime"].isoformat(),
            "duration": int(row["Duration(min)"])
        })

    # Convert blocked intervals to a format for visualization
    blocked_intervals = []
    current_start = None
    current_label = None

    for s in range(TOTAL_SLOTS):
        if commitments[s] == 15:  # This slot is blocked
            if current_start is None or blocked_labels[s] != current_label:
                # Either starting a new blocked interval or changing label
                if current_start is not None:
                    # End the previous interval
                    blocked_intervals.append({
                        "startTime": current_start.isoformat(),
                        "endTime": (slot_to_datetime(s)).isoformat(),
                        "label": current_label
                    })
                current_start = slot_to_datetime(s)
                current_label = blocked_labels[s]
        elif current_start is not None:
            # End of a blocked interval
            blocked_intervals.append({
                "startTime": current_start.isoformat(),
                "endTime": (slot_to_datetime(s)).isoformat(),
                "label": current_label
            })
            current_start = None
            current_label = None

    # If there's an ongoing blocked interval at the end
    if current_start is not None:
        blocked_intervals.append({
            "startTime": current_start.isoformat(),
            "endTime": (slot_to_datetime(TOTAL_SLOTS-1) + timedelta(minutes=15)).isoformat(),
            "label": current_label
        })

    # Summary data
    summary_data = {
        "totalLeisure": int(total_leisure),
        "totalStress": float(total_stress),
        "day0": DAY0.isoformat()
    }

    # Read the template and replace placeholders
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>7-Day Task Schedule Visualization</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 20px;
      background-color: #f5f5f5;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      background-color: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    h1 {
      color: #333;
      text-align: center;
      margin-bottom: 30px;
    }
    .schedule {
      display: grid;
      grid-template-columns: 60px repeat(7, 1fr);
      gap: 1px;
      border: 1px solid #ddd;
    }
    .time-label {
      grid-column: 1;
      background-color: #f8f8f8;
      padding: 5px;
      text-align: right;
      font-size: 12px;
      border-bottom: 1px solid #ddd;
      height: 20px;
      line-height: 20px;
    }
    .day-header {
      background-color: #4285f4;
      color: white;
      padding: 10px 5px;
      text-align: center;
      font-weight: bold;
    }
    .time-slot {
      background-color: #f8f8f8;
      border-bottom: 1px solid #eee;
      height: 20px;
    }
    .task {
      position: absolute;
      border-radius: 4px;
      padding: 4px;
      font-size: 12px;
      overflow: hidden;
      box-sizing: border-box;
      color: white;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .summary {
      margin-top: 30px;
      padding: 15px;
      background-color: #f8f8f8;
      border-radius: 5px;
    }
    .task-list {
      margin-top: 20px;
    }
    .task-list h3 {
      margin-bottom: 10px;
      color: #333;
    }
    .task-list-item {
      background-color: white;
      padding: 10px;
      margin-bottom: 8px;
      border-radius: 4px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .blocked-time {
      background-color: rgba(220, 220, 220, 0.8);
      position: absolute;
      font-size: 10px;
      color: #555;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>7-Day Task Schedule Visualization</h1>

    <div id="schedule-container" style="position: relative; overflow-x: auto;">
      <div class="schedule" id="schedule-grid">
        <!-- Day headers will be added by JavaScript -->
        <!-- Time slots will be added by JavaScript -->
      </div>
    </div>

    <div class="summary">
      <h2>Schedule Summary</h2>
      <p><strong>Total Leisure Time:</strong> <span id="total-leisure">0</span> minutes</p>
      <p><strong>Total Stress Score:</strong> <span id="total-stress">0</span></p>
    </div>

    <div class="task-list">
      <h3>Scheduled Tasks</h3>
      <div id="task-list-container">
        <!-- Task items will be inserted here -->
      </div>
    </div>
  </div>

  <script>
    // Schedule data will be populated by Python
    const scheduleData = SCHEDULE_DATA_PLACEHOLDER;
    const blockedIntervals = BLOCKED_INTERVALS_PLACEHOLDER;
    const summaryData = SUMMARY_DATA_PLACEHOLDER;

    // Color mapping based on priority*difficulty
    function getTaskColor(priority, difficulty) {
      const score = priority * difficulty;
      if (score >= 20) return "#E53935"; // High stress (red)
      if (score >= 12) return "#FB8C00"; // Medium-high stress (orange)
      if (score >= 8) return "#FDD835";  // Medium stress (yellow)
      if (score >= 4) return "#43A047";  // Medium-low stress (green)
      return "#1E88E5";                  // Low stress (blue)
    }

    document.addEventListener("DOMContentLoaded", function() {
      const scheduleGrid = document.getElementById("schedule-grid");
      const container = document.getElementById("schedule-container");

      // First row: day headers
      const headerRow = document.createElement("div");
      headerRow.style.gridColumn = "1";
      headerRow.className = "time-label";
      scheduleGrid.appendChild(headerRow);

      // Add day headers
      const startDate = new Date(summaryData.day0);
      for (let i = 0; i < 7; i++) {
        const dayDate = new Date(startDate);
        dayDate.setDate(startDate.getDate() + i);

        const dayHeader = document.createElement("div");
        dayHeader.className = "day-header";
        dayHeader.textContent = dayDate.toLocaleDateString('en-US', {
          weekday: 'short',
          month: 'short',
          day: 'numeric'
        });
        dayHeader.style.gridColumn = i + 2;
        scheduleGrid.appendChild(dayHeader);
      }

      // Create time slots (8:00 - 22:00, every 15 minutes)
      for (let hour = 8; hour < 22; hour++) {
        for (let minute = 0; minute < 60; minute += 15) {
          // Time label
          if (minute === 0) {
            const timeLabel = document.createElement("div");
            timeLabel.className = "time-label";
            timeLabel.textContent = `${hour}:00`;
            scheduleGrid.appendChild(timeLabel);
          } else {
            const emptyLabel = document.createElement("div");
            emptyLabel.className = "time-label";
            emptyLabel.style.color = "#ccc";
            emptyLabel.textContent = `${hour}:${minute}`;
            scheduleGrid.appendChild(emptyLabel);
          }

          // Create time slots for each day
          for (let day = 0; day < 7; day++) {
            const timeSlot = document.createElement("div");
            timeSlot.className = "time-slot";
            scheduleGrid.appendChild(timeSlot);
          }
        }
      }

      // Position for tasks (relative to the grid)
      const slotHeight = 22; // Height of each 15-min slot (including border)
      const dayWidth = scheduleGrid.offsetWidth / 8; // 8 columns (1 for time labels + 7 days)
      const timeColumnWidth = 60; // Width of time column

      // Calculate slot index for a given time
      function timeToSlotIndex(time) {
        const hours = time.getHours();
        const minutes = time.getMinutes();
        return (hours - 8) * 4 + Math.floor(minutes / 15);
      }

      // Add blocked intervals
      for (const interval of blockedIntervals) {
        const startTime = new Date(interval.startTime);
        const endTime = new Date(interval.endTime);
        const startSlot = timeToSlotIndex(startTime);
        const endSlot = timeToSlotIndex(new Date(endTime.getTime() - 1000)); // Subtract 1s to get correct slot
        const dayIndex = startTime.getDay();

        const blockedDiv = document.createElement("div");
        blockedDiv.className = "blocked-time";

        const top = startSlot * slotHeight;
        const height = (endSlot - startSlot + 1) * slotHeight;
        const left = timeColumnWidth + dayIndex * dayWidth;

        blockedDiv.style.top = `${top}px`;
        blockedDiv.style.height = `${height}px`;
        blockedDiv.style.left = `${left}px`;
        blockedDiv.style.width = `${dayWidth}px`;
        blockedDiv.innerHTML = `<span style="font-size: 10px; color: #444;">${interval.label}</span>`;
        blockedDiv.style.display = "flex";
        blockedDiv.style.alignItems = "center";
        blockedDiv.style.justifyContent = "center";
        blockedDiv.style.textAlign = "center";
        container.appendChild(blockedDiv);
      }

      // Add tasks to the schedule
      for (const task of scheduleData) {
        const startTime = new Date(task.startTime);
        const endTime = new Date(task.endTime);

        const startSlot = timeToSlotIndex(startTime);
        const endSlot = timeToSlotIndex(new Date(endTime.getTime() - 1000)); // Subtract 1s to get correct slot
        const dayIndex = startTime.getDay();

        const taskDiv = document.createElement("div");
        taskDiv.className = "task";
        taskDiv.style.backgroundColor = getTaskColor(task.priority, task.difficulty);

        const top = startSlot * slotHeight;
        const height = (endSlot - startSlot + 1) * slotHeight;
        const left = timeColumnWidth + dayIndex * dayWidth;

        taskDiv.style.top = `${top}px`;
        taskDiv.style.height = `${height}px`;
        taskDiv.style.left = `${left}px`;
        taskDiv.style.width = `${dayWidth}px`;

        taskDiv.innerHTML = `<strong>${task.name}</strong><br>P:${task.priority}, D:${task.difficulty}`;
        container.appendChild(taskDiv);

        // Add to task list below calendar
        const listItem = document.createElement("div");
        listItem.className = "task-list-item";
        listItem.innerHTML = `
          <strong>${task.name}</strong> (Priority: ${task.priority}, Difficulty: ${task.difficulty})<br>
          Time: ${startTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} -
          ${endTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})},
          ${startTime.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'})}
        `;
        document.getElementById("task-list-container").appendChild(listItem);
      }

      // Update summary data
      document.getElementById("total-leisure").textContent = summaryData.totalLeisure;
      document.getElementById("total-stress").textContent = summaryData.totalStress;
    });
  </script>
</body>
</html>"""

    import json
    html_content = html_template.replace(
        'SCHEDULE_DATA_PLACEHOLDER', json.dumps(schedule_data)
    ).replace(
        'BLOCKED_INTERVALS_PLACEHOLDER', json.dumps(blocked_intervals)
    ).replace(
        'SUMMARY_DATA_PLACEHOLDER', json.dumps(summary_data)
    )

    # Write to file
    filename = 'schedule_visualization.html'
    with open(filename, 'w') as f:
        f.write(html_content)

    print(BRIGHT_GREEN + f"\nHTML visualization saved to {filename}" + RESET)
    print(BRIGHT_GREEN + f"Open this file in your web browser to view the schedule visualization." + RESET)

def clamp_to_7day_horizon(dt):
    """
    Clamp dt to be within [DAY0, DAY0 + 7 days].
    If dt < DAY0, set dt = DAY0.
    If dt > DAY0+7 days, set dt = day0+7 days.
    """
    if dt < DAY0:
        return DAY0
    limit = DAY0 + timedelta(days=TOTAL_DAYS)
    if dt > limit:
        return limit
    return dt

def datetime_to_slot(dt):
    """
    Convert dt to a slot index in [0..391], each slot = 15 minutes from 08:00 to 22:00 over 7 days.
    """
    dt = clamp_to_7day_horizon(dt)
    delta = dt - DAY0
    total_minutes = delta.total_seconds() / 60

    day_offset = int(total_minutes // (24*60))  # how many full days from DAY0
    leftover = total_minutes % (24*60)          # minutes into the day

    # 08:00..22:00 => 14 hours = 840 minutes => 56 slots
    # clamp leftover to [0..840]
    leftover = max(0, min(leftover, 840))
    slot_in_day = int(leftover // 15)

    raw_slot = day_offset*SLOTS_PER_DAY + slot_in_day
    # clamp final index
    return max(0, min(raw_slot, TOTAL_SLOTS-1))

def slot_to_datetime(slot):
    """
    Convert a slot [0..391] back to a datetime = DAY0 + 15*slot minutes.
    """
    days = slot // SLOTS_PER_DAY
    slots_in_day = slot % SLOTS_PER_DAY

    hours = slots_in_day // 4
    minutes = (slots_in_day % 4) * 15

    return DAY0 + timedelta(days=days, hours=hours, minutes=minutes)

def user_friendly_str(dt):
    """Return a nicely formatted datetime string, e.g. Mar 31 13:45."""
    return dt.strftime("%b %d %H:%M")

def parse_user_datetime(prompt):
    """
    Repeatedly ask user for a datetime in YYYY-MM-DD HH:MM format or blank to skip.
    """
    while True:
        user_input = input(prompt).strip()
        if not user_input:
            return None
        try:
            dt = datetime.strptime(user_input, "%Y-%m-%d %H:%M")
            return dt
        except ValueError:
            print(BRIGHT_YELLOW + "  Invalid format! Please use YYYY-MM-DD HH:MM." + RESET)

# Build sets of valid slots for "morning", "afternoon", "evening"
morning_slots = []
afternoon_slots = []
evening_slots = []
for day in range(TOTAL_DAYS):
    base = day * SLOTS_PER_DAY
    # morning => 08:00..12:00 => first 16 slots of that day
    morning_slots.extend(range(base, base+16))
    # afternoon => 12:00..16:00 => next 16 slots
    afternoon_slots.extend(range(base+16, base+32))
    # evening => 16:00..22:00 => last 24 slots
    evening_slots.extend(range(base+32, base+56))

PREFERENCE_MAP = {
    "morning": set(morning_slots),
    "afternoon": set(afternoon_slots),
    "evening": set(evening_slots)
}

# ------------------------------------------------------------
# USER INPUT MODE
# ------------------------------------------------------------
def gather_tasks():
    """
    Prompt the user for tasks manually.
    Returns a list of {name, priority, difficulty, duration, deadline_slot, preference}
    """
    tasks = []
    print(BRIGHT_CYAN + "=== ENTER YOUR TASKS ===" + RESET)
    while True:
        try:
            n = int(input("How many tasks do you want to schedule? (e.g., 5): "))
            if n < 1:
                print(BRIGHT_YELLOW + "Please enter a positive integer." + RESET)
                continue
            break
        except ValueError:
            print(BRIGHT_YELLOW + "Please enter a valid integer." + RESET)

    for i in range(n):
        print(f"\n{BRIGHT_GREEN}-- Task {i+1} --{RESET}")
        name = input("  Name of task: ").strip() or f"Task_{i+1}"

        # Priority
        while True:
            try:
                prio = int(input("  Priority (1-5): "))
                if 1 <= prio <= 5:
                    break
                else:
                    print("  Must be in [1..5]")
            except ValueError:
                print("  Please enter an integer in [1..5].")

        # Difficulty
        while True:
            try:
                diff = int(input("  Difficulty (1-5): "))
                if 1 <= diff <= 5:
                    break
                else:
                    print("  Must be in [1..5]")
            except ValueError:
                print("  Please enter an integer in [1..5].")

        # Duration in 15-min blocks
        while True:
            try:
                dur = int(input("  Duration in 15-min blocks (e.g. 4 => 1 hour): "))
                if dur < 1:
                    print("  Duration must be >= 1.")
                else:
                    break
            except ValueError:
                print("  Please enter an integer >= 1.")

        # Deadline
        print("  Enter the deadline in YYYY-MM-DD HH:MM format (within next 7 days). Leave blank for last possible day.")
        dt = parse_user_datetime("  Deadline: ")
        if dt is None:
            # Default to the very last slot (end of day 6 at 22:00)
            deadline_slot = TOTAL_SLOTS - 1
            # Optional: Print confirmation of the default deadline time
            default_deadline_dt = slot_to_datetime(deadline_slot) + timedelta(minutes=15) # Get the *end* time of the last slot
            print(BRIGHT_YELLOW + f"    (No deadline entered. Defaulting to end of horizon: {user_friendly_str(default_deadline_dt)})" + RESET)
        else:
            # Convert user-provided datetime to the slot index
            # datetime_to_slot handles clamping to the 8:00-22:00 window and the 7-day horizon
            deadline_slot = datetime_to_slot(dt)
            # Optional: Inform user if their input was clamped
            clamped_dt = slot_to_datetime(deadline_slot) # Get the start time of the calculated slot
            # Check if the resulting slot's start time matches the input time (within 15 min tolerance)
            # A simple check is if the calculated slot corresponds to a different time than intended
            if abs((dt - clamped_dt).total_seconds()) > 60 and dt >= DAY0 and dt <= DAY0 + timedelta(days=TOTAL_DAYS) : # only warn if clamping happened within the valid period
                 effective_deadline_end = clamped_dt + timedelta(minutes=15)
                 print(BRIGHT_YELLOW + f"    (Note: Deadline time adjusted to fit 08:00-22:00 window. Effective deadline: {user_friendly_str(effective_deadline_end)})" + RESET)


        # --- Rest of the task gathering loop ---
        tasks.append({
            "name": name,
            "priority": prio,
            "difficulty": diff,
            "duration": dur,
            "deadline_slot": deadline_slot, # Use the calculated slot
            "preference": pref
        })
    return tasks

def gather_blocked_intervals():
    """
    Prompt user for blocked intervals in real date/time format.
    Returns a tuple (commitments, blocked_labels) where:
      - commitments[s] = 15 if blocked, else 0
      - blocked_labels[s] = description of the blocked activity
    """
    commitments = {s: 0 for s in range(TOTAL_SLOTS)}
    blocked_labels = {s: "" for s in range(TOTAL_SLOTS)}

    print(BRIGHT_CYAN + "\n=== ENTER YOUR BLOCKED TIME INTERVALS ===" + RESET)
    while True:
        try:
            b = int(input("How many blocked intervals? (0 if none): "))
            if b < 0:
                print(BRIGHT_YELLOW + "Please enter a non-negative integer." + RESET)
                continue
            break
        except ValueError:
            print(BRIGHT_YELLOW + "Please enter a valid integer." + RESET)

    for i in range(b):
        print(f"\n{BRIGHT_GREEN}-- Blocked Interval {i+1} --{RESET}")
        print("  Enter start date/time in YYYY-MM-DD HH:MM. Leave blank to skip.")
        start_dt = parse_user_datetime("  Start: ")
        if not start_dt:
            continue

        print("  Enter end date/time in YYYY-MM-DD HH:MM.")
        end_dt = parse_user_datetime("  End: ")
        if not end_dt:
            continue

        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt

        label = input("  Description (e.g., 'Class', 'Meeting'): ").strip()
        if not label:
            label = f"Blocked Time {i+1}"

        start_slot = datetime_to_slot(start_dt)
        end_slot   = datetime_to_slot(end_dt)
        for s in range(start_slot, end_slot+1):
            commitments[s] = 15
            blocked_labels[s] = label

    return commitments, blocked_labels

# ------------------------------------------------------------
# AUTO-GENERATE MODE
# ------------------------------------------------------------
def auto_generate_tasks(num_tasks=10):
    """
    Generate student-specific tasks within the next 7 days.
    Includes assignments, projects, study sessions, etc.
    Does NOT specify exact deadline times, only the deadline DAY.
    The deadline is assumed to be the end of that day (22:00).
    """
    # np.random.seed(42)  # for repeatable demo

    # Student-specific task names and categories
    task_types = [
        ("Assignment", 3, 5, 4),           # (type, avg priority, avg difficulty, avg duration)
        ("Study Session", 2, 2, 3),
        ("Group Project", 4, 4, 4),
        ("Reading", 2, 2, 2),
        ("Homework", 3, 3, 2),
        ("Essay", 4, 4, 6),
        ("Lab Report", 4, 5, 4),
        ("Exam Prep", 5, 4, 5),
        ("Research", 3, 3, 3),
        ("Presentation Prep", 4, 3, 3)
    ]

    courses = [
        "Math 101",
        "Computer Science 202",
        "Physics 150",
        "English 105",
        "History 201",
        "Chemistry 110",
        "Economics 230",
        "Psychology 120"
    ]

    # Preferences set
    pref_choices = ["morning", "afternoon", "evening"]

    tasks = []
    for i in range(num_tasks):
        # Select random task type and course
        task_type, base_prio, base_diff, base_dur = task_types[np.random.randint(0, len(task_types))]
        course = courses[np.random.randint(0, len(courses))]

        # Create task name
        name = f"{task_type} - {course}"

        # Add some variation to priority, difficulty, duration
        prio = min(5, max(1, int(base_prio + np.random.randint(-1, 2))))  # +/- 1 from base
        diff = min(5, max(1, int(base_diff + np.random.randint(-1, 2))))  # +/- 1 from base
        dur = min(8, max(1, int(base_dur + np.random.randint(-1, 2))))    # +/- 1 from base

        # Determine the deadline DAY (0-6)
        is_long_term = task_type in ["Group Project", "Essay", "Research"]
        is_classwork = task_type in ["Exam Prep", "Lab Report"]

        if is_long_term:
            # Longer-term tasks have deadlines 4-6 days out
            deadline_day = np.random.randint(4, TOTAL_DAYS) # Day index 4, 5, or 6
        elif is_classwork:
            # Class-related tasks often due in 1-3 days
            deadline_day = np.random.randint(1, 4) # Day index 1, 2, or 3
        else:
            # Regular assignments 2-5 days out
            deadline_day = np.random.randint(2, 6) # Day index 2, 3, 4, or 5

        # Calculate the deadline slot as the *last slot* of the deadline day
        # Last slot of day `d` is `(d + 1) * SLOTS_PER_DAY - 1`
        deadline_slot = (deadline_day + 1) * SLOTS_PER_DAY - 1

        # --- Removed random hour/minute generation ---
        # rand_hour = ...
        # rand_minute = ...
        # dt = DAY0 + timedelta(...)
        # dl_slot = datetime_to_slot(dt) # <<< This is removed

        # Set Preference
        if task_type in ["Study Session", "Reading", "Research"]:
            pref = np.random.choice(pref_choices)
        elif task_type in ["Exam Prep", "Presentation Prep"]:
            pref = np.random.choice(["morning", "morning", "afternoon"])
        else:
            pref = np.random.choice(pref_choices)

        tasks.append({
            "name": name,
            "priority": prio,
            "difficulty": diff,
            "duration": dur,
            "deadline_slot": deadline_slot, # Now always end of the deadline day
            "deadline_day_debug": deadline_day, # Keep for reference if needed
            "preference": pref
        })
    return tasks

def auto_generate_blocked(n_intervals=8):
    """
    Randomly block out intervals in the 7-day horizon.
    Creates typical student schedule including classes, meals, club activities, etc.
    """
    # np.random.seed(99)  # separate seed for blocked intervals
    commitments = {s: 0 for s in range(TOTAL_SLOTS)}
    # Create a dict to store the reason for each blocked slot
    blocked_labels = {s: "" for s in range(TOTAL_SLOTS)}

    # 1. Generate fixed class schedule (same classes on M/W/F and T/Th)
    class_times_mwf = [
        (9, 0, 50, "Math 101"),    # 9:00-9:50
        (11, 0, 50, "Physics 150"),   # 11:00-11:50
        (14, 0, 50, "English 105")    # 14:00-14:50
    ]

    class_times_tth = [
        (9, 30, 75, "CS 202"),   # 9:30-10:45
        (13, 0, 75, "History 201")    # 13:00-14:15
    ]

    # Monday, Wednesday, Friday classes
    for day_offset in [0, 2, 4]:  # Monday=0, Wednesday=2, Friday=4
        for start_hour, start_min, duration_min, class_name in class_times_mwf:
            start_dt = DAY0 + timedelta(days=day_offset, hours=start_hour-8, minutes=start_min)
            start_slot = datetime_to_slot(start_dt)
            duration_slots = (duration_min + 14) // 15  # round up to nearest 15-min slot
            end_slot = min(start_slot + duration_slots, TOTAL_SLOTS-1)

            for s in range(start_slot, end_slot):
                commitments[s] = 15
                blocked_labels[s] = f"Class: {class_name}"

    # Tuesday, Thursday classes
    for day_offset in [1, 3]:  # Tuesday=1, Thursday=3
        for start_hour, start_min, duration_min, class_name in class_times_tth:
            start_dt = DAY0 + timedelta(days=day_offset, hours=start_hour-8, minutes=start_min)
            start_slot = datetime_to_slot(start_dt)
            duration_slots = (duration_min + 14) // 15  # round up to nearest 15-min slot
            end_slot = min(start_slot + duration_slots, TOTAL_SLOTS-1)

            for s in range(start_slot, end_slot):
                commitments[s] = 15
                blocked_labels[s] = f"Class: {class_name}"

    # 2. Add daily meals
    for day in range(TOTAL_DAYS):
        # Breakfast: 8:00-8:30
        breakfast_start = day * SLOTS_PER_DAY
        for s in range(breakfast_start, breakfast_start + 2):
            commitments[s] = 15
            blocked_labels[s] = "Breakfast"

        # Lunch: 12:00-12:45
        lunch_start = day * SLOTS_PER_DAY + 16  # 8:00 + 4 hours = 12:00
        for s in range(lunch_start, lunch_start + 3):
            commitments[s] = 15
            blocked_labels[s] = "Lunch"

        # Dinner: 18:00-19:00
        dinner_start = day * SLOTS_PER_DAY + 40  # 8:00 + 10 hours = 18:00
        for s in range(dinner_start, dinner_start + 4):
            commitments[s] = 15
            blocked_labels[s] = "Dinner"

    # 3. Add club activities and social events
    # Monday: Club meeting 16:00-17:30
    club_start = 0 * SLOTS_PER_DAY + 32  # Monday 16:00
    for s in range(club_start, club_start + 6):
        commitments[s] = 15
        blocked_labels[s] = "Club Meeting"

    # Wednesday: Study group 17:00-18:30
    study_start = 2 * SLOTS_PER_DAY + 36  # Wednesday 17:00
    for s in range(study_start, study_start + 6):
        commitments[s] = 15
        blocked_labels[s] = "Study Group"

    # Friday: Social activity 19:00-22:00
    social_start = 4 * SLOTS_PER_DAY + 44  # Friday 19:00
    for s in range(social_start, social_start + 12):
        commitments[s] = 15
        blocked_labels[s] = "Social Activity"

    # Saturday: Free time/errands 10:00-13:00
    errand_start = 5 * SLOTS_PER_DAY + 8  # Saturday 10:00
    for s in range(errand_start, errand_start + 12):
        commitments[s] = 15
        blocked_labels[s] = "Errands"

    # Sunday: Family time or religious commitment 10:00-12:00
    family_start = 6 * SLOTS_PER_DAY + 8  # Sunday 10:00
    for s in range(family_start, family_start + 8):
        commitments[s] = 15
        blocked_labels[s] = "Family Time"

    # 4. Add a few random commitments to simulate unexpected events
    random_events = ["Doctor Appointment", "Meeting", "Phone Call", "Gym", "Commute"]
    for i in range(n_intervals - 8):  # We already have 8 types of commitments
        # pick random start date/time
        s_day = int(np.random.randint(0, TOTAL_DAYS))
        s_hour = int(np.random.randint(8, 22))
        s_min = int(np.random.choice([0, 15, 30, 45]))

        start_dt = DAY0 + timedelta(days=s_day, hours=s_hour-8, minutes=s_min)
        start_slot = datetime_to_slot(start_dt)

        # random length between 30 min and 2 hours
        length_blocks = int(np.random.randint(2, 9))
        end_slot = min(start_slot + length_blocks, TOTAL_SLOTS-1)

        # Choose a random event type
        event = random_events[np.random.randint(0, len(random_events))]

        for s in range(start_slot, end_slot+1):
            commitments[s] = 15
            blocked_labels[s] = event

    return commitments, blocked_labels

def print_blocked_intervals(commitments, blocked_labels):
    """Print a summary of blocked intervals to the CLI."""
    print(BRIGHT_CYAN + "\n=== BLOCKED TIME INTERVALS ===" + RESET)

    # Group consecutive slots with the same label
    current_start_slot = None
    current_label = None
    blocked_periods = []

    for s in range(TOTAL_SLOTS):
        if commitments[s] == 15:
            # This slot is blocked
            if current_start_slot is None or blocked_labels[s] != current_label:
                # Either starting a new blocked interval or changing label
                if current_start_slot is not None:
                    # End the previous interval
                    blocked_periods.append({
                        "start_slot": current_start_slot,
                        "end_slot": s - 1,
                        "label": current_label
                    })
                current_start_slot = s
                current_label = blocked_labels[s]
        elif current_start_slot is not None:
            # End of a blocked interval
            blocked_periods.append({
                "start_slot": current_start_slot,
                "end_slot": s - 1,
                "label": current_label
            })
            current_start_slot = None
            current_label = None

    # If there's an ongoing blocked interval at the end
    if current_start_slot is not None:
        blocked_periods.append({
            "start_slot": current_start_slot,
            "end_slot": TOTAL_SLOTS - 1,
            "label": current_label
        })

    # Print the blocked periods in a nice table format
    if not blocked_periods:
        print("No blocked intervals")
        return

    # ASCII table header
    header = (
        "+-------------------+-------------------+----------------------------+\n"
        "|     Start Time    |      End Time     |          Activity          |\n"
        "+-------------------+-------------------+----------------------------+"
    )
    print(header)

    # Sort by start time
    blocked_periods.sort(key=lambda x: x["start_slot"])

    # Print each blocked period
    for period in blocked_periods:
        start_dt = slot_to_datetime(period["start_slot"])
        end_dt = slot_to_datetime(period["end_slot"]) + timedelta(minutes=15)  # Add 15 min since end is inclusive

        start_str = start_dt.strftime("%a %b %d %H:%M")
        end_str = end_dt.strftime("%a %b %d %H:%M")
        label = period["label"]

        # Limit label length for display
        if len(label) > 26:
            label = label[:23] + "..."

        print(f"| {start_str:<17} | {end_str:<17} | {label:<26} |")
        print("+-------------------+-------------------+----------------------------+")

    # Print a summary
    total_blocked_minutes = sum(
        (period["end_slot"] - period["start_slot"] + 1) * 15
        for period in blocked_periods
    )
    print(f"\nTotal blocked time: {total_blocked_minutes} minutes "
          f"({total_blocked_minutes/60:.1f} hours)")
    print(f"Percentage of available time blocked: "
          f"{100 * total_blocked_minutes / (TOTAL_SLOTS * 15):.1f}%")


# ------------------------------------------------------------
# MAIN SCHEDULER
# ------------------------------------------------------------
def main():
    print(BRIGHT_MAGENTA + "="*55 + RESET)
    print(BRIGHT_MAGENTA + "   WELCOME to the 7-Day Task Scheduler (Demo)   " + RESET)
    print(BRIGHT_MAGENTA + "="*55 + RESET + "\n")

    mode = input("Do you want to (A)uto-generate or (M)anually enter tasks & blocked intervals? [A/M]: ").strip().lower()

    if mode == "m":
        tasks = gather_tasks()
        commitments, blocked_labels = gather_blocked_intervals()
        blocked_labels = {s: "Blocked" for s in range(TOTAL_SLOTS) if commitments[s] == 15}
    else:
        # Auto-generate
        print(BRIGHT_CYAN + "Auto-generating tasks and blocked intervals..." + RESET)
        tasks = auto_generate_tasks(num_tasks=5)
        commitments, blocked_labels = auto_generate_blocked(n_intervals=3)

        print(BRIGHT_GREEN + "\nAUTO-GENERATED TASKS:" + RESET)
        df = pd.DataFrame(tasks)
        print(df)

        print(BRIGHT_GREEN + "\nAUTO-GENERATED BLOCKED INTERVALS" + RESET)
        # We'll just show how many slots are blocked
        blocked_count = sum(1 for s in commitments if commitments[s] == 15)
        print(f"  Total blocked slots: {blocked_count} / {TOTAL_SLOTS}")

    print_blocked_intervals(commitments, blocked_labels)


    # Show tasks nicely
    print("\n" + BRIGHT_CYAN + "Current Tasks:" + RESET)
    df_tasks = pd.DataFrame(tasks)
    print(df_tasks)

    # Build the model
    model = LpProblem("Weekly_Scheduler", LpMaximize)

    # Decision variables
    X = {}
    n_tasks = len(tasks)
    for i in range(n_tasks):
        for s in range(TOTAL_SLOTS):
            X[(i,s)] = LpVariable(f"X_{i}_{s}", cat=LpBinary)

    Y = {s: LpVariable(f"Y_{s}", cat=LpBinary) for s in range(TOTAL_SLOTS)}
    L_var = {s: LpVariable(f"L_{s}", lowBound=0, cat=LpContinuous) for s in range(TOTAL_SLOTS)}

    # Objective: Maximize sum(L[s]) - sum(priority*difficulty)
    alpha, beta = 1.0, 1.0
    model += (
        alpha * lpSum(L_var[s] for s in range(TOTAL_SLOTS))
        - beta * lpSum(X[(i,s)] * (tasks[i]["priority"]*tasks[i]["difficulty"])
                       for i in range(n_tasks) for s in range(TOTAL_SLOTS))
    ), "Maximize_Leisure_Minus_Stress"

    # (a) Each task assigned exactly once
    for i in range(n_tasks):
        model += lpSum(X[(i,s)] for s in range(TOTAL_SLOTS)) == 1, f"Assign_{i}"

    # (b) Deadlines
    for i in range(n_tasks):
        dur = tasks[i]["duration"]
        dl = tasks[i]["deadline_slot"]
        for s in range(TOTAL_SLOTS):
            if s + dur - 1 > dl:
                model += (X[(i,s)] == 0), f"Deadline_{i}_{s}"

    # (c) No overlap
    for t in range(TOTAL_SLOTS):
        # sum of tasks occupying slot t <= 1
        in_conflict = []
        for i in range(n_tasks):
            d = tasks[i]["duration"]
            for st in range(TOTAL_SLOTS):
                if st <= t < st + d:
                    in_conflict.append(X[(i,st)])
        model += lpSum(in_conflict) <= 1, f"NoOverlap_{t}"

    # (d) Ask user for preferred scheduling window
    print("\nEnter your preferred scheduling window:")
    start_hour_str = input("Start hour (8-21, e.g. '8' for 8:00 AM): ").strip()
    end_hour_str = input("End hour (9-22, e.g. '17' for 5:00 PM): ").strip()

    # Default values if input is invalid
    try:
        start_hour = max(8, min(21, int(start_hour_str)))
    except:
        start_hour = 8  # Default to 8:00 AM

    try:
        end_hour = max(start_hour + 1, min(22, int(end_hour_str)))
    except:
        end_hour = 22  # Default to 10:00 PM (whole day)

    # Calculate slot offsets within each day based on hours
    slots_per_day = SLOTS_PER_DAY  # 56 slots per day
    start_slot_offset = (start_hour - 8) * 4  # Each hour has 4 slots
    end_slot_offset = (end_hour - 8) * 4  # Exclusive end

    print(f"Tasks will be scheduled between {start_hour}:00 and {end_hour}:00 each day.")

    # Add time window constraints to the model
    for i in range(n_tasks):
        dur = tasks[i]["duration"]
        for d in range(TOTAL_DAYS):
            day_start = d * slots_per_day

            # Prevent tasks from starting before start_hour
            for s in range(day_start, day_start + start_slot_offset):
                model += X[(i,s)] == 0, f"TooEarly_{i}_{s}"

            # Prevent tasks from ending after end_hour
            for s in range(day_start + end_slot_offset - dur + 1, day_start + slots_per_day):
                model += X[(i,s)] == 0, f"TooLate_{i}_{s}"

    # (e) Preference
    for i in range(n_tasks):
        pref = tasks[i]["preference"]
        allowed_slots = PREFERENCE_MAP[pref]
        for s in range(TOTAL_SLOTS):
            if s not in allowed_slots:
                model += X[(i,s)] == 0, f"Pref_{i}_{s}"

    # (f) Commitments
    for s in range(TOTAL_SLOTS):
        if commitments[s] == 15:
            # slot s is blocked
            for i in range(n_tasks):
                d = tasks[i]["duration"]
                for st in range(max(0, s-d+1), s+1):
                    model += X[(i,st)] == 0, f"Blocked_{i}_{st}_{s}"

    # (g) Leisure
    for s in range(TOTAL_SLOTS):
        occupying = []
        for i in range(n_tasks):
            d = tasks[i]["duration"]
            for st in range(TOTAL_SLOTS):
                if st <= s < st + d:
                    occupying.append(X[(i,st)])
        model += (Y[s] >= lpSum(occupying)), f"Used_{s}"

        free_mins = 15 - commitments[s]
        if free_mins <= 0:
            model += (L_var[s] <= 0), f"NoLeisure_{s}"
        else:
            model += (L_var[s] <= free_mins*(1 - Y[s])), f"LeisureBound_{s}"

    print(BRIGHT_CYAN + "\nSolving the model. Please wait..." + RESET)
    status = model.solve()
    print("Solver status:", LpStatus[status])

    if LpStatus[status] == "Optimal":
        print(BRIGHT_GREEN + "Optimal schedule found!\n" + RESET)

        # Collect schedule
        schedule_records = []
        for i in range(n_tasks):
            for s in range(TOTAL_SLOTS):
                if X[(i,s)].varValue > 0.5:
                    start_slot = s
                    end_slot   = s + tasks[i]["duration"] - 1
                    start_dt   = slot_to_datetime(start_slot)
                    end_dt     = slot_to_datetime(end_slot) + timedelta(minutes=15)
                    schedule_records.append({
                        "Task": tasks[i]["name"],
                        "Priority": tasks[i]["priority"],
                        "Difficulty": tasks[i]["difficulty"],
                        "DayIndex": start_slot // SLOTS_PER_DAY,
                        "StartSlot": start_slot,
                        "StartTime": start_dt,
                        "EndTime": end_dt,
                        "Duration(min)": 15 * tasks[i]["duration"]
                    })

        schedule_df = pd.DataFrame(schedule_records)
        schedule_df.sort_values(by=["DayIndex","StartSlot"], inplace=True)

        # Verify that all tasks are scheduled within the specified time window
        for _, row in schedule_df.iterrows():
            task_start_hour = row["StartTime"].hour
            task_end_hour = row["EndTime"].hour
            task_end_minute = row["EndTime"].minute

            # Check if outside the window
            if task_start_hour < start_hour or (task_end_hour > end_hour) or (task_end_hour == end_hour and task_end_minute > 0):
                print(BRIGHT_YELLOW + f"WARNING: Task '{row['Task']}' scheduled outside time window ({start_hour}:00-{end_hour}:00)" + RESET)
                print(f"  Scheduled at: {row['StartTime']} to {row['EndTime']}")

        # Summaries
        total_leisure = sum(L_var[s].varValue for s in range(TOTAL_SLOTS))
        total_stress  = sum(
            X[(i,s)].varValue * tasks[i]["priority"] * tasks[i]["difficulty"]
            for i in range(n_tasks)
            for s in range(TOTAL_SLOTS)
        )

        print(BRIGHT_MAGENTA + "="*50 + RESET)
        print(BRIGHT_MAGENTA + "            FINAL SCHEDULE            " + RESET)
        print(BRIGHT_MAGENTA + "="*50 + RESET)

        for day_idx in range(TOTAL_DAYS):
            day_slice = schedule_df[schedule_df["DayIndex"] == day_idx]
            if day_slice.empty:
                continue
            day_label = (DAY0 + timedelta(days=day_idx)).strftime("%a %Y-%m-%d")
            print(f"\n{BRIGHT_CYAN}=== Day {day_idx} ({day_label}) ==={RESET}")

            # ASCII table
            header = (
                "+---------------------+---------------------+----------------------------+\n"
                "|      Start Time     |       End Time      |           Task             |\n"
                "+---------------------+---------------------+----------------------------+"
            )
            print(header)
            for _, row in day_slice.iterrows():
                st_str = row["StartTime"].strftime("%b %d %H:%M")
                et_str = row["EndTime"].strftime("%b %d %H:%M")
                task_str = f'{row["Task"]} (P={row["Priority"]},D={row["Difficulty"]})'
                line = f"| {st_str:<19} | {et_str:<19} | {task_str:<26} |"
                print(line)
                print("+---------------------+---------------------+----------------------------+")

        print(BRIGHT_GREEN + f"\nTotal Leisure = {total_leisure:.1f} minutes" + RESET)
        print(BRIGHT_GREEN + f"Total Stress  = {total_stress:.1f}" + RESET)
        generate_html_visualization(schedule_df, commitments, blocked_labels, total_leisure, total_stress)
    else:
        print(BRIGHT_YELLOW + "No feasible solution found. Adjust constraints or tasks." + RESET)


if __name__ == "__main__":
    main()
