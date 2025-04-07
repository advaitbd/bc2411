import React, { useState, useEffect, useMemo } from "react"; // Added useMemo
import {
  Calendar,
  Clock,
  Wand2,
  Settings,
  AlertCircle,
  Plus,
  X,
  Sparkles,
  Loader2,
  ArrowLeft, // For prev week
  ArrowRight, // For next week
  Info, // For info icons
  Trash2, // For delete buttons
} from "lucide-react";
import {
  format,
  addDays,
  parseISO,
  startOfWeek,
  addWeeks,
  isSameDay,
  differenceInMinutes,
  isValid,
  startOfDay, // Use startOfDay for comparisons
  endOfDay, // Might be useful
} from "date-fns";

// Assume backend returns naive local ISO strings (no 'Z' or offset)
const API_BASE_URL = "http://localhost:5001/api"; // Backend URL

// --- Constants defined outside component ---
const GRID_START_HOUR = 8;
const GRID_END_HOUR = 22; // Display up to 22:00 (exclusive end for loop)

interface Task {
  id: string; // Keep track of tasks
  name: string;
  priority: number;
  difficulty?: number; // Optional on input, backend defaults
  duration: number; // Duration in minutes
  deadline: string | number; // ISO string (local assumed) or relative days
  preference: "morning" | "afternoon" | "evening" | "any";
}

interface BlockedInterval {
  id: string;
  startTime: string; // Naive local ISO format string (e.g., YYYY-MM-DDTHH:MM:SS)
  endTime: string; // Naive local ISO format string
  activity: string;
}

// Matches the backend response format for scheduled items
interface ScheduledTaskItem {
  id: string; // Task ID from the original task input
  name: string;
  startTime: string; // Naive local ISO format string
  endTime: string; // Naive local ISO format string
  priority: number;
  difficulty: number;
  duration_min: number;
  preference: string;
  start_slot: number; // Added by backend
  end_slot: number; // Added by backend
}

// Keep track of scheduled tasks per day (key: 'yyyy-MM-dd')
type OptimizedSchedule = Record<string, ScheduledTaskItem[]>;

// Helper function to parse potentially naive ISO strings safely
const parseLocalISO = (dateString: string | null | undefined): Date | null => {
  if (!dateString) return null;
  try {
    // parseISO handles strings without timezone info as local time
    const parsed = parseISO(dateString);
    return isValid(parsed) ? parsed : null;
  } catch (e) {
    console.error("Error parsing date string:", dateString, e);
    return null;
  }
};

function App() {
  // --- State Hooks ---
  const [mode, setMode] = useState<"auto" | "manual" | null>(null);
  const [startHour, setStartHour] = useState(8); // User preference start
  const [endHour, setEndHour] = useState(22); // User preference end
  const [optimizedSchedule, setOptimizedSchedule] = useState<OptimizedSchedule>(
    {},
  );
  const [tasks, setTasks] = useState<Task[]>([]);
  const [blockedIntervals, setBlockedIntervals] = useState<BlockedInterval[]>(
    [],
  );
  // Calculate currentWeek based on local time start of the week
  const [currentWeekStart, setCurrentWeekStart] = useState(() =>
    startOfWeek(new Date(), { weekStartsOn: 1 }),
  ); // Monday as start
  const [isOptimized, setIsOptimized] = useState(false);
  const [isLoading, setIsLoading] = useState(false); // Loading state for API calls
  const [error, setError] = useState<string | null>(null); // Error messages
  const [optimizationResult, setOptimizationResult] = useState<{
    totalLeisure: number | null;
    totalStress: number | null;
    status: string | null;
    message: string | null;
    warnings: string[] | null;
  }>({
    totalLeisure: null,
    totalStress: null,
    status: null,
    message: null,
    warnings: null,
  });
  const [selectedEvent, setSelectedEvent] = useState<
    ScheduledTaskItem | BlockedInterval | null
  >(null);
  const [showEventDetailsModal, setShowEventDetailsModal] = useState(false);
  const [showNewTaskForm, setShowNewTaskForm] = useState(false);
  const [showNewBlockForm, setShowNewBlockForm] = useState(false);

  // --- Memoized Values for Forms & Calendar ---
  const defaultTaskData = useMemo(
    () => ({
      name: "",
      priority: 3,
      duration: 60,
      deadline: 3, // Default to 3 days from now
      deadlineType: "days",
      preference: "any" as Task["preference"],
      // Set default date to 3 days from now
      deadlineDate: format(addDays(new Date(), 3), "yyyy-MM-dd"),
    }),
    [],
  ); // Empty dependency array, calculated once

  const defaultBlockData = useMemo(
    () => ({
      activity: "",
      startTime: "09:00",
      endTime: "10:00",
      date: format(new Date(), "yyyy-MM-dd"), // Default to today
    }),
    [],
  ); // Empty dependency array

  const [newTaskData, setNewTaskData] = useState(defaultTaskData);
  const [newBlockData, setNewBlockData] = useState(defaultBlockData);

  // **MOVED HOOKS HERE** - For Calendar Display
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(currentWeekStart, i)),
    [currentWeekStart],
  );

  const hours = useMemo(
    () =>
      Array.from(
        { length: GRID_END_HOUR - GRID_START_HOUR },
        (_, i) => GRID_START_HOUR + i,
      ),
    [], // Now depends only on constants, empty dependency array
  );

  // --- Effects ---
  // Reset optimized state when inputs change
  useEffect(() => {
    setIsOptimized(false);
    setOptimizedSchedule({});
    setOptimizationResult({
      totalLeisure: null,
      totalStress: null,
      status: null,
      message: null,
      warnings: null,
    });
  }, [tasks, blockedIntervals, startHour, endHour]);

  // --- Form Data Reset Functions ---
  const resetNewTaskForm = () => setNewTaskData(defaultTaskData);
  const resetNewBlockForm = () => setNewBlockData(defaultBlockData);

  // --- API Call Functions ---

  const handleAutoGenerate = async () => {
    setIsLoading(true);
    setError(null);
    setOptimizedSchedule({});
    setIsOptimized(false);
    setOptimizationResult({
      totalLeisure: null,
      totalStress: null,
      status: null,
      message: null,
      warnings: null,
    });

    try {
      const response = await fetch(`${API_BASE_URL}/auto-generate`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({})); // Try to get error details
        throw new Error(
          errorData.error || `HTTP error! status: ${response.status}`,
        );
      }
      const data = await response.json();
      console.log("Auto-generated data:", data);

      // Tasks and Blocked Intervals now use naive local ISO strings
      setTasks(data.tasks);
      setBlockedIntervals(data.blockedIntervals);
      setMode("auto"); // Set mode after data is fetched
    } catch (err) {
      console.error("Failed to auto-generate:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to fetch auto-generated data.",
      );
      setTasks([]); // Clear data on error
      setBlockedIntervals([]);
      setMode(null); // Reset mode
    } finally {
      setIsLoading(false);
    }
  };

  const handleOptimize = async () => {
    setIsLoading(true);
    setError(null);
    setOptimizedSchedule({}); // Clear previous schedule
    setIsOptimized(false);
    setOptimizationResult({
      totalLeisure: null,
      totalStress: null,
      status: null,
      message: null,
      warnings: null,
    });

    // --- Prepare data for backend ---
    const tasksToSend = tasks.map((task) => ({
      ...task,
      // Deadline is already string (local ISO) or number (days)
      deadline: task.deadline,
    }));

    const payload = {
      tasks: tasksToSend,
      blockedIntervals: blockedIntervals,
      settings: {
        startHour: startHour, // Send user preference
        endHour: endHour, // Send user preference
      },
    };

    console.log("Sending to /api/optimize:", JSON.stringify(payload, null, 2));

    try {
      const response = await fetch(`${API_BASE_URL}/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      console.log("Optimization response:", result);

      if (!response.ok) {
        // Extract error details if available from backend response
        throw new Error(
          result.error ||
            result.message ||
            `HTTP error! status: ${response.status}`, // Prioritize backend error messages
        );
      }

      if (
        (result.status === "Optimal" || result.status === "Feasible") &&
        result.schedule
      ) {
        const scheduleByDate: OptimizedSchedule = {};
        result.schedule.forEach((item: ScheduledTaskItem) => {
          const startTime = parseLocalISO(item.startTime); // Parse as local
          if (startTime) {
            // Group by the LOCAL date 'yyyy-MM-dd'
            const dateKey = format(startTime, "yyyy-MM-dd");
            if (!scheduleByDate[dateKey]) {
              scheduleByDate[dateKey] = [];
            }
            scheduleByDate[dateKey].push(item);
          } else {
            console.warn(
              "Could not parse start time for scheduled item, skipping:",
              item,
            );
          }
        });

        // Sort items within each day by start time
        Object.keys(scheduleByDate).forEach((dateKey) => {
          scheduleByDate[dateKey].sort((a, b) => {
            const timeA = parseLocalISO(a.startTime)?.getTime() || 0;
            const timeB = parseLocalISO(b.startTime)?.getTime() || 0;
            return timeA - timeB;
          });
        });

        setOptimizedSchedule(scheduleByDate);
        setIsOptimized(true);
        setOptimizationResult({
          totalLeisure: result.total_leisure,
          totalStress: result.total_stress,
          status: result.status,
          message: `Schedule generated successfully (${result.status}).`,
          warnings: result.warnings || null,
        });
      } else {
        // Handle non-optimal/feasible statuses or missing schedule
        // Use the message from the solver result if available
        const failureMessage =
          result.message ||
          `Optimization failed with status: ${result.status || "Unknown"}`;
        setError(failureMessage);
        setOptimizationResult({
          totalLeisure: null,
          totalStress: null,
          status: result.status || "Error",
          message: failureMessage,
          warnings: result.warnings || null,
        });
      }
    } catch (err) {
      console.error("Optimization failed:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Failed to optimize schedule.";
      setError(errorMessage);
      setOptimizationResult({
        totalLeisure: null,
        totalStress: null,
        status: "Error",
        message: errorMessage,
        warnings: null,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleManualMode = () => {
    setMode("manual");
    setTasks([]); // Start with empty lists in manual mode
    setBlockedIntervals([]);
    setOptimizedSchedule({});
    setIsOptimized(false);
    setError(null);
    setOptimizationResult({
      totalLeisure: null,
      totalStress: null,
      status: null,
      message: null,
      warnings: null,
    });
  };

  // --- Form Handlers ---
  const handleTaskFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value, type } = e.target;
    // Special handling for radio buttons
    if (name === "deadlineType") {
      setNewTaskData((prev) => ({ ...prev, deadlineType: value }));
      return;
    }

    const isNumeric =
      ["priority", "duration", "deadline"].includes(name) &&
      type !== "select" &&
      name !== "deadlineDate";

    setNewTaskData((prev) => ({
      ...prev,
      [name]: isNumeric ? parseInt(value) || "" : value,
    }));
  };

  const handleBlockFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;
    setNewBlockData((prev) => ({ ...prev, [name]: value }));
  };

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null); // Clear previous errors

    let deadlineValue: string | number;
    if (newTaskData.deadlineType === "date") {
      // Combine date and a default time (e.g., end of day)
      const datePart = newTaskData.deadlineDate; // Should be YYYY-MM-DD
      if (!datePart || datePart.length !== 10) {
        setError("Invalid deadline date format selected. Use YYYY-MM-DD.");
        return;
      }
      // Set deadline to 23:59:59 on the chosen LOCAL day
      deadlineValue = `${datePart}T23:59:59`;
      const parsedDeadline = parseLocalISO(deadlineValue);
      if (!parsedDeadline || parsedDeadline < startOfDay(new Date())) {
        setError("Deadline date cannot be in the past.");
        return;
      }
    } else {
      // Relative days
      const days = parseInt(newTaskData.deadline.toString());
      if (isNaN(days) || days < 0) {
        setError("Deadline days must be a non-negative number.");
        return;
      }
      deadlineValue = days; // Keep as number for relative days
    }

    if (!newTaskData.name.trim()) {
      setError("Task name cannot be empty.");
      return;
    }
    const duration = parseInt(newTaskData.duration.toString());
    if (isNaN(duration) || duration <= 0) {
      setError("Task duration must be a positive number.");
      return;
    }

    const newTask: Task = {
      id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: newTaskData.name.trim(),
      priority: newTaskData.priority || 1,
      duration: duration,
      deadline: deadlineValue, // Can be local ISO string or number
      preference: newTaskData.preference,
      // Difficulty is optional, backend will default if not sent
    };
    setTasks((prev) => [...prev, newTask]);
    setShowNewTaskForm(false);
    resetNewTaskForm();
    // No need to reset optimized state here, useEffect handles it
  };

  const handleAddBlock = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null); // Clear previous errors

    const startDateTimeStr = `${newBlockData.date}T${newBlockData.startTime}`;
    const endDateTimeStr = `${newBlockData.date}T${newBlockData.endTime}`;

    const startDT = parseLocalISO(startDateTimeStr);
    const endDT = parseLocalISO(endDateTimeStr);

    if (!startDT || !endDT) {
      setError("Invalid date or time format for blocked interval.");
      return;
    }

    if (endDT <= startDT) {
      setError("End time must be after start time for the blocked interval.");
      return;
    }
    if (!newBlockData.activity.trim()) {
      setError("Blocked interval activity name cannot be empty.");
      return;
    }

    const newBlock: BlockedInterval = {
      id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      activity: newBlockData.activity.trim(),
      // Store as local ISO without ms or Z
      startTime: format(startDT, "yyyy-MM-dd'T'HH:mm:ss"),
      endTime: format(endDT, "yyyy-MM-dd'T'HH:mm:ss"),
    };
    setBlockedIntervals((prev) => [...prev, newBlock]);
    setShowNewBlockForm(false);
    resetNewBlockForm();
    // No need to reset optimized state here, useEffect handles it
  };

  // --- Delete Handlers ---
  const handleDeleteTask = (taskId: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId));
  };

  const handleDeleteBlock = (blockId: string) => {
    setBlockedIntervals((prev) => prev.filter((block) => block.id !== blockId));
  };

  // --- Event Click Handler ---
  const handleEventClick = (eventData: ScheduledTaskItem | BlockedInterval) => {
    console.log(`Clicked event:`, eventData);
    setSelectedEvent(eventData);
    setShowEventDetailsModal(true); // Show the modal
  };

  // --- Helper to get deadline display string ---
  const getDeadlineDisplay = (deadline: string | number): string => {
    if (typeof deadline === "number") {
      return `In ${deadline} day(s)`;
    }
    // Assumes deadline is a naive local ISO string
    const dt = parseLocalISO(deadline);
    if (dt) {
      // Format appropriately, maybe relative if close
      const now = new Date();
      const diffDays = differenceInMinutes(dt, now) / (60 * 24);
      if (diffDays < 0) return `Overdue (${format(dt, "MMM d, HH:mm")})`;
      if (diffDays < 1) return `Today ${format(dt, "HH:mm")}`;
      if (diffDays < 2) return `Tomorrow ${format(dt, "HH:mm")}`;
      if (diffDays < 7) return `${format(dt, "EEE, HH:mm")}`;
      return format(dt, "MMM dd, yyyy HH:mm");
    }
    return "Invalid Date";
  };

  // --- Render Functions ---

  const renderTimeWindow = () => (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Settings className="w-5 h-5 text-purple-400" />
        Scheduling Window Preference
      </h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <label
            htmlFor="startHour"
            className="block text-sm text-gray-400 mb-2"
          >
            Start Hour (00:00 - 23:00)
          </label>
          <select
            id="startHour"
            value={startHour}
            onChange={(e) => setStartHour(parseInt(e.target.value))}
            className="bg-gray-700 rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-purple-400 appearance-none cursor-pointer border border-gray-600"
          >
            {Array.from({ length: 24 }, (_, i) => i).map((hour) => (
              <option
                key={hour}
                value={hour}
              >{`${hour.toString().padStart(2, "0")}:00`}</option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label htmlFor="endHour" className="block text-sm text-gray-400 mb-2">
            End Hour (01:00 - 24:00)
          </label>
          <select
            id="endHour"
            value={endHour}
            // Ensure endHour is always after startHour
            onChange={(e) =>
              setEndHour(Math.max(startHour + 1, parseInt(e.target.value)))
            }
            className="bg-gray-700 rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-purple-400 appearance-none cursor-pointer border border-gray-600"
          >
            {/* Allow selecting up to hour 24 (representing end of day 23:59) */}
            {Array.from({ length: 24 }, (_, i) => i + 1).map((hour) => (
              <option key={hour} value={hour} disabled={hour <= startHour}>
                {`${hour === 24 ? "24" : hour.toString().padStart(2, "0")}:00`}{" "}
                {/* Display 24:00 */}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
        <Info size={12} />
        Note: Backend currently uses 8am-10pm (22:00) internally. These settings
        are preferences for future enhancement.
      </p>
    </div>
  );

  const renderModeSelection = () => (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg text-center">
      <h2 className="text-xl font-semibold mb-6">
        How would you like to start?
      </h2>
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <button
          onClick={handleAutoGenerate}
          disabled={isLoading}
          className="flex-1 max-w-xs bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:text-gray-400 disabled:cursor-not-allowed py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors duration-150 text-base font-medium"
        >
          {isLoading && mode === null ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Wand2 className="w-5 h-5" />
          )}
          Auto-generate Sample
        </button>
        <button
          onClick={handleManualMode}
          disabled={isLoading}
          className="flex-1 max-w-xs bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-400 disabled:cursor-not-allowed py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors duration-150 text-base font-medium"
        >
          <Plus className="w-5 h-5" />
          Start Manually
        </button>
      </div>
    </div>
  );

  const renderNewTaskForm = () => (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-lg shadow-2xl border border-gray-700 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6 sticky top-0 bg-gray-800 pt-1 pb-3 -mt-1 z-10">
          <h3 className="text-2xl font-semibold">Add New Task</h3>
          <button
            onClick={() => {
              setShowNewTaskForm(false);
              resetNewTaskForm();
              setError(null);
            }}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-full hover:bg-gray-700"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        <form onSubmit={handleAddTask} className="space-y-4 pb-2">
          {/* Form fields - adjusted styling slightly */}
          <div>
            <label
              htmlFor="taskName"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Task Name
            </label>
            <input
              id="taskName"
              name="name"
              type="text"
              value={newTaskData.name}
              onChange={handleTaskFormChange}
              required
              className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="taskPriority"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Priority (1=Low, 5=High)
              </label>
              <input
                id="taskPriority"
                name="priority"
                type="number"
                min="1"
                max="5"
                value={newTaskData.priority}
                onChange={handleTaskFormChange}
                required
                className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
            <div>
              <label
                htmlFor="taskDuration"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Duration (minutes)
              </label>
              <input
                id="taskDuration"
                name="duration"
                type="number"
                min="15"
                step="15"
                value={newTaskData.duration}
                onChange={handleTaskFormChange}
                required
                className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Deadline
            </label>
            <div className="flex items-center gap-4 bg-gray-700 p-2 rounded border border-gray-600 mb-2">
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <input
                  type="radio"
                  name="deadlineType"
                  value="days"
                  checked={newTaskData.deadlineType === "days"}
                  onChange={handleTaskFormChange}
                  className="form-radio h-4 w-4 text-purple-500 bg-gray-600 border-gray-500 focus:ring-purple-500 focus:ring-offset-gray-800"
                />
                Relative (Days from now)
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <input
                  type="radio"
                  name="deadlineType"
                  value="date"
                  checked={newTaskData.deadlineType === "date"}
                  onChange={handleTaskFormChange}
                  className="form-radio h-4 w-4 text-purple-500 bg-gray-600 border-gray-500 focus:ring-purple-500 focus:ring-offset-gray-800"
                />
                Specific Date
              </label>
            </div>
            <div className="mt-2">
              {newTaskData.deadlineType === "days" ? (
                <input
                  name="deadline"
                  type="number"
                  min="0"
                  value={newTaskData.deadline}
                  onChange={handleTaskFormChange}
                  required
                  className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  placeholder="Days from today"
                />
              ) : (
                <input
                  name="deadlineDate"
                  type="date"
                  value={newTaskData.deadlineDate}
                  min={format(new Date(), "yyyy-MM-dd")} // Prevent past dates
                  onChange={handleTaskFormChange}
                  required
                  className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              )}
            </div>
          </div>

          <div>
            <label
              htmlFor="taskPreference"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Time Preference
            </label>
            <select
              id="taskPreference"
              name="preference"
              value={newTaskData.preference}
              onChange={handleTaskFormChange}
              className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent appearance-none cursor-pointer"
            >
              <option value="any">Any Time</option>
              <option value="morning">Morning (8am - 12pm)</option>
              <option value="afternoon">Afternoon (12pm - 4pm)</option>
              <option value="evening">Evening (4pm - 10pm)</option>
            </select>
          </div>
          {/* Error Display within Modal */}
          {error && (
            <div className="bg-red-900 border border-red-700 text-red-300 px-3 py-2 rounded text-sm mt-2">
              {error}
            </div>
          )}
          <button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700 py-2.5 rounded-lg mt-6 transition-colors font-semibold text-base"
          >
            Add Task
          </button>
        </form>
      </div>
    </div>
  );

  const renderNewBlockForm = () => (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-lg shadow-2xl border border-gray-700 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6 sticky top-0 bg-gray-800 pt-1 pb-3 -mt-1 z-10">
          <h3 className="text-2xl font-semibold">Add Blocked Time</h3>
          <button
            onClick={() => {
              setShowNewBlockForm(false);
              resetNewBlockForm();
              setError(null);
            }}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-full hover:bg-gray-700"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        <form onSubmit={handleAddBlock} className="space-y-4 pb-2">
          {/* Form fields - adjusted styling slightly */}
          <div>
            <label
              htmlFor="blockActivity"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Activity Name
            </label>
            <input
              id="blockActivity"
              name="activity"
              type="text"
              value={newBlockData.activity}
              onChange={handleBlockFormChange}
              required
              className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor="blockDate"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Date
              </label>
              <input
                id="blockDate"
                name="date"
                type="date"
                value={newBlockData.date}
                min={format(new Date(), "yyyy-MM-dd")} // Prevent past dates
                onChange={handleBlockFormChange}
                required
                className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label
                  htmlFor="blockStartTime"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  Start Time
                </label>
                <input
                  id="blockStartTime"
                  name="startTime"
                  type="time"
                  step="900" // 15 minute steps
                  value={newBlockData.startTime}
                  onChange={handleBlockFormChange}
                  required
                  className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
              <div>
                <label
                  htmlFor="blockEndTime"
                  className="block text-sm font-medium text-gray-300 mb-1"
                >
                  End Time
                </label>
                <input
                  id="blockEndTime"
                  name="endTime"
                  type="time"
                  step="900" // 15 minute steps
                  value={newBlockData.endTime}
                  onChange={handleBlockFormChange}
                  required
                  className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>
          {/* Error Display within Modal */}
          {error && (
            <div className="bg-red-900 border border-red-700 text-red-300 px-3 py-2 rounded text-sm mt-2">
              {error}
            </div>
          )}
          <button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700 py-2.5 rounded-lg mt-6 transition-colors font-semibold text-base"
          >
            Add Blocked Time
          </button>
        </form>
      </div>
    </div>
  );

  const renderTasks = () => (
    <div className="bg-gray-800 p-6 rounded-xl shadow-lg">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-purple-400 flex-shrink-0" />
          Tasks ({tasks.length})
        </h2>
        <div className="flex gap-2 flex-wrap">
          {mode === "manual" && (
            <button
              onClick={() => setShowNewTaskForm(true)}
              disabled={isLoading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Task
            </button>
          )}
          <button
            onClick={handleOptimize}
            disabled={isLoading || tasks.length === 0}
            className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:text-gray-400 disabled:cursor-not-allowed text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            Optimize
          </button>
        </div>
      </div>
      {tasks.length === 0 && (
        <p className="text-gray-400 text-center py-4 italic">
          No tasks added yet. Add tasks manually or use auto-generate.
        </p>
      )}
      <div className="overflow-x-auto max-h-96">
        {" "}
        {/* Added max-h and overflow */}
        <table className="w-full min-w-[650px] border-separate border-spacing-y-1">
          <thead className="sticky top-0 bg-gray-800 z-10">
            <tr className="text-left text-sm text-gray-400">
              <th className="pb-2 px-3 font-medium">Name</th>
              <th className="pb-2 px-3 font-medium text-center">Priority</th>
              <th className="pb-2 px-3 font-medium text-center">Duration</th>
              <th className="pb-2 px-3 font-medium">Deadline</th>
              <th className="pb-2 px-3 font-medium">Preference</th>
              <th className="pb-2 px-1 font-medium text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr
                key={task.id}
                className="bg-gray-750 hover:bg-gray-700 transition-colors rounded-lg"
              >
                <td className="py-2.5 px-3 rounded-l-lg">{task.name}</td>
                <td className="py-2.5 px-3 text-center">{task.priority}</td>
                <td className="py-2.5 px-3 text-center">{task.duration} min</td>
                <td className="py-2.5 px-3 text-xs">
                  {getDeadlineDisplay(task.deadline)}
                </td>
                <td className="py-2.5 px-3 capitalize">{task.preference}</td>
                <td className="py-2.5 px-1 text-center rounded-r-lg">
                  <button
                    onClick={() => handleDeleteTask(task.id)}
                    title="Delete Task"
                    className="p-1 text-gray-400 hover:text-red-400 transition-colors rounded-full hover:bg-gray-600"
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderBlockedIntervals = () => (
    <div className="bg-gray-800 p-6 rounded-xl shadow-lg">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Clock className="w-5 h-5 text-purple-400 flex-shrink-0" />
          Blocked Times ({blockedIntervals.length})
        </h2>
        <button
          onClick={() => setShowNewBlockForm(true)}
          disabled={isLoading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Block
        </button>
      </div>
      {blockedIntervals.length === 0 && (
        <p className="text-gray-400 text-center py-4 italic">
          No blocked times added yet. Add classes, appointments, etc.
        </p>
      )}
      <div className="overflow-x-auto max-h-96">
        {" "}
        {/* Added max-h and overflow */}
        <table className="w-full min-w-[550px] border-separate border-spacing-y-1">
          <thead className="sticky top-0 bg-gray-800 z-10">
            <tr className="text-left text-sm text-gray-400">
              <th className="pb-2 px-3 font-medium">Activity</th>
              <th className="pb-2 px-3 font-medium">Start Time</th>
              <th className="pb-2 px-3 font-medium">End Time</th>
              <th className="pb-2 px-1 font-medium text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {blockedIntervals
              .sort((a, b) => {
                const timeA = parseLocalISO(a.startTime)?.getTime() || 0;
                const timeB = parseLocalISO(b.startTime)?.getTime() || 0;
                return timeA - timeB;
              }) // Sort by start time
              .map((interval) => (
                <tr
                  key={interval.id}
                  className="bg-gray-750 hover:bg-gray-700 transition-colors rounded-lg"
                >
                  <td className="py-2.5 px-3 rounded-l-lg">
                    {interval.activity}
                  </td>
                  <td className="py-2.5 px-3 text-sm">
                    {format(
                      parseLocalISO(interval.startTime) || new Date(),
                      "MMM dd, HH:mm",
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-sm">
                    {format(
                      parseLocalISO(interval.endTime) || new Date(),
                      "HH:mm",
                    )}
                  </td>
                  <td className="py-2.5 px-1 text-center rounded-r-lg">
                    <button
                      onClick={() => handleDeleteBlock(interval.id)}
                      title="Delete Blocked Time"
                      className="p-1 text-gray-400 hover:text-red-400 transition-colors rounded-full hover:bg-gray-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderCalendarEvent = (
    startTimeStr: string,
    endTimeStr: string,
    title: string,
    type: "task" | "blocked",
    eventId: string, // Use eventId consistently
    onClick: () => void, // Ensure onClick is always passed
  ) => {
    const start = parseLocalISO(startTimeStr);
    const end = parseLocalISO(endTimeStr);

    // Robust check for valid dates and positive duration
    if (!start || !end || end <= start) {
      console.warn(
        `Invalid date range for event: ${title} (ID: ${eventId}), Start: ${startTimeStr}, End: ${endTimeStr}. Skipping render.`,
      );
      return null;
    }

    // Use the constant calendar grid settings
    const dayViewStartHour = GRID_START_HOUR;
    const dayViewEndHour = GRID_END_HOUR;
    const totalDayViewMinutes = (dayViewEndHour - dayViewStartHour) * 60;

    if (totalDayViewMinutes <= 0) return null; // Avoid division by zero

    // Calculate start and end minutes relative to the view window (8am)
    const startMinutesOffset = Math.max(
      0,
      start.getHours() * 60 + start.getMinutes() - dayViewStartHour * 60,
    );
    const endMinutesOffset = Math.min(
      totalDayViewMinutes,
      end.getHours() * 60 + end.getMinutes() - dayViewStartHour * 60,
    );

    // Calculate duration within the view window
    const durationMinutesInView = endMinutesOffset - startMinutesOffset;

    // Only render if the event overlaps with the view window
    if (durationMinutesInView <= 0) {
      // console.log(`Event ${title} (ID: ${eventId}) is outside the ${dayViewStartHour}-${dayViewEndHour} view window. Skipping render.`);
      return null;
    }

    const topPercent = (startMinutesOffset / totalDayViewMinutes) * 100;
    const heightPercent = (durationMinutesInView / totalDayViewMinutes) * 100;

    let bgColor =
      type === "task"
        ? "bg-purple-600 border-purple-400"
        : "bg-gray-600 border-gray-500";
    let hoverColor =
      type === "task" ? "hover:bg-purple-700" : "hover:bg-gray-700";
    let textColor = type === "task" ? "text-white" : "text-gray-200";

    return (
      <div
        key={`${type}-${eventId}`} // Use stable key
        className={`absolute left-1 right-1 px-1.5 py-0.5 rounded ${bgColor} ${hoverColor} ${textColor} text-xs overflow-hidden shadow border cursor-pointer transition-colors duration-150 pointer-events-auto`}
        style={{
          top: `${topPercent}%`,
          height: `${Math.max(heightPercent, 2)}%`, // Ensure minimum visible height
          minHeight: "16px", // Ensure text is readable
          zIndex: type === "task" ? 10 : 5, // Tasks on top
        }}
        title={`${title}\n${format(start, "HH:mm")} - ${format(end, "HH:mm")}`}
        onClick={(e) => {
          e.stopPropagation(); // Prevent potential parent clicks if nested
          onClick();
        }}
      >
        {/* Only show times if height allows */}
        <div
          className={`font-semibold truncate ${heightPercent < 5 ? "leading-tight" : ""}`}
        >
          {title}
        </div>
        {heightPercent >= 5 && ( // Show time only if enough space
          <div className="text-[10px] opacity-80 truncate leading-tight">
            {format(start, "HH:mm")} - {format(end, "HH:mm")}
          </div>
        )}
      </div>
    );
  };

  const renderCalendar = () => {
    // Uses 'days' and 'hours' from component scope (defined with useMemo)
    return (
      <div className="bg-gray-800 p-4 sm:p-6 rounded-xl shadow-lg overflow-hidden mt-6">
        <div className="flex flex-col sm:flex-row justify-between items-center mb-4 gap-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Calendar className="w-5 h-5 text-purple-400" />
            Optimized Weekly Schedule
          </h2>
          <div className="flex gap-2 items-center bg-gray-700 p-1 rounded-lg">
            <button
              onClick={() => setCurrentWeekStart((w) => addWeeks(w, -1))}
              className="p-2 text-gray-300 hover:bg-gray-600 rounded-md transition-colors"
              title="Previous Week"
            >
              <ArrowLeft size={18} />
            </button>
            <span className="text-sm font-medium px-2 w-32 text-center">
              {format(currentWeekStart, "MMM dd")} -{" "}
              {format(addDays(currentWeekStart, 6), "MMM dd, yyyy")}
            </span>
            <button
              onClick={() => setCurrentWeekStart((w) => addWeeks(w, 1))}
              className="p-2 text-gray-300 hover:bg-gray-600 rounded-md transition-colors"
              title="Next Week"
            >
              <ArrowRight size={18} />
            </button>
          </div>
        </div>

        {/* Optimization Results Summary */}
        {isOptimized && optimizationResult.status && (
          <div
            className={`mb-4 p-3 rounded-lg text-sm border ${
              optimizationResult.status === "Optimal" ||
              optimizationResult.status === "Feasible"
                ? "bg-green-900 border-green-700 text-green-200"
                : "bg-yellow-900 border-yellow-700 text-yellow-200" // Keep yellow for non-optimal feasible? Maybe orange?
            }`}
          >
            <p className="flex items-center gap-1.5">
              <span className="font-semibold">Status:</span>{" "}
              {optimizationResult.status}
              {optimizationResult.totalLeisure !== null && (
                <span className="ml-auto mr-4 text-xs opacity-80">
                  Leisure: {optimizationResult.totalLeisure.toFixed(0)} min
                </span>
              )}
              {optimizationResult.totalStress !== null && (
                <span className="text-xs opacity-80">
                  Stress: {optimizationResult.totalStress.toFixed(1)}
                </span>
              )}
            </p>

            {/* Show solver message only if it's not a simple success message */}
            {optimizationResult.message &&
              !optimizationResult.message.toLowerCase().includes("success") && (
                <p className="mt-1 text-xs opacity-90">
                  <span className="font-semibold">Solver Message:</span>{" "}
                  {optimizationResult.message}
                </p>
              )}
            {optimizationResult.warnings &&
              optimizationResult.warnings.length > 0 && (
                <div className="mt-2 pt-2 border-t border-opacity-30 border-current">
                  <p className="font-semibold text-xs mb-1">Warnings:</p>
                  <ul className="list-disc list-inside text-yellow-300 text-xs space-y-0.5">
                    {optimizationResult.warnings.map((warn, idx) => (
                      <li key={idx}>{warn}</li>
                    ))}
                  </ul>
                </div>
              )}
          </div>
        )}
        {/* Separate Error Display for Optimization Errors */}
        {error &&
          optimizationResult.status &&
          ["Error", "Infeasible", "Not Solved"].includes(
            optimizationResult.status,
          ) && (
            <div className="mb-4 p-3 rounded-lg text-sm bg-red-900 border border-red-700 text-red-200">
              <p>
                <strong className="font-semibold">
                  {optimizationResult.status || "Error"}:
                </strong>{" "}
                {error || optimizationResult.message}
              </p>
            </div>
          )}

        {/* Calendar Grid */}
        <div className="overflow-x-auto relative">
          {/* Use CSS Grid for layout */}
          <div className="grid grid-cols-[45px_repeat(7,minmax(110px,1fr))] min-w-[800px]">
            {" "}
            {/* Time labels + 7 days */}
            {/* Top-left corner */}
            <div className="sticky top-0 z-30 bg-gray-800 h-14 border-b border-r border-gray-700"></div>
            {/* Day Headers */}
            {days.map((day) => (
              <div
                key={`header-${day.toISOString()}`}
                className="sticky top-0 z-30 bg-gray-800 h-14 p-2 text-center border-b border-r border-gray-700 flex flex-col justify-center items-center"
              >
                <div className="font-medium text-sm leading-tight">
                  {format(day, "EEE")} {/* Mon, Tue, etc. */}
                </div>
                <div className="text-xs text-gray-400 leading-tight">
                  {format(day, "d MMM")} {/* 10 Jun, etc. */}
                </div>
              </div>
            ))}
            {/* Time Slots Area */}
            {/* Time Labels Column */}
            <div className="col-start-1 row-start-2 row-span-auto">
              {hours.map((hour) => (
                <div
                  key={`time-${hour}`}
                  className="h-12 pr-2 text-right text-[10px] text-gray-500 border-r border-gray-700 flex items-center justify-end"
                >
                  {`${hour.toString().padStart(2, "0")}:00`}
                </div>
              ))}
            </div>
            {/* Grid Cells & Event Rendering */}
            {days.map((day, dayIndex) => (
              <div
                key={`day-col-${day.toISOString()}`}
                className="col-start-[--col-start] row-start-2 row-span-auto relative border-r border-gray-700 bg-gray-850/30" // Slightly different bg for day columns
                style={{ "--col-start": dayIndex + 2 } as React.CSSProperties}
              >
                {/* Background Hour Lines */}
                {hours.map((_, hourIndex) => (
                  <div
                    key={`line-${dayIndex}-${hourIndex}`}
                    className="h-12 border-b border-gray-700/50"
                  ></div>
                ))}

                {/* Absolutely Positioned Events for this Day */}
                <div className="absolute inset-0 top-0 left-0 right-0 bottom-0 pointer-events-none">
                  {" "}
                  {/* Container for absolute events */}
                  {/* Render Blocked Intervals */}
                  {blockedIntervals
                    .filter((interval) => {
                      const start = parseLocalISO(interval.startTime);
                      return start && isSameDay(start, day); // Compare based on local day
                    })
                    .map((interval) =>
                      renderCalendarEvent(
                        interval.startTime,
                        interval.endTime,
                        interval.activity,
                        "blocked",
                        interval.id,
                        () => handleEventClick(interval),
                      ),
                    )}
                  {/* Render Optimized Tasks */}
                  {isOptimized &&
                    optimizedSchedule[format(day, "yyyy-MM-dd")]?.map(
                      (scheduled) =>
                        renderCalendarEvent(
                          scheduled.startTime,
                          scheduled.endTime,
                          scheduled.name,
                          "task",
                          scheduled.id,
                          () => handleEventClick(scheduled),
                        ),
                    )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }; // End renderCalendar

  // --- Event Details Modal ---
  const renderEventDetailsModal = () => {
    if (!showEventDetailsModal || !selectedEvent) return null;

    const isTask = "priority" in selectedEvent; // Check if it's a ScheduledTaskItem
    const title = isTask ? selectedEvent.name : selectedEvent.activity;
    const startTime = parseLocalISO(selectedEvent.startTime);
    const endTime = parseLocalISO(
      (selectedEvent as ScheduledTaskItem).endTime ||
        (selectedEvent as BlockedInterval).endTime,
    );

    return (
      <div
        className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 backdrop-blur-sm"
        onClick={() => setShowEventDetailsModal(false)}
      >
        <div
          className="bg-gray-800 p-6 rounded-xl w-full max-w-md shadow-2xl border border-gray-700"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xl font-semibold">
              {isTask ? "Task Details" : "Blocked Time Details"}
            </h3>
            <button
              onClick={() => setShowEventDetailsModal(false)}
              className="text-gray-400 hover:text-white p-1 rounded-full hover:bg-gray-700 transition-colors"
            >
              <X size={20} />
            </button>
          </div>
          <div className="space-y-2 text-sm">
            <p>
              <strong className="font-medium text-gray-300 w-24 inline-block">
                {isTask ? "Task:" : "Activity:"}
              </strong>{" "}
              {title}
            </p>
            <p>
              <strong className="font-medium text-gray-300 w-24 inline-block">
                Start Time:
              </strong>{" "}
              {startTime ? format(startTime, "EEE, MMM dd HH:mm") : "N/A"}
            </p>
            <p>
              <strong className="font-medium text-gray-300 w-24 inline-block">
                End Time:
              </strong>{" "}
              {endTime ? format(endTime, "HH:mm") : "N/A"}
            </p>
            {isTask && (
              <>
                <p>
                  <strong className="font-medium text-gray-300 w-24 inline-block">
                    Duration:
                  </strong>{" "}
                  {selectedEvent.duration_min} min
                </p>
                <p>
                  <strong className="font-medium text-gray-300 w-24 inline-block">
                    Priority:
                  </strong>{" "}
                  {selectedEvent.priority}
                </p>
                <p>
                  <strong className="font-medium text-gray-300 w-24 inline-block">
                    Difficulty:
                  </strong>{" "}
                  {selectedEvent.difficulty}
                </p>
                <p>
                  <strong className="font-medium text-gray-300 w-24 inline-block">
                    Preference:
                  </strong>{" "}
                  <span className="capitalize">{selectedEvent.preference}</span>
                </p>
                {/* You could potentially show the original deadline here if needed */}
              </>
            )}
          </div>
          <button
            onClick={() => setShowEventDetailsModal(false)}
            className="mt-6 w-full bg-gray-600 hover:bg-gray-500 py-2 px-4 rounded-lg transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-slate-900 text-gray-100 p-4 md:p-8 font-sans">
      <div className="max-w-7xl mx-auto">
        <header className="flex items-center gap-3 mb-8">
          <Sparkles className="w-8 h-8 text-purple-400 flex-shrink-0" />
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-purple-400 to-pink-500 text-transparent bg-clip-text">
            IntelliSchedule
          </h1>
        </header>

        {/* Global Error Display (for non-modal, non-optimization errors) */}
        {error &&
          !showNewBlockForm &&
          !showNewTaskForm &&
          !(
            optimizationResult.status &&
            ["Error", "Infeasible", "Not Solved"].includes(
              optimizationResult.status,
            )
          ) && (
            <div className="mb-4 p-3 rounded-lg text-sm bg-red-900 border border-red-700 flex justify-between items-center">
              <span className="flex items-center gap-2">
                {" "}
                <AlertCircle size={16} /> {error}
              </span>
              <button
                onClick={() => setError(null)}
                className="text-red-300 hover:text-white p-1 rounded-full hover:bg-red-800 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
          )}

        {!mode && !isLoading && renderModeSelection()}
        {isLoading && !mode && (
          <div className="flex justify-center items-center h-60 bg-gray-800 rounded-xl">
            <Loader2 className="w-12 h-12 text-purple-400 animate-spin" />
          </div>
        )}

        {mode && (
          <>
            {renderTimeWindow()}
            {/* Grid for Tasks and Blocks on larger screens */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {renderTasks()}
              {renderBlockedIntervals()}
            </div>
            {renderCalendar()}
          </>
        )}

        {showNewTaskForm && renderNewTaskForm()}
        {showNewBlockForm && renderNewBlockForm()}
        {renderEventDetailsModal()}
      </div>
      <footer className="text-center text-xs text-gray-500 mt-12 pb-4">
        IntelliSchedule v1.1 - React + Flask + PuLP
      </footer>
    </div>
  );
}

export default App;
