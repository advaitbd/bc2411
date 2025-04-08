# Optimization Model for Weekly Task Scheduling

## Overview

This document describes the mathematical optimization model used to generate a weekly task schedule. The goal is to assign a start time to each task within a 7-day horizon (broken into 15-minute slots) while respecting various constraints (deadlines, commitments, preferences, daily limits) and optimizing for two main objectives: maximizing leisure time and minimizing a "stress" score associated with tasks.

The model is implemented using both Gurobi (`solve_schedule_gurobi`) and PuLP (`solve_schedule_pulp`) libraries. The underlying logic and formulation are equivalent in both implementations.

**Time Horizon:**
*   **Total Days:** $D = 7$
*   **Slots per Day:** $S_{day} = 56$ (8:00 AM to 10:00 PM, 15-min slots)
*   **Total Slots:** $S_{total} = D \times S_{day} = 392$ (indexed $s = 0, ..., S_{total}-1$)

## Parameters and Inputs

*   **Tasks ($T$):** A set of tasks, indexed by $i$. Each task $i$ has attributes:
    *   $p_i$: Priority
    *   $d_i$: Difficulty
    *   $dur_i$: Duration (in slots)
    *   $dl_i$: Deadline slot index (task must finish by the end of this slot)
    *   $pref_i$: Preference type ("any", "morning", "afternoon", "evening")
    *   $AllowedSlots_i$: Set of slot indices `s` where task `i` is allowed to *start* based on $pref_i$.
*   **Commitments ($C$):** A set of slot indices $s$ that are unavailable/committed.
*   **$\alpha$ (Float):** Weight factor for maximizing total leisure time.
*   **$\beta$ (Float):** Weight factor for minimizing total stress score.
*   **$Limit_{daily}$ (Integer, Optional):** Maximum task slots allowed per day.

## Decision Variables

1.  **$X_{i,s}$ (Binary):**
    *   $X_{i,s} = 1$ if task $i \in T$ **starts** at slot $s \in \{0, ..., S_{total}-1\}$.
    *   $X_{i,s} = 0$ otherwise.

2.  **$Y_{s}$ (Binary):**
    *   $Y_{s} = 1$ if slot $s \in \{0, ..., S_{total}-1\}$ is **occupied** by any task.
    *   $Y_{s} = 0$ otherwise.

3.  **$L_{s}$ (Continuous):**
    *   Represents the amount of **leisure time (in minutes)** within slot $s \in \{0, ..., S_{total}-1\}$.
    *   $0 \le L_{s} \le 15$.

## Objective Function

**Purpose:** Maximize total weighted leisure time minus total weighted stress.

**LaTeX:**
```latex
\text{Maximize} \quad \alpha \sum_{s=0}^{S_{total}-1} L_s - \beta \sum_{i \in T} \sum_{s=0}^{S_{total}-1} (p_i \times d_i) X_{i,s}
```
**Note:** Stress $(p_i \times d_i)$ is associated with the *start* of the task $i$ at slot $s$.

**Gurobi Implementation:**
```python
# Gurobi
obj_leisure = alpha * gp.quicksum(L_var[s] for s in range(TOTAL_SLOTS))
obj_stress = beta * gp.quicksum(X[i, s] * (tasks[i]["priority"] * tasks[i]["difficulty"])
                               for i in range(n_tasks) for s in range(TOTAL_SLOTS))
m.setObjective(obj_leisure - obj_stress, GRB.MAXIMIZE)
```

**PuLP Implementation:**
```python
# PuLP
model += (
    alpha * lpSum(L_var[s] for s in range(TOTAL_SLOTS))
    - beta * lpSum(X[(i, s)] * (tasks[i]["priority"] * tasks[i]["difficulty"])
                   for i in range(n_tasks) for s in range(TOTAL_SLOTS))
), "Maximize_Leisure_Minus_Stress"
```

## Constraints

**a) Task Assignment (Assign)**
*   **Purpose:** Ensures every task is scheduled exactly one time.
*   **LaTeX:**
    ```latex
    \sum_{s=0}^{S_{total}-1} X_{i,s} = 1 \quad \forall i \in T
    ```
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    m.addConstrs((X.sum(i, '*') == 1 for i in range(n_tasks)), name="Assign")
    ```
*   **PuLP Implementation:**
    ```python
    # PuLP
    for i in range(n_tasks):
        task_key = tasks[i].get('id', i)
        model += lpSum(X[(i, s)] for s in range(TOTAL_SLOTS)) == 1, f"Assign_{task_key}"
    ```

**b) Deadlines & Horizon (Deadline, HorizonEnd)**
*   **Purpose:** Ensures tasks finish by their deadline and fit within the planning horizon.
*   **LaTeX:**
    ```latex
    X_{i,s} = 0 \quad \forall i \in T, \forall s \in \{0, ..., S_{total}-1\} \text{ such that } (s + dur_i - 1 > dl_i) \lor (s + dur_i > S_{total})
    ```
    (This means $X_{i,s}$ must be 0 if starting at $s$ would cause the task to finish after its deadline $dl_i$ or extend beyond the total available slots $S_{total}$.)
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
*   **PuLP Implementation:**
    ```python
    # PuLP
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"]
        dl = tasks[i]["deadline_slot"]
        task_key = tasks[i].get('id', i)
        for s in range(TOTAL_SLOTS):
            # Deadline check
            if s + dur - 1 > dl:
                 model += (X[(i, s)] == 0), f"Deadline_{task_key}_s{s}"
            # Horizon check
            if s + dur > TOTAL_SLOTS:
                 model += (X[(i, s)] == 0), f"HorizonEnd_{task_key}_s{s}"
    ```

**c) No Overlap (NoOverlap)**
*   **Purpose:** Prevents multiple tasks from occupying the same time slot $t$.
*   **LaTeX:**
    ```latex
    \sum_{i \in T} \sum_{s = \max(0, t - dur_i + 1)}^{t} X_{i,s} \le 1 \quad \forall t \in \{0, ..., S_{total}-1\}
    ```
    (The inner sum is over all start times $s$ for task $i$ such that task $i$ would be active during slot $t$.)
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
*   **PuLP Implementation:**
    ```python
    # PuLP
    for t in range(TOTAL_SLOTS):
        occupying_tasks_vars = []
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            for s in range(max(0, t - dur + 1), t + 1):
                 if s + dur <= TOTAL_SLOTS: # Check if start is valid
                     occupying_tasks_vars.append(X[(i, s)])
        if occupying_tasks_vars:
             model += lpSum(occupying_tasks_vars) <= 1, f"NoOverlap_s{t}"
    ```

**d) Preferences (PrefWin)**
*   **Purpose:** Restricts task starting times to preferred windows.
*   **LaTeX:**
    ```latex
    X_{i,s} = 0 \quad \forall i \in T, \forall s \notin AllowedSlots_i
    ```
*   **Gurobi Implementation:**
    ```python
    # Gurobi
    for i in range(n_tasks):
        # ... determine allowed_slots based on preference ...
        allowed_slots = PREFERENCE_MAP.get(pref, PREFERENCE_MAP["any"])
        for s in range(TOTAL_SLOTS):
            if s not in allowed_slots:
                m.addConstr(X[i, s] == 0, name=f"PrefWin_{task_key}_s{s}")
    ```
*   **PuLP Implementation:**
    ```python
    # PuLP
    for i in range(n_tasks):
        # ... determine allowed_slots based on preference ...
        allowed_slots = PREFERENCE_MAP.get(pref, PREFERENCE_MAP["any"])
        for s in range(TOTAL_SLOTS):
            if s not in allowed_slots:
                model += X[(i, s)] == 0, f"PrefWin_{task_key}_s{s}"
    ```

**e) Commitments (CommitOverlap)**
*   **Purpose:** Prevents tasks from overlapping with committed slots $C$.
*   **LaTeX:**
    ```latex
    X_{i,s} = 0 \quad \forall i \in T, \forall s \text{ such that } \{s, s+1, ..., s + dur_i - 1\} \cap C \neq \emptyset
    ```
    (If the set of slots occupied by task $i$ starting at $s$ intersects with the set of committed slots $C$, then $X_{i,s}$ must be 0.)
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
*   **PuLP Implementation:**
    ```python
    # PuLP
    committed_slots = set(commitments.keys())
    for i in range(n_tasks):
        dur = tasks[i]["duration_slots"]
        task_key = tasks[i].get('id', i)
        for s in range(TOTAL_SLOTS):
             task_occupies = {slot for slot in range(s, s + dur) if slot < TOTAL_SLOTS}
             if task_occupies.intersection(committed_slots):
                 model += X[(i, s)] == 0, f"CommitOverlap_{task_key}_s{s}"
    ```

**f) Leisure Calculation & Y Link (Link_Y_Exact, NoLeisure_Committed, LeisureBound_NotCommitted)**
*   **Purpose:** Links $Y_s$ to task occupation and calculates leisure $L_s$.
*   **LaTeX:**
    1.  Link $Y_s$:
        ```latex
        Y_s = \sum_{i \in T} \sum_{start = \max(0, s - dur_i + 1)}^{s} X_{i,start} \quad \forall s \in \{0, ..., S_{total}-1\}
        ```
        (This sum is exactly the one from the No Overlap constraint, ensuring $Y_s$ is 0 or 1)
    2.  Calculate $L_s$:
        ```latex
        L_s = 0 \quad \forall s \in C
        ```
        ```latex
        L_s \le 15 \times (1 - Y_s) \quad \forall s \notin C
        ```
        ```latex
        L_s \ge 0 \quad \forall s
        ```
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
*   **PuLP Implementation:**
    ```python
    # PuLP
    for s in range(TOTAL_SLOTS):
        # Determine occupying_task_vars (list of X[(i, start)] covering s)
        occupying_task_vars = []
        for i in range(n_tasks):
            dur = tasks[i]["duration_slots"]
            for start_slot in range(max(0, s - dur + 1), s + 1):
                 if start_slot + dur <= TOTAL_SLOTS:
                     occupying_task_vars.append(X[(i, start_slot)])

        # Link Y[s]
        if occupying_task_vars:
             model += Y[s] == lpSum(occupying_task_vars), f"Link_Y_Exact_{s}"
        else:
             model += Y[s] == 0, f"Force_Y_zero_{s}"

        # Calculate leisure L_var[s]
        is_committed = 1 if s in commitments else 0
        if is_committed:
             model += L_var[s] == 0, f"NoLeisure_Committed_{s}"
        else:
             model += L_var[s] <= 15 * (1 - Y[s]), f"LeisureBound_NotCommitted_{s}"
             # L_var[s] >= 0 handled by LpVariable definition
    ```

**g) Daily Limits (DailyLimit_Day)**
*   **Purpose:** (Optional) Enforces a maximum number of task-occupied slots per day.
*   **LaTeX:**
    Let $Slots_{day, d} = \{s \mid d \times S_{day} \le s < (d+1) \times S_{day}\}$ be the set of slots for day $d$.
    ```latex
    \sum_{s \in Slots_{day, d}} Y_s \le Limit_{daily} \quad \forall d \in \{0, ..., D-1\}
    ```
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
*   **PuLP Implementation:**
    ```python
    # PuLP
    if daily_limit_slots is not None and daily_limit_slots >= 0:
         for d in range(TOTAL_DAYS):
             day_start_slot = d * SLOTS_PER_DAY
             day_end_slot = day_start_slot + SLOTS_PER_DAY
             daily_task_slots_sum = lpSum(Y[s] for s in range(day_start_slot, day_end_slot))
             model += daily_task_slots_sum <= daily_limit_slots, f"DailyLimit_Day_{d}"
    ```

## Solver Notes

*   Both the Gurobi and PuLP implementations use the exact same variable definitions, objective function structure, and constraint logic described above.
*   Gurobi often provides superior performance for larger or more complex Mixed-Integer Programming (MIP) problems like this one and offers more advanced features (e.g., automatic IIS computation for infeasible models).
*   PuLP (using the default CBC solver) is open-source and generally sufficient for moderately sized problems.

## Output

If a feasible or optimal solution is found, the solver returns:
*   The status (e.g., "Optimal", "Feasible", "Time Limit Reached").
*   A list (`schedule`) containing dictionaries for each scheduled task, including its ID, name, assigned `start_slot`, calculated `end_slot`, corresponding `startTime` and `endTime` (as ISO strings), duration, priority, difficulty, and preference.
*   The calculated `total_leisure` in minutes.
*   The calculated `total_stress` score.
*   The time taken by the solver (`solve_time_seconds`).
