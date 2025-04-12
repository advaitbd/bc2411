import React from "react";
import { X } from "lucide-react";

interface ModelExplanationProps {
  onClose: () => void;
}

const ModelExplanation: React.FC<ModelExplanationProps> = ({ onClose }) => {
  // Updated to match explain.html structure and constraint order, keeping dark theme
  const explanationHtml = `
<!doctype html>
<html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Scheduler Logic Visualization</title>
        <style>
            /* Styles adapted from explain.html for modal context & dark theme */
            .explanation-content {
                font-family: sans-serif;
                line-height: 1.6;
                color: #e5e7eb; /* Light gray text */
                background-color: #1f2937; /* gray-800 */
                padding: 20px;
                max-height: 80vh;
                overflow-y: auto;
                border-radius: 8px;
                border: 1px solid #4b5563; /* gray-600 */
            }
            .explanation-content h1,
            .explanation-content h2,
            .explanation-content h3 {
                border-bottom: 1px solid #4b5563; /* gray-600 */
                padding-bottom: 5px;
                margin-top: 1.5em;
                margin-bottom: 0.8em;
                color: #f3f4f6; /* Lighter headings */
            }
            .explanation-content h1 { font-size: 1.8em; margin-top: 0; }
            .explanation-content h2 { font-size: 1.4em; }
            .explanation-content h3 { font-size: 1.15em; }

            .explanation-content table {
                border-collapse: collapse;
                margin-bottom: 20px;
                width: 100%;
                table-layout: fixed;
                background-color: #374151; /* gray-700 */
            }
            .explanation-content th,
            .explanation-content td {
                border: 1px solid #4b5563; /* gray-600 */
                padding: 4px;
                text-align: center;
                font-size: 10px;
                word-wrap: break-word;
                color: #e5e7eb; /* Light gray text */
            }
            .explanation-content th {
                background-color: #4b5563; /* gray-600 */
                color: #f9fafb; /* Off-white */
                font-weight: bold;
            }
            .explanation-content .slot {
                min-width: 30px;
                height: 35px; /* Slightly taller */
                position: relative;
                background-color: #374151; /* Default: Dark background */
                vertical-align: top;
                color: #d1d5db; /* gray-300 */
            }
             .explanation-content .slot-available { /* Explicit available style */
                 background-color: #3f4b5a; /* Slightly lighter gray */
                 color: #e5e7eb;
            }
            .explanation-content .slot-index {
                font-weight: bold;
                color: #9ca3af; /* gray-400 */
                display: block;
                margin-bottom: 2px;
                font-size: 9px;
            }
            .explanation-content .slot-time {
                font-size: 9px;
                color: #9ca3af; /* gray-400 */
                display: block;
            }
            .explanation-content code {
                background-color: #4b5563; /* gray-600 */
                padding: 2px 5px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.9em;
                color: #f0fdf4; /* light green */
            }
            .explanation-content ul { list-style: disc; margin-left: 20px; margin-bottom: 1em;}
            .explanation-content li { margin-bottom: 0.3em; }
            .explanation-content strong { color: #c4b5fd; } /* purple-300 */
            .explanation-content .highlight { color: #fde047; } /* yellow-300 */

            /* --- Constraint Visualization Styles (adapted for dark theme) --- */
            .explanation-content .committed { /* gray-600 */
                background-color: #4b5563; color: white;
            }
            .explanation-content .task-occupied { /* blue-500 */
                background-color: #3b82f6; color: white;
            }
            .explanation-content .disallowed-deadline { /* red-500 */
                background-color: #ef4444; color: white;
            }
            .explanation-content .disallowed-preference { /* gray-500 */
                background-color: #6b7280; color: #e5e7eb;
            }
            .explanation-content .disallowed-commitment-start { /* orange-500 */
                background-color: #f97316; color: white;
            }
             .explanation-content .disallowed-overlap-start { /* purple-500 */
                background-color: #a855f7; color: white;
            }
             .explanation-content .disallowed-hard-task { /* fuchsia-500 - Used for hard task limit visualization */
                background-color: #d946ef; color: white;
            }
            .explanation-content .leisure-yes { /* green-500 */
                background-color: #22c55e; color: white;
            }
            .explanation-content .leisure-no { /* red-500 */
                background-color: #ef4444; color: white;
            }
            .explanation-content .filtered-out { /* stone-500 */
                background-color: #78716c; color: #e5e7eb; text-decoration: line-through;
            }
             .explanation-content .hard-task-row { /* No specific background, just border */
                border: 2px solid #facc15; /* yellow-400 */
             }
            /* Add a specific style for visualizing disallowed hard task START slots */
             .explanation-content .hard-task-day-blocked {
                 background-color: #d946ef; /* fuchsia-500 */
                 color: white;
             }


            .explanation-content .legend {
                margin-bottom: 20px;
                padding: 10px;
                border: 1px solid #4b5563; /* gray-600 */
                background-color: #374151; /* gray-700 */
                font-size: 0.9em;
            }
            .explanation-content .legend span {
                display: inline-block;
                width: 15px;
                height: 15px;
                margin-right: 5px;
                vertical-align: middle;
                border: 1px solid #9ca3af; /* gray-400 */
            }
        </style>
    </head>
    <body>
        <div class="explanation-content">
             <h1>Scheduler Logic Explained</h1>

            <p>
                This page illustrates the core logic behind the task scheduling optimization. The goal is to assign tasks to 15-minute time slots over a 7-day period (8am to 10pm daily) while respecting various constraints and maximizing leisure time / minimizing stress.
            </p>
            <p>
                The system uses <strong>Day 0 (Today, 8am - 10pm)</strong> which corresponds to global slots <strong>0 to 55</strong> as examples. There are 56 slots per day, totaling 392 slots over 7 days.
            </p>

            <div class="legend">
                <strong>General Legend:</strong><br />
                <span style="background-color: #3f4b5a"></span> Available Slot &nbsp;
                <span class="committed"></span> Committed Slot &nbsp;
                <span class="task-occupied"></span> Task Occupied &nbsp;
                <span class="disallowed-deadline"></span> START Invalidated (Deadline/Horizon) &nbsp;
                <span class="disallowed-preference"></span> START Invalidated (Preference) &nbsp;
                <span class="disallowed-commitment-start"></span> START Invalidated (Commitment Conflict) &nbsp;
                <span class="disallowed-overlap-start"></span> START Invalidated (Potential Overlap) &nbsp;
                <span class="hard-task-day-blocked"></span> START Invalidated (Hard Task Limit) &nbsp;
                <span class="leisure-yes"></span> Has Leisure (15 min) &nbsp;
                <span class="leisure-no"></span> No Leisure (0 min) &nbsp;
                <br />
                <strong>Task Table Specific:</strong><br />
                <span class="filtered-out"></span> Task Filtered Out (Pi Condition) &nbsp;
                <span style="border: 2px solid #facc15; background-color: #374151;"></span> Hard Task (Difficulty >= Threshold) &nbsp;
            </div>

            <h2>Basic Time Slot Grid (Day 0: Slots 0-55)</h2>
             <p>
                Each cell represents a 15-minute slot. Top number: global slot index, bottom: start time. (Example subset shown).
            </p>
            <table>
                <thead>
                    <tr>
                        <th colspan="8">Day 0 (Example: 8am - 10am)</th>
                    </tr>
                    <tr>
                        <th>8:00</th><th>8:15</th><th>8:30</th><th>8:45</th><th>9:00</th><th>9:15</th><th>9:30</th><th>9:45</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="slot slot-available"><span class="slot-index">0</span><span class="slot-time">08:00</span></td>
                        <td class="slot slot-available"><span class="slot-index">1</span><span class="slot-time">08:15</span></td>
                        <td class="slot slot-available"><span class="slot-index">2</span><span class="slot-time">08:30</span></td>
                        <td class="slot slot-available"><span class="slot-index">3</span><span class="slot-time">08:45</span></td>
                        <td class="slot slot-available"><span class="slot-index">4</span><span class="slot-time">09:00</span></td>
                        <td class="slot slot-available"><span class="slot-index">5</span><span class="slot-time">09:15</span></td>
                        <td class="slot slot-available"><span class="slot-index">6</span><span class="slot-time">09:30</span></td>
                        <td class="slot slot-available"><span class="slot-index">7</span><span class="slot-time">09:45</span></td>
                    </tr>
                </tbody>
            </table>

            <h2>Step 1: Task Pre-filtering (Pi Condition)</h2>
            <p>
                <strong>Intuition:</strong> Before scheduling, tasks are evaluated to see if they provide sufficient duration relative to their difficulty and priority. Tasks that are too short for their combined difficulty/priority are filtered out and not considered for scheduling. This implements the <code>Pi &ge; 0.7</code> requirement.
            </p>
            <p>
                <strong>Model:</strong> A task <code>i</code> is kept for scheduling (added to set <code>T</code>) only if
                <code>Duration_min(i) &ge; (Difficulty(i) * Priority(i)) * ln(10/3)</code>.
            </p>
            <p><strong>Example:</strong> Constant <code>ln(10/3) &approx; 1.204</code>.</p>
            <ul>
                <li>
                    Task X: Dur=60min, Diff=3, Prio=4. Required = (3*4)*1.204 = 14.45 min. Since 60 &ge; 14.45, Task X is <strong class="highlight">schedulable</strong>.
                </li>
                <li>
                    Task Y: Dur=15min, Diff=5, Prio=3. Required = (5*3)*1.204 = 18.06 min. Since 15 < 18.06, Task Y is <strong class="highlight">filtered out</strong>.
                </li>
            </ul>
            <p><strong>Visualization (Example Task List):</strong></p>
            <table>
                <thead>
                    <tr><th>Task</th><th>Duration (min)</th><th>Difficulty</th><th>Priority</th><th>Required Min Duration</th><th>Schedulable?</th></tr>
                </thead>
                <tbody>
                    <tr><td>Task X</td><td>60</td><td>3</td><td>4</td><td>~15 min</td><td class="leisure-yes">Yes</td></tr>
                    <tr class="filtered-out"><td>Task Y</td><td>15</td><td>5</td><td>3</td><td>~19 min</td><td class="leisure-no">No</td></tr>
                    <tr><td>Task Z</td><td>30</td><td>2</td><td>2</td><td>~5 min</td><td class="leisure-yes">Yes</td></tr>
                </tbody>
            </table>
            <p>
                The subsequent constraints and optimization only apply to the tasks marked "Yes" (Set <code>T</code>).
            </p>

            <h2>Step 2: Optimization Constraints (Applied to Schedulable Tasks)</h2>

             <!-- Constraint (a): Mandatory Task Assignment (LaTeX 6.1) -->
            <h3>(a) Mandatory Task Assignment</h3>
            <p>
                <strong>Intuition:</strong> Every task that passed the Pi pre-filter (i.e., is in set <code>T</code>) must be scheduled exactly once.
            </p>
            <p>
                <strong>Model:</strong> <code>Sum(X[i, s] for s in all_slots) = 1</code> for each task <code>i</code> in <code>T</code>.
            </p>
            <p>
                <strong>Visualization:</strong> This ensures the final schedule includes one start time for every task deemed "schedulable" in Step 1 (like X and Z above). If it's impossible to fit all schedulable tasks due to other constraints, the model will report infeasibility.
            </p>

            <!-- Constraint (b): Hard Task Limitation (LaTeX 6.2) -->
            <h3>(b) Hard Task Limitation</h3>
            <p>
                <strong>Intuition:</strong> Schedule at most one "hard" task (difficulty &ge; threshold, e.g., 4) per day among the schedulable tasks to prevent overwhelm.
            </p>
            <p>
                <strong>Model:</strong> <code>Sum(X[i, s] for i in T_hard for s in day_d_slots) &le; 1</code> for each day <code>d</code>, where <code>T_hard</code> includes only tasks from set <code>T</code> with difficulty at or above the threshold.
            </p>
            <p>
                <strong>Example:</strong> Hard Threshold = 4. Task C (Diff=4, Schedulable) and Task D (Diff=5, Schedulable) are both hard.
            </p>
            <ul>
                <li>If Task C is scheduled to start on Day 1, Task D <strong class="highlight">cannot</strong> also be scheduled to <strong class="highlight">start</strong> on Day 1.</li>
                <li>Task D must start on a different day (e.g., Day 0 or Day 2).</li>
            </ul>
            <p><strong>Visualization (Hard Task Distribution):</strong></p>
            <table>
                 <thead>
                     <tr><th>Task</th><th>Difficulty</th><th>Schedulable?</th><th>Hard? (&ge;4)</th><th>Scheduled Day</th></tr>
                 </thead>
                 <tbody>
                     <tr><td>Task A</td><td>3</td><td>Yes</td><td>No</td><td>Day 0</td></tr>
                     <tr class="filtered-out hard-task-row"><td>Task B (Hard but filtered)</td><td>4</td><td class="leisure-no">No</td><td>Yes</td><td>N/A (Filtered)</td></tr>
                     <tr class="hard-task-row"><td>Task C</td><td>4</td><td class="leisure-yes">Yes</td><td>Yes</td><td>Day 1</td></tr>
                     <tr class="hard-task-row"><td>Task D</td><td>5</td><td class="leisure-yes">Yes</td><td>Yes</td><td>Day 2</td></tr>
                     <tr><td>Task E</td><td>1</td><td>Yes</td><td>No</td><td>Day 1</td> <!-- Can share day with hard task C --></tr>
                 </tbody>
             </table>
            <p>
                Only <strong class="highlight">schedulable hard tasks</strong> (C, D) are subject to the one-per-day start limit. Filtered hard tasks (B) don't count. Non-hard tasks (A, E) can share days with hard tasks.
            </p>
            <p><strong>Visualization (Potential start slots for Task D on Day 1, if Task C starts on Day 1):</strong></p>
             <table>
                 <thead><tr><th colspan=4>Day 1 Slots (assuming Task C [Hard] starts today)</th></tr></thead>
                 <tbody>
                    <tr>
                        <td class="slot slot-available hard-task-row" title="Task D is Hard (Diff=5)">
                             <span class="slot-index">60</span><span class="slot-time">09:00</span>(D?)
                        </td>
                        <td class="slot hard-task-day-blocked hard-task-row" title="Task D (Hard) cannot START today, Task C (Hard) already starts today.">
                             <span class="slot-index">61</span><span class="slot-time">09:15</span> Blocked
                        </td>
                         <td class="slot hard-task-day-blocked hard-task-row" title="Task D (Hard) cannot START today...">
                             <span class="slot-index">62</span><span class="slot-time">09:30</span> Blocked
                         </td>
                         <td class="slot hard-task-day-blocked hard-task-row" title="Task D (Hard) cannot START today...">
                             <span class="slot-index">63</span><span class="slot-time">09:45</span> Blocked
                         </td>
                    </tr>
                </tbody>
            </table>


            <!-- Constraint (c): Deadlines & Horizon (LaTeX 6.3) -->
            <h3>(c) Deadlines & Horizon</h3>
            <p>
                <strong>Intuition:</strong> Schedulable tasks must finish by their deadline and fit entirely within the 7-day window.
            </p>
            <p>
                <strong>Model:</strong> <code>X[i, s] = 0</code> for task <code>i</code> in <code>T</code> if starting at slot <code>s</code> means its last slot (<code>s + dur_i - 1</code>) is after its deadline slot (<code>dl_i</code>), OR if the task extends beyond the horizon (<code>s + dur_i > TOTAL_SLOTS</code>).
            </p>
            <p>
                <strong>Example:</strong> Schedulable Task A (duration 4 slots, deadline slot <code>dl_A = 6</code>). Where can it NOT start?
            </p>
            <ul>
                <li>Start at <code>s=3</code>: Occupies 3, 4, 5, 6. Last slot is 6. OK (<code>6 &le; 6</code>).</li>
                <li>Start at <code>s=4</code>: Occupies 4, 5, 6, 7. Last slot is 7. VIOLATES deadline (<code>7 > 6</code>). <code>X[A, 4]</code> must be 0.</li>
                <li>...and so on for <code>s=5, 6, ...</code></li>
            </ul>
             <p><strong>Visualization (Slots near deadline 6 for Task A):</strong></p>
            <table>
                <tbody>
                    <tr>
                        <td class="slot slot-available" title="Task A (dur=4, dl=6) CAN start here (ends slot 6)"><span class="slot-index">3</span><span class="slot-time">08:45</span></td>
                        <td class="slot disallowed-deadline" title="Task A cannot START here (would end slot 7 > dl=6)"><span class="slot-index">4</span><span class="slot-time">09:00</span></td>
                        <td class="slot disallowed-deadline" title="Task A cannot START here (would end slot 8 > dl=6)"><span class="slot-index">5</span><span class="slot-time">09:15</span></td>
                        <td class="slot disallowed-deadline" title="Task A cannot START here (would end slot 9 > dl=6)"><span class="slot-index">6</span><span class="slot-time">09:30</span></td>
                    </tr>
                </tbody>
            </table>


            <!-- Constraint (d): No Overlap (LaTeX 6.4) -->
            <h3>(d) No Overlap</h3>
             <p>
                <strong>Intuition:</strong> Only one scheduled task (from set <code>T</code>) can be active in any given time slot.
            </p>
            <p>
                <strong>Model:</strong> For any slot <code>t</code>, the sum of <code>X[i, s]</code> for all tasks <code>i</code> in <code>T</code> that would be *active* during slot <code>t</code> (i.e., started at an <code>s</code> such that <code>s &le; t < s + dur_i</code>) must be &le; 1.
            </p>
            <p>
                <strong>Example:</strong> Schedulable Task B (duration 3 slots) is scheduled to start at <code>s=5</code> (occupies 5, 6, 7). Can Schedulable Task C (duration 2 slots) start at <code>s=6</code>?
            </p>
            <ul>
                <li>Task B occupies slots 5, 6, 7.</li>
                <li>Task C starting at <code>s=6</code> would occupy slots 6, 7.</li>
                <li>This creates an overlap in slots 6 and 7.</li>
                <li>The constraint prevents this. If <code>X[B, 5] = 1</code>, then <code>X[C, 6]</code> must be 0. Similarly, Task C cannot start at s=7 either (would overlap slot 7).</li>
            </ul>
            <p><strong>Visualization (If Task B starts at 5):</strong></p>
             <table>
                 <thead><tr><th colspan=5>Example Slots (Task B starts slot 5)</th></tr></thead>
                 <tbody>
                    <tr>
                        <td class="slot slot-available" title="Task C (dur=2) could start here (occupies 4, 5)"><span class="slot-index">4</span><span class="slot-time">09:00</span></td>
                        <td class="slot task-occupied disallowed-overlap-start" title="Task B occupies. Task C cannot start here (overlap 5,6)"><span class="slot-index">5</span><span class="slot-time">09:15</span>(B)</td>
                        <td class="slot task-occupied disallowed-overlap-start" title="Task B occupies. Task C cannot start here (overlap 6,7)"><span class="slot-index">6</span><span class="slot-time">09:30</span>(B)</td>
                        <td class="slot task-occupied disallowed-overlap-start" title="Task B occupies. Task C cannot start here (overlap 7)"><span class="slot-index">7</span><span class="slot-time">09:45</span>(B)</td>
                        <td class="slot slot-available" title="Task C could start here (occupies 8, 9)"><span class="slot-index">8</span><span class="slot-time">10:00</span></td>
                    </tr>
                </tbody>
            </table>


            <!-- Constraint (e): Preferences (LaTeX 6.5) -->
            <h3>(e) Preferences</h3>
            <p>
                <strong>Intuition:</strong> Schedulable tasks (from set <code>T</code>) should start only within their preferred time windows (morning, afternoon, evening, or any).
            </p>
            <p>
                <strong>Model:</strong> <code>X[i, s] = 0</code> if slot <code>s</code> is not in the <code>AllowedSlots_i</code> set for task <code>i</code>'s preference.
            </p>
            <p>
                <strong>Example:</strong> Schedulable Task D has preference "morning" (slots 0-15 on any day). Can it start at slot <code>s=18</code> (12:30 PM on Day 0)?
            </p>
            <ul>
                <li>Slot 18 corresponds to 12:30 PM, which is considered "afternoon".</li>
                <li>The constraint forces <code>X[D, 18] = 0</code> because 18 is not in the set of morning slots.</li>
            </ul>
             <p><strong>Visualization (Morning preference for Task D):</strong></p>
            <table>
                <thead><tr><th colspan=5>Example Slots (Task D has Morning preference)</th></tr></thead>
                <tbody>
                    <tr>
                        <td class="slot slot-available" title="Task D (Morning pref) can START here"><span class="slot-index">15</span><span class="slot-time">11:45</span></td>
                        <td class="slot disallowed-preference" title="Task D cannot START here (Afternoon slot)"><span class="slot-index">16</span><span class="slot-time">12:00</span></td>
                        <td class="slot disallowed-preference" title="Task D cannot START here (Afternoon slot)"><span class="slot-index">17</span><span class="slot-time">12:15</span></td>
                        <td class="slot disallowed-preference" title="Task D cannot START here (Afternoon slot)"><span class="slot-index">18</span><span class="slot-time">12:30</span></td>
                        <td class="slot disallowed-preference" title="... etc. Task D cannot start in afternoon/evening slots">...</td>
                    </tr>
                </tbody>
            </table>


            <!-- Constraint (f): Commitments (LaTeX 6.6) -->
            <h3>(f) Commitments</h3>
             <p>
                <strong>Intuition:</strong> Scheduled tasks (from set <code>T</code>) cannot overlap with pre-existing fixed commitments.
            </p>
            <p>
                <strong>Model:</strong> <code>X[i, s] = 0</code> if the set of slots task <code>i</code> in <code>T</code> would occupy starting at <code>s</code> (i.e., <code>{s, s+1, ..., s + dur_i - 1}</code>) has any intersection with the set of committed slots <code>C</code>.
            </p>
            <p>
                <strong>Example:</strong> There's a commitment at slot <code>s=10</code>. Schedulable Task E has duration 3 slots. Where can it NOT start?
            </p>
            <ul>
                <li>Start at <code>s=7</code>: Occupies {7, 8, 9}. No overlap with {10}. OK.</li>
                <li>Start at <code>s=8</code>: Occupies {8, 9, 10}. Overlaps slot 10. INVALID START. <code>X[E, 8] = 0</code>.</li>
                <li>Start at <code>s=9</code>: Occupies {9, 10, 11}. Overlaps slot 10. INVALID START. <code>X[E, 9] = 0</code>.</li>
                <li>Start at <code>s=10</code>: Occupies {10, 11, 12}. Overlaps slot 10. INVALID START. <code>X[E, 10] = 0</code>.</li>
                <li>Start at <code>s=11</code>: Occupies {11, 12, 13}. No overlap with {10}. OK.</li>
            </ul>
            <p><strong>Visualization (Commitment at slot 10):</strong></p>
            <table>
                 <thead><tr><th colspan=5>Example Slots (Commitment at slot 10)</th></tr></thead>
                 <tbody>
                    <tr>
                        <td class="slot slot-available" title="Task E (dur=3) can START here (occupies 7,8,9)"><span class="slot-index">7</span><span class="slot-time">09:45</span></td>
                        <td class="slot disallowed-commitment-start" title="Task E cannot START here (occupies 8,9,10 - conflicts slot 10)"><span class="slot-index">8</span><span class="slot-time">10:00</span></td>
                        <td class="slot disallowed-commitment-start" title="Task E cannot START here (occupies 9,10,11 - conflicts slot 10)"><span class="slot-index">9</span><span class="slot-time">10:15</span></td>
                        <td class="slot committed disallowed-commitment-start" title="Commitment here. Task E cannot START here (occupies 10,11,12 - conflicts slot 10)"><span class="slot-index">10</span><span class="slot-time">10:30</span>(C)</td>
                        <td class="slot slot-available" title="Task E can START here (occupies 11,12,13)"><span class="slot-index">11</span><span class="slot-time">10:45</span></td>
                    </tr>
                </tbody>
            </table>


            <!-- Constraint (g): Leisure Calculation & Occupation Link (LaTeX 6.7) -->
            <h3>(g) Leisure Calculation & Occupation Link</h3>
             <p>
                <strong>Intuition:</strong> Leisure time (15 mins per slot) exists only in slots that are NOT committed AND NOT occupied by a scheduled task (from set <code>T</code>). An auxiliary variable <code>Y[s]</code> tracks if a slot <code>s</code> is occupied by a task.
            </p>
            <p>
                <strong>Model:</strong> Links occupation variable <code>Y[s]</code> to task starts <code>X[i, start]</code>. Then calculates leisure <code>L[s]</code>: <code>L[s] = 0</code> if <code>s</code> is committed OR <code>Y[s]=1</code>. Otherwise, <code>L[s] &le; 15</code> (objective function pushes it to 15).
            </p>
            <p><strong>Example:</strong> Slot 20 is free, Slot 21 has a commitment, Slot 22 is occupied by scheduled Task F (from T).</p>
            <ul>
                <li>Slot 20: Is free (not committed, <code>Y[20]=0</code>). Result: <code>L[20]=15</code>.</li>
                <li>Slot 21: Has a commitment. Result: <code>L[21]=0</code>.</li>
                <li>Slot 22: Is occupied by Task F (<code>Y[22]=1</code>). Result: <code>L[22]=0</code>.</li>
            </ul>
             <p><strong>Visualization (Example Slot Statuses after solving):</strong></p>
            <table>
                 <thead><tr><th colspan=4>Example Slots After Scheduling</th></tr></thead>
                 <tbody>
                    <tr>
                        <td class="slot leisure-yes" title="Not committed, not occupied (Y=0) -> Leisure=15"><span class="slot-index">20</span><span class="slot-time">13:00</span>Leisure!</td>
                        <td class="slot committed leisure-no" title="Committed -> Leisure=0"><span class="slot-index">21</span><span class="slot-time">13:15</span>Commit</td>
                        <td class="slot task-occupied leisure-no" title="Task F Occupied (Y=1) -> Leisure=0"><span class="slot-index">22</span><span class="slot-time">13:30</span>Task F</td>
                        <td class="slot leisure-yes" title="Not committed, not occupied (Y=0) -> Leisure=15"><span class="slot-index">23</span><span class="slot-time">13:45</span>Leisure!</td>
                    </tr>
                </tbody>
            </table>


            <!-- Constraint (h): Daily Limits (LaTeX 6.8) -->
            <h3>(h) Daily Limits (Optional)</h3>
            <p>
                <strong>Intuition:</strong> Limit the total number of task-occupied slots (by tasks from <code>T</code>) per day.
            </p>
            <p>
                <strong>Model:</strong> <code>Sum(Y[s] for s in day_d) &le; Limit_daily</code> for each day <code>d</code>.
            </p>
            <p>
                <strong>Example:</strong> Daily Limit = 6 slots for Day 0. Consider scheduling Schedulable Task G (dur=4, start=2) and Schedulable Task H (dur=3, start=7).
            </p>
            <ul>
                <li>Task G occupies slots 2, 3, 4, 5 (4 slots). <code>Y[2]=Y[3]=Y[4]=Y[5]=1</code>.</li>
                <li>Task H occupies slots 7, 8, 9 (3 slots). <code>Y[7]=Y[8]=Y[9]=1</code>.</li>
                <li>Total occupied slots (Y=1) on Day 0 = 4 + 3 = 7 slots.</li>
                <li>This violates the limit (7 > 6). This combination of start times is invalid if the limit is active.</li>
            </ul>
             <p><strong>Visualization (Limit = 6 slots, potential outcome):</strong></p>
            <table>
                <thead><tr><th colspan=10>Day 0 Slots (Violation if Limit=6)</th></tr></thead>
                 <tbody>
                    <tr>
                        <td class="slot slot-available"><span class="slot-index">1</span><span class="slot-time">08:15</span></td>
                        <td class="slot task-occupied" title="Task G"><span class="slot-index">2</span><span class="slot-time">08:30</span>G</td>
                        <td class="slot task-occupied" title="Task G"><span class="slot-index">3</span><span class="slot-time">08:45</span>G</td>
                        <td class="slot task-occupied" title="Task G"><span class="slot-index">4</span><span class="slot-time">09:00</span>G</td>
                        <td class="slot task-occupied" title="Task G"><span class="slot-index">5</span><span class="slot-time">09:15</span>G</td>
                        <td class="slot slot-available"><span class="slot-index">6</span><span class="slot-time">09:30</span></td>
                        <td class="slot task-occupied" title="Task H"><span class="slot-index">7</span><span class="slot-time">09:45</span>H</td>
                        <td class="slot task-occupied" title="Task H"><span class="slot-index">8</span><span class="slot-time">10:00</span>H</td>
                        <td class="slot task-occupied" title="Task H"><span class="slot-index">9</span><span class="slot-time">10:15</span>H</td>
                        <td class="slot slot-available"><span class="slot-index">10</span><span class="slot-time">10:30</span></td>
                    </tr>
                </tbody>
            </table>
            <p style="color: #f87171; font-weight: bold;">
                VIOLATION (if Limit=6): Total occupied slots (Y=1) = 7, exceeds Daily Limit of 6. The solver would need to find a different schedule for G and H (or report infeasibility).
            </p>


            <h2>Objective Function</h2>
            <p>
                The model aims to <strong>maximize</strong> a weighted sum: <code>(alpha * Total_Leisure) - (beta * Total_Stress)</code>.
            </p>
            <ul>
                <li><strong>Total Leisure:</strong> Sum of <code>L[s]</code> (leisure minutes in each slot) across all slots. Higher <code>alpha</code> prioritizes free time.</li>
                <li><strong>Total Stress:</strong> Sum of <code>(Priority * Difficulty)</code> for each scheduled task (task in set T). Higher <code>beta</code> would normally aim to minimize scheduling high-stress tasks. However, since <strong class="highlight">all</strong> tasks passing the pre-filter (set T) <strong class="highlight">must</strong> be scheduled (Constraint a), the total stress calculated this way is constant for a given set of input tasks. The <code>beta</code> term, therefore, acts primarily as a constant offset in the objective and doesn't influence which tasks get scheduled (as they are all mandatory) or significantly impact *when* they are scheduled relative to maximizing leisure. The main driver is finding a feasible schedule for all tasks in T and maximizing leisure among those feasible options.</li>
            </ul>
             <p>
                The optimization finds a schedule that satisfies all constraints (a-h) for all tasks in set T, and among the valid schedules, chooses the one that yields the highest total leisure minutes.
            </p>

        </div>
    </body>
</html>
  `;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-[60] p-4 backdrop-blur-sm">
      <div className="relative bg-gray-800 rounded-xl w-full max-w-4xl shadow-2xl border border-gray-700">
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-gray-400 hover:text-white transition-colors p-1.5 rounded-full hover:bg-gray-700 z-10"
          aria-label="Close explanation"
        >
          <X className="w-6 h-6" />
        </button>
        <div
          className="model-explanation-container overflow-hidden rounded-xl" // Container for innerHTML
          dangerouslySetInnerHTML={{ __html: explanationHtml }}
        />
      </div>
    </div>
  );
};

export default ModelExplanation;
