# Intelligent Task Scheduler

This project is a web application designed to help users schedule their tasks intelligently over a week. It takes user-defined tasks (with priorities, durations, deadlines, and time preferences) and blocked time intervals (like classes or appointments) and uses an optimization model to generate a feasible or optimal schedule that attempts to balance completing tasks with maximizing leisure time and minimizing stress (based on task priority and difficulty).

The application features a React frontend with a weekly calendar view and a Flask backend powered by the Gurobi optimization library.

![image](https://github.com/user-attachments/assets/11925fb1-e539-4753-ad13-a75b89e660c6)

## Key Features

*   **Task Management:** Add tasks with details like name, priority (1-5), duration (minutes), deadline (relative days or specific date), and time preference (morning, afternoon, evening, any).
*   **Blocked Time:** Define fixed commitments or unavailable time slots (e.g., classes, meetings, meals).
*   **NTU Schedule Import:** Upload your NTU class schedule to automatically populate blocked intervals.
*   **Auto-Generation:** Option to populate the scheduler with sample student-like tasks and blocked times for demonstration.
*   **Optimization Engine:** Uses mathematical optimization (via Gurobi) to find a schedule based on the defined objective function and constraints.
*   **Multiple Optimization Models:** Three variations of the model (standard, no Y variable, and deadline penalty) for different scheduling approaches.
*   **Weekly Calendar View:** Displays the optimized schedule visually across a 7-day week (Monday-Sunday, 8 AM - 10 PM).
*   **Customizable Time Window:** Adjust the start and end hours to focus on your active hours.
*   **Optimization Parameters:** Control the weighting between leisure time (α) and task stress (β).
*   **Interactive Analysis:** View optimization status (Optimal, Feasible, Infeasible) and metrics (total leisure, total stress).
*   **Model Explanation:** Detailed documentation and visualization of the optimization model.
*   **Dark Theme UI:** Built with Tailwind CSS for a clean, modern dark interface.

## Technology Stack

*   **Frontend:**
    *   React (with TypeScript)
    *   Vite (Build Tool)
    *   Tailwind CSS (Styling)
    *   Lucide React (Icons)
    *   `date-fns` (Date/Time Utilities)
*   **Backend:**
    *   Flask (Web Framework)
    *   Gurobi (Mathematical Optimization Solver)
    *   PuLP (Alternative Linear Programming Modeler)
    *   Python 3.x
    *   Pandas, NumPy (for data manipulation and analysis)
    *   Matplotlib, Seaborn (for visualization)

## Optimization Models

The project includes multiple optimization model variants:

1. **Standard Model (`allocation_logic_no_y.py`)**: The core model balancing leisure time and stress.
2. **Deadline Penalty Model (`allocation_logic_deadline_penalty.py`)**: Incorporates penalties for scheduling tasks close to their deadlines.

Each model is thoroughly documented in `model.md` and has corresponding LaTeX files and HTML explanations in the `model` directory.

## Analysis Tools

The project includes several analysis tools:

- **Sensitivity Analysis (`sensitivity_analysis.py`)**: Evaluates how changes in input parameters affect the optimization results.
- **Schedule Variation Analysis (`schedule_variation_visualisation.py`)**: Visualizes different schedule scenarios.
- **Run Analysis (`run_analysis.py`)**: Automates the analysis process.

## Getting Started

### Prerequisites

*   Python 3.8+
*   Node.js 18+ and npm (or yarn)
*   A Python virtual environment tool (like `venv`)
*   Gurobi Optimizer (academic license available)

### Backend Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-folder>/bc2411
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    # On Windows:
    # .venv\Scripts\activate
    # On macOS/Linux:
    source .venv/bin/activate
    ```
3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up Gurobi:**
    - Obtain a Gurobi license (academic licenses are free)
    - Install Gurobi following their installation instructions
    - Activate your license

5.  **Run the Flask development server:**
    ```bash
    python app.py
    ```
    The backend API should now be running, typically on `http://localhost:5001`.

### Frontend Setup

1.  **Navigate to the frontend project directory:**
    ```bash
    cd project
    ```
2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```
3.  **Run the Vite development server:**
    ```bash
    npm run dev
    ```
    The frontend should now be running, typically on `http://localhost:5173` (or another port if 5173 is busy), and will connect to the backend API.

## How to Run

1.  Start the **Backend** server (`python app.py` in the `bc2411` directory).
2.  Start the **Frontend** server (`npm run dev` in the `bc2411/project` directory).
3.  Open your web browser and navigate to the frontend URL (usually `http://localhost:5173`).

## API Endpoints

*   `GET /api/auto-generate`: Generates a sample set of tasks and blocked intervals. Returns JSON data for the frontend.
*   `POST /api/optimize`: Accepts a JSON payload containing `tasks`, `blockedIntervals`, and `settings`. Runs the optimization model and returns the results, including the `status` and the generated `schedule`.

## Project Structure

```
bc2411/
├── app.py                             # Flask Backend Server & API Endpoints
├── allocation_logic.py                # Standard Gurobi Optimization Logic
├── allocation_logic_no_y.py           # Optimized Model without Y variable
├── allocation_logic_deadline_penalty.py # Model with deadline penalty
├── model.md                           # Technical documentation of the optimization model
├── model/                             # LaTeX and HTML explanations of each model
│   ├── model.pdf                      # PDF documentation for the standard model
│   ├── model_no_y.pdf                 # PDF documentation for the no Y model
│   └── model_deadline_penalty.pdf     # PDF documentation for the deadline penalty model
├── sensitivity_analysis.py            # Analyzes model sensitivity to parameter changes
├── schedule_variation_visualisation.py # Visualizes different schedule scenarios
├── analysis/                          # Analysis results and visualizations
├── requirements.txt                   # Python Dependencies
├── .venv/                             # Python Virtual Environment
└── project/                           # Frontend React Project
    ├── .bolt/                         # Bolt AI configuration
    ├── public/                        # Static assets for Vite
    ├── src/                           # React Source Code
    │   ├── components/                # Reusable React components
    │   │   ├── Calendar.tsx           # Calendar view component
    │   │   ├── TaskForm.tsx           # Task input form
    │   │   ├── BlockForm.tsx          # Blocked interval input form
    │   │   ├── ModelExplanation.tsx   # Model explanation component
    │   │   └── ...                    # Other components
    │   ├── utils/                     # Utility functions
    │   │   ├── dateUtils.ts           # Date/time helpers
    │   │   ├── formUtils.ts           # Form processing utilities
    │   │   ├── scheduleParser.ts      # NTU schedule parser
    │   │   └── ...                    # Other utilities
    │   ├── App.tsx                    # Main Application Component
    │   ├── index.css                  # Tailwind CSS setup
    │   ├── main.tsx                   # React Root Render
    │   └── types.ts                   # TypeScript type definitions
    ├── index.html                     # Entry HTML file for Vite
    ├── package.json                   # Frontend dependencies and scripts
    ├── tailwind.config.js             # Tailwind configuration
    ├── postcss.config.js              # PostCSS configuration
    ├── vite.config.ts                 # Vite configuration
    ├── tsconfig.json                  # TypeScript main config
    └── tsconfig.node.json             # TypeScript config for Vite/Node env
```

## Optimization Model Overview

The core scheduling logic resides in the allocation logic files. It uses the Gurobi solver to formulate and solve a Mathematical Programming problem:

*   **Time Representation:** The week (7 days, customizable hours) is divided into discrete 15-minute time slots.
*   **Decision Variables:**
    *   `X[i, s]`: Binary variable, 1 if task `i` starts at slot `s`, 0 otherwise.
    *   `L[s]`: Continuous variable representing leisure minutes (0-15) in slot `s`.
*   **Objective Function:** Maximize a weighted sum: `Maximize alpha * Total_Leisure - beta * Total_Stress`.
    *   `Total_Leisure`: Sum of `L[s]` over all slots.
    *   `Total_Stress`: Sum of `Priority[i] * Difficulty[i]` for all *scheduled* tasks `i`.
    *   `alpha` and `beta` are user-configurable weights to balance leisure vs. stress minimization.
*   **Constraints:**
    1.  **Task Assignment:** Each task must be assigned exactly one starting slot.
    2.  **Deadlines:** Each task must finish *before or at* its deadline slot.
    3.  **No Overlap (Tasks):** A time slot can be occupied by at most one task.
    4.  **No Overlap (Commitments):** Tasks cannot be scheduled during predefined blocked/committed time slots.
    5.  **Preferences:** Tasks can only start in slots that match their time preference (morning, afternoon, evening, any).
    6.  **Leisure Calculation:** Ensure that `L[s]` is non-negative and that it is calculated based on the availability of slots for leisure.
    7.  **Daily Limit (Optional):** Can limit the total number of task-occupied slots per day.
