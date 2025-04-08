# Optimization Model for Weekly Task Scheduling (Gurobi Implementation)

## Overview

This document describes the mathematical optimization model used to generate a weekly task schedule using the Gurobi solver (`solve_schedule_gurobi`). The goal is to assign a start time to each task within a 7-day horizon (broken into 15-minute slots) while respecting various constraints (deadlines, commitments, preferences, daily limits) and optimizing for two main objectives: maximizing leisure time and minimizing a "stress" score associated with tasks.

**Time Horizon:**
*   Total Days: 7
*   Slots per Day: 56 (8:00 AM to 10:00 PM, 15-min slots)
*   Total Slots: 392 (indexed 0 to 391)

## Parameters and Inputs

*   **`tasks` (List of Dictionaries):** Each task has attributes: `id`, `name`, `priority`, `difficulty`, `duration_slots`, `deadline_slot`, `preference`.
*   **`commitments` (Dictionary):** Maps blocked global slots `s` to a value (e.g., 15).
*   **`alpha` (Float):** Weight factor for maximizing total leisure time.
*   **`beta` (Float):** Weight factor for minimizing total stress score.
*   **`daily_limit_slots` (Integer, Optional):** Maximum task slots allowed per day.

## Decision Variables

1.  **`X[i, s]` (Binary):** 1 if task `i` starts at slot `s`, 0 otherwise.
2.  **`Y[s]` (Binary):** 1 if slot `s` is occupied by any task, 0 otherwise.
3.  **`L_var[s]` (Continuous):** Amount of leisure time (0-15 minutes) in slot `s`.

## Objective Function

*   **Purpose:** Maximize total weighted leisure time minus total weighted stress. Stress is calculated based on priority and difficulty at the task's start time.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    obj_leisure = alpha * gp.quicksum(L_var[s] for s in range(TOTAL_SLOTS))
    obj_stress = beta * gp.quicksum(X[i, s] * (tasks[i]["priority"] * tasks[i]["difficulty"])
                                   for i in range(n_tasks) for s in range(TOTAL_SLOTS))
    m.setObjective(obj_leisure - obj_stress, GRB.MAXIMIZE)
    ```

## Constraints

**a) Task Assignment (Assign)**
*   **Purpose:** Ensures every task is scheduled exactly one time.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    m.addConstrs((X.sum(i, '*') == 1 for i in range(n_tasks)), name="Assign")
    ```

**b) Deadlines & Horizon (Deadline, HorizonEnd)**
*   **Purpose:** Ensures tasks finish by their deadline and fit within the planning horizon.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"]
        dl = tasks[i]["deadline_slot"]
        task_key = tasks[i].get('id', i)
        for s in range(TOTAL_SLOTS):
            # Deadline check
            if s + dur - 1 > dl:
                m.addConstr(X[i, s] == 0, name=f"Deadline_{task_key}_s{s}")
            # Horizon check
            if s + dur > TOTAL_SLOTS:
                m.addConstr(X[i, s] == 0, name=f"HorizonEnd_{task_key}_s{s}")
    ```

**c) No Overlap (NoOverlap)**
*   **Purpose:** Prevents multiple tasks from occupying the same time slot $t$.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    for t in range(TOTAL_SLOTS):
        occupying_tasks_vars = []
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            for s in range(max(0, t - dur + 1), t + 1):
                 if s + dur <= TOTAL_SLOTS: # Check if start is valid
                     occupying_tasks_vars.append(X[i, s])
        if occupying_tasks_vars:
             m.addConstr(gp.quicksum(occupying_tasks_vars) <= 1, name=f"NoOverlap_s{t}")
    ```

**d) Preferences (PrefWin)**
*   **Purpose:** Restricts task starting times to preferred windows.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    for i in range(n_tasks):
        # ... determine allowed_slots based on preference ...
        pref = tasks[i].get("preference", "any")
        task_key = tasks[i].get('id', i)
        # ... handle potential invalid preference ...
        allowed_slots = PREFERENCE_MAP.get(pref, PREFERENCE_MAP["any"])

        for s in range(TOTAL_SLOTS):
            if s not in allowed_slots:
                m.addConstr(X[i, s] == 0, name=f"PrefWin_{task_key}_s{s}")
    ```

**e) Commitments (CommitOverlap)**
*   **Purpose:** Prevents tasks from overlapping with committed slots.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    committed_slots = set(commitments.keys())
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"]
        task_key = tasks[i].get('id', i)
        for s in range(TOTAL_SLOTS):
            task_occupies = set(range(s, min(s + dur, TOTAL_SLOTS)))
            if task_occupies.intersection(committed_slots):
                m.addConstr(X[i, s] == 0, name=f"CommitOverlap_{task_key}_s{s}")
    ```

**f) Leisure Calculation & Y Link (Link_Y_Exact, NoLeisure_Committed, LeisureBound_NotCommitted)**
*   **Purpose:** Links the occupation variable $Y_s$ to task starts and calculates leisure $L_s$ based on occupation and commitments.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    for s in range(TOTAL_SLOTS):
        # Determine occupying_task_vars_sum (LinExpr of X[i, start] covering s)
        occupying_task_vars_sum = gp.LinExpr()
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            for start_slot in range(max(0, s - dur + 1), s + 1):
                if start_slot + dur <= TOTAL_SLOTS:
                    occupying_task_vars_sum.add(X[i, start_slot])

        # Link Y[s]
        m.addConstr(Y[s] == occupying_task_vars_sum, name=f"Link_Y_Exact_{s}")

        # Calculate leisure L_var[s]
        is_committed = 1 if s in commitments else 0
        if is_committed:
            m.addConstr(L_var[s] == 0, name=f"NoLeisure_Committed_{s}")
        else:
            m.addConstr(L_var[s] <= 15 * (1 - Y[s]), name=f"LeisureBound_NotCommitted_{s}")
            # L_var[s] >= 0 is handled by variable definition (lb=0)
    ```

**g) Daily Limits (DailyLimit_Day)**
*   **Purpose:** (Optional) Enforces a maximum number of task-occupied slots per day.
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    if daily_limit_slots is not None and daily_limit_slots >= 0:
        for d in range(TOTAL_DAYS):
            day_start_slot = d * SLOTS_PER_DAY
            day_end_slot = day_start_slot + SLOTS_PER_DAY
            daily_task_slots_sum = gp.quicksum(Y[s] for s in range(day_start_slot, day_end_slot))
            m.addConstr(daily_task_slots_sum <= daily_limit_slots, name=f"DailyLimit_Day_{d}")
    ```

## Solver Notes

*   This model is implemented using Gurobi (`solve_schedule_gurobi`).
*   Gurobi is a high-performance commercial solver suitable for complex Mixed-Integer Programming (MIP) problems like this one. It offers advanced features like automatic Irreducible Inconsistent Subsystem (IIS) computation for debugging infeasible models.

## Output

If a feasible or optimal solution is found, the solver returns:
*   The status (e.g., "Optimal", "Feasible", "Time Limit Reached").
*   A list (`schedule`) containing dictionaries for each scheduled task, including its ID, name, assigned `start_slot`, calculated `end_slot`, corresponding `startTime` and `endTime` (as ISO strings), duration, priority, difficulty, and preference.
*   The calculated `total_leisure` in minutes.
*   The calculated `total_stress` score.
*   The time taken by the solver (`solve_time_seconds`).
