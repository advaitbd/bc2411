import React, { useState, useEffect } from "react";
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
} from "date-fns";

const API_BASE_URL = "http://localhost:5001/api"; // Backend URL

interface Task {
  id: string; // Keep track of tasks
  name: string;
  priority: number;
  // difficulty: number; // Backend defaults if not sent
  duration: number; // Duration in minutes
  deadline: string | number; // Can be ISO string or relative days for input/display
  preference: "morning" | "afternoon" | "evening" | "any"; // Added 'any'
}

interface BlockedInterval {
  id: string;
  startTime: string; // ISO format string (e.g., YYYY-MM-DDTHH:MM:SSZ)
  endTime: string; // ISO format string
  activity: string;
}

// Matches the backend response format for scheduled items
interface ScheduledTaskItem {
  id: string; // Task ID from the original task input
  name: string;
  startTime: string; // ISO format string
  endTime: string; // ISO format string
  priority: number;
  difficulty: number;
  duration_min: number;
  preference: string;
  start_slot: number; // Added by backend
  end_slot: number; // Added by backend
}

// Keep track of scheduled tasks per day (key: 'yyyy-MM-dd')
type OptimizedSchedule = Record<string, ScheduledTaskItem[]>;

function App() {
  const [mode, setMode] = useState<"auto" | "manual" | null>(null);
  const [startHour, setStartHour] = useState(8);
  const [endHour, setEndHour] = useState(22);
  const [optimizedSchedule, setOptimizedSchedule] = useState<OptimizedSchedule>(
    {},
  );
  const [tasks, setTasks] = useState<Task[]>([]);
  const [blockedIntervals, setBlockedIntervals] = useState<BlockedInterval[]>(
    [],
  );
  const [currentWeek, setCurrentWeek] = useState(startOfWeek(new Date())); // Start with current week
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
  // const [showEventDetailsModal, setShowEventDetailsModal] = useState(false); // For future modal

  // -- Modals State --
  const [showNewTaskForm, setShowNewTaskForm] = useState(false);
  const [showNewBlockForm, setShowNewBlockForm] = useState(false);

  // -- Form Data State --
  const [newTaskData, setNewTaskData] = useState({
    name: "",
    priority: 3,
    duration: 60,
    deadline: 3,
    deadlineType: "days",
    preference: "any" as Task["preference"],
    deadlineDate: format(addDays(new Date(), 3), "yyyy-MM-dd"),
  });
  const [newBlockData, setNewBlockData] = useState({
    activity: "",
    startTime: "09:00",
    endTime: "10:00",
    date: format(new Date(), "yyyy-MM-dd"),
  });

  // Function to reset form data
  const resetNewTaskForm = () =>
    setNewTaskData({
      name: "",
      priority: 3,
      duration: 60,
      deadline: 3,
      deadlineType: "days",
      preference: "any",
      deadlineDate: format(addDays(new Date(), 3), "yyyy-MM-dd"),
    });
  const resetNewBlockForm = () =>
    setNewBlockData({
      activity: "",
      startTime: "09:00",
      endTime: "10:00",
      date: format(new Date(), "yyyy-MM-dd"),
    });

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
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log("Auto-generated data:", data);

      // Ensure deadlines are handled appropriately (backend sends ISO strings)
      const formattedTasks = data.tasks.map((task: any) => ({
        ...task,
        deadline: task.deadline, // Keep as ISO string from backend
      }));

      setTasks(formattedTasks);
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
      duration: task.duration, // Send duration in minutes
      deadline: task.deadline,
    }));

    const payload = {
      tasks: tasksToSend,
      blockedIntervals: blockedIntervals,
      settings: {
        startHour: startHour,
        endHour: endHour,
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
        throw new Error(
          result.error || `HTTP error! status: ${response.status}`,
        );
      }

      if (result.status === "Optimal" || result.status === "Feasible") {
        const scheduleByDate: OptimizedSchedule = {};
        result.schedule.forEach((item: ScheduledTaskItem) => {
          try {
            const dateKey = format(parseISO(item.startTime), "yyyy-MM-dd");
            if (!scheduleByDate[dateKey]) {
              scheduleByDate[dateKey] = [];
            }
            scheduleByDate[dateKey].push(item);
          } catch (parseError) {
            console.error(
              "Error parsing date for scheduled item:",
              item,
              parseError,
            );
          }
        });

        Object.keys(scheduleByDate).forEach((dateKey) => {
          scheduleByDate[dateKey].sort(
            (a, b) =>
              parseISO(a.startTime).getTime() - parseISO(b.startTime).getTime(),
          );
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
        setError(
          result.message || `Optimization failed with status: ${result.status}`,
        );
        setOptimizationResult({
          totalLeisure: null,
          totalStress: null,
          status: result.status,
          message: result.message,
          warnings: result.warnings || null,
        });
      }
    } catch (err) {
      console.error("Optimization failed:", err);
      setError(
        err instanceof Error ? err.message : "Failed to optimize schedule.",
      );
      setOptimizationResult({
        totalLeisure: null,
        totalStress: null,
        status: "Error",
        message:
          err instanceof Error
            ? err.message
            : "Client-side error during optimization.",
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
    const isNumeric = ["priority", "duration", "deadline"].includes(name);

    if (name === "deadlineType") {
      setNewTaskData((prev) => ({ ...prev, deadlineType: value }));
      return;
    }

    setNewTaskData((prev) => ({
      ...prev,
      [name]: isNumeric && type !== "select" ? parseInt(value) || "" : value,
    }));
  };

  const handleBlockFormChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setNewBlockData((prev) => ({ ...prev, [name]: value }));
  };

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    const deadlineValue =
      newTaskData.deadlineType === "date"
        ? parseISO(`${newTaskData.deadlineDate}T23:59:59Z`).toISOString()
        : parseInt(newTaskData.deadline.toString());

    if (
      newTaskData.deadlineType === "date" &&
      !isValid(parseISO(deadlineValue as string))
    ) {
      setError("Invalid deadline date selected.");
      return;
    }
    if (
      newTaskData.deadlineType === "days" &&
      (isNaN(deadlineValue as number) || (deadlineValue as number) < 0)
    ) {
      setError("Deadline days must be a non-negative number.");
      return;
    }
    if (!newTaskData.name.trim()) {
      setError("Task name cannot be empty.");
      return;
    }
    if (newTaskData.duration <= 0) {
      setError("Task duration must be positive.");
      return;
    }

    const newTask: Task = {
      id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: newTaskData.name,
      priority: newTaskData.priority || 1,
      duration: newTaskData.duration || 15,
      deadline: deadlineValue,
      preference: newTaskData.preference,
    };
    setTasks((prev) => [...prev, newTask]);
    setShowNewTaskForm(false);
    resetNewTaskForm();
    setIsOptimized(false);
    setOptimizedSchedule({});
    setError(null);
  };

  const handleAddBlock = (e: React.FormEvent) => {
    e.preventDefault();
    const startDateTimeStr = `${newBlockData.date}T${newBlockData.startTime}:00`;
    const endDateTimeStr = `${newBlockData.date}T${newBlockData.endTime}:00`;

    const startDT = parseISO(startDateTimeStr);
    const endDT = parseISO(endDateTimeStr);

    if (!isValid(startDT) || !isValid(endDT)) {
      setError("Invalid date or time format for blocked interval.");
      return;
    }

    if (endDT <= startDT) {
      setError("End time must be after start time.");
      return;
    }
    if (!newBlockData.activity.trim()) {
      setError("Blocked interval activity name cannot be empty.");
      return;
    }

    const newBlock: BlockedInterval = {
      id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      activity: newBlockData.activity,
      startTime: startDT.toISOString(),
      endTime: endDT.toISOString(),
    };
    setBlockedIntervals((prev) => [...prev, newBlock]);
    setShowNewBlockForm(false);
    resetNewBlockForm();
    setIsOptimized(false);
    setOptimizedSchedule({});
    setError(null);
  };

  // --- Event Click Handler ---
  const handleEventClick = (
    type: "task" | "block",
    eventData: ScheduledTaskItem | BlockedInterval,
  ) => {
    console.log(`Clicked ${type}:`, eventData);
    setSelectedEvent(eventData);
    // setShowEventDetailsModal(true); // Uncomment this to enable a modal

    // For now, just alert details:
    try {
      const startTimeParsed = parseISO(eventData.startTime);
      const endTimeParsed = parseISO(
        (eventData as ScheduledTaskItem).endTime ||
          (eventData as BlockedInterval).endTime,
      ); // Handle both types

      if (!isValid(startTimeParsed) || !isValid(endTimeParsed)) {
        throw new Error("Invalid date in event data");
      }

      const details =
        type === "task"
          ? `Task: ${(eventData as ScheduledTaskItem).name}\nTime: ${format(startTimeParsed, "HH:mm")} - ${format(endTimeParsed, "HH:mm")}\nPriority: ${(eventData as ScheduledTaskItem).priority}`
          : `Blocked: ${(eventData as BlockedInterval).activity}\nTime: ${format(startTimeParsed, "HH:mm")} - ${format(endTimeParsed, "HH:mm")}`;
      alert(details); // Replace with modal later
    } catch (error) {
      console.error("Error formatting event details:", error);
      alert(
        `Could not display details for ${type === "task" ? (eventData as ScheduledTaskItem).name : (eventData as BlockedInterval).activity}. Invalid date format encountered.`,
      );
    }
  };

  // --- Helper to get deadline display string ---
  const getDeadlineDisplay = (deadline: string | number): string => {
    if (typeof deadline === "number") {
      return `In ${deadline} day(s)`;
    }
    try {
      const dt = parseISO(deadline);
      if (isValid(dt)) {
        return format(dt, "MMM dd, yyyy");
      }
    } catch (e) {
      /* ignore parse error */
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
            Start Hour (08:00 - 21:00)
          </label>
          <select
            id="startHour"
            value={startHour}
            onChange={(e) => setStartHour(parseInt(e.target.value))}
            className="bg-gray-700 rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-purple-400 appearance-none"
          >
            {Array.from({ length: 14 }, (_, i) => 8 + i).map((hour) => (
              <option
                key={hour}
                value={hour}
              >{`${hour.toString().padStart(2, "0")}:00`}</option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label htmlFor="endHour" className="block text-sm text-gray-400 mb-2">
            End Hour (09:00 - 22:00)
          </label>
          <select
            id="endHour"
            value={endHour}
            onChange={(e) =>
              setEndHour(Math.max(startHour + 1, parseInt(e.target.value)))
            }
            className="bg-gray-700 rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-purple-400 appearance-none"
          >
            {Array.from({ length: 14 }, (_, i) => 9 + i).map((hour) => (
              <option
                key={hour}
                value={hour}
                disabled={hour <= startHour}
              >{`${hour.toString().padStart(2, "0")}:00`}</option>
            ))}
          </select>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-2">
        Note: This currently acts as a preference for the solver, not a hard
        constraint.
      </p>
    </div>
  );

  const renderModeSelection = () => (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg">
      <h2 className="text-xl font-semibold mb-4">Get Started</h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <button
          onClick={handleAutoGenerate}
          disabled={isLoading}
          className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:cursor-not-allowed py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors duration-150"
        >
          {isLoading && mode === null ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Wand2 className="w-5 h-5" />
          )}
          Auto-generate Sample Schedule
        </button>
        <button
          onClick={handleManualMode}
          disabled={isLoading}
          className="flex-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:cursor-not-allowed py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors duration-150"
        >
          <Plus className="w-5 h-5" />
          Start Manually
        </button>
      </div>
    </div>
  );

  const renderNewTaskForm = () => (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-lg shadow-2xl">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-2xl font-semibold">Add New Task</h3>
          <button
            onClick={() => {
              setShowNewTaskForm(false);
              resetNewTaskForm();
              setError(null);
            }}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        <form onSubmit={handleAddTask} className="space-y-4">
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
              className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
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
                className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
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
                className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Deadline
            </label>
            <div className="flex items-center gap-4 bg-gray-700 p-2 rounded">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="deadlineType"
                  value="days"
                  checked={newTaskData.deadlineType === "days"}
                  onChange={handleTaskFormChange}
                  className="form-radio text-purple-500 bg-gray-600 border-gray-500 focus:ring-purple-500"
                />
                Relative (Days from now)
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="deadlineType"
                  value="date"
                  checked={newTaskData.deadlineType === "date"}
                  onChange={handleTaskFormChange}
                  className="form-radio text-purple-500 bg-gray-600 border-gray-500 focus:ring-purple-500"
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
                  className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="Days from today"
                />
              ) : (
                <input
                  name="deadlineDate"
                  type="date"
                  value={newTaskData.deadlineDate}
                  onChange={handleTaskFormChange}
                  required
                  className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
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
              className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 appearance-none"
            >
              <option value="any">Any Time</option>
              <option value="morning">Morning (8am - 12pm)</option>
              <option value="afternoon">Afternoon (12pm - 4pm)</option>
              <option value="evening">Evening (4pm - 10pm)</option>
            </select>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700 py-2.5 rounded-lg mt-4 transition-colors font-semibold"
          >
            Add Task
          </button>
        </form>
      </div>
    </div>
  );

  const renderNewBlockForm = () => (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-lg shadow-2xl">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-2xl font-semibold">Add Blocked Time</h3>
          <button
            onClick={() => {
              setShowNewBlockForm(false);
              resetNewBlockForm();
              setError(null);
            }}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        <form onSubmit={handleAddBlock} className="space-y-4">
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
              className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
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
                onChange={handleBlockFormChange}
                required
                className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
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
                  value={newBlockData.startTime}
                  onChange={handleBlockFormChange}
                  required
                  className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
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
                  value={newBlockData.endTime}
                  onChange={handleBlockFormChange}
                  required
                  className="w-full bg-gray-700 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700 py-2.5 rounded-lg mt-4 transition-colors font-semibold"
          >
            Add Blocked Time
          </button>
        </form>
      </div>
    </div>
  );

  const renderTasks = () => (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-purple-400 flex-shrink-0" />
          Current Tasks ({tasks.length})
        </h2>
        <div className="flex gap-2 flex-wrap">
          {mode === "manual" && (
            <button
              onClick={() => setShowNewTaskForm(true)}
              disabled={isLoading}
              className="bg-blue-500 hover:bg-blue-600 disabled:bg-blue-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Task
            </button>
          )}
          <button
            onClick={handleOptimize}
            disabled={isLoading || tasks.length === 0}
            className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:cursor-not-allowed text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            Optimize Schedule
          </button>
        </div>
      </div>
      {tasks.length === 0 && (
        <p className="text-gray-400 text-center py-4">No tasks added yet.</p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px]">
          <thead>
            <tr className="text-left text-sm text-gray-400 border-b border-gray-700">
              <th className="pb-3 px-2">Name</th>
              <th className="pb-3 px-2">Priority</th>
              <th className="pb-3 px-2">Duration</th>
              <th className="pb-3 px-2">Deadline</th>
              <th className="pb-3 px-2">Preference</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr
                key={task.id}
                className="border-b border-gray-700 hover:bg-gray-750"
              >
                <td className="py-3 px-2">{task.name}</td>
                <td className="py-3 px-2 text-center">{task.priority}</td>
                <td className="py-3 px-2">{task.duration} min</td>
                <td className="py-3 px-2">
                  {getDeadlineDisplay(task.deadline)}
                </td>
                <td className="py-3 px-2 capitalize">{task.preference}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderBlockedIntervals = () => (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Clock className="w-5 h-5 text-purple-400 flex-shrink-0" />
          Blocked Time Intervals ({blockedIntervals.length})
        </h2>
        <button
          onClick={() => setShowNewBlockForm(true)}
          disabled={isLoading}
          className="bg-blue-500 hover:bg-blue-600 disabled:bg-blue-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Block
        </button>
      </div>
      {blockedIntervals.length === 0 && (
        <p className="text-gray-400 text-center py-4">
          No blocked times added yet.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[500px]">
          <thead>
            <tr className="text-left text-sm text-gray-400 border-b border-gray-700">
              <th className="pb-3 px-2">Activity</th>
              <th className="pb-3 px-2">Start Time</th>
              <th className="pb-3 px-2">End Time</th>
            </tr>
          </thead>
          <tbody>
            {blockedIntervals
              .sort((a, b) => {
                try {
                  // Add try-catch for robust parsing during sort
                  return (
                    parseISO(a.startTime).getTime() -
                    parseISO(b.startTime).getTime()
                  );
                } catch {
                  return 0; // Keep original order if parsing fails
                }
              }) // Sort by start time
              .map((interval) => (
                <tr
                  key={interval.id}
                  className="border-b border-gray-700 hover:bg-gray-750"
                >
                  <td className="py-3 px-2">{interval.activity}</td>
                  <td className="py-3 px-2">
                    {isValid(parseISO(interval.startTime))
                      ? format(parseISO(interval.startTime), "MMM dd, HH:mm")
                      : "Invalid Date"}
                  </td>
                  <td className="py-3 px-2">
                    {isValid(parseISO(interval.endTime))
                      ? format(parseISO(interval.endTime), "HH:mm")
                      : ""}
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
    eventId?: string, // Renamed from taskId for clarity
    onClick?: () => void, // Added onClick handler prop
  ) => {
    try {
      const start = parseISO(startTimeStr);
      const end = parseISO(endTimeStr);

      if (!isValid(start) || !isValid(end) || end <= start) {
        console.warn(
          "Invalid date range for event:",
          title,
          startTimeStr,
          endTimeStr,
        );
        return null;
      }

      const dayStartHour = 8;
      const dayEndHour = 22;
      const totalDayMinutes = (dayEndHour - dayStartHour) * 60;

      const startMinutesOffset = Math.max(
        0,
        start.getHours() * 60 + start.getMinutes() - dayStartHour * 60,
      );
      const endMinutesOffset = Math.min(
        totalDayMinutes,
        end.getHours() * 60 + end.getMinutes() - dayStartHour * 60,
      );

      const durationMinutes = endMinutesOffset - startMinutesOffset;

      if (durationMinutes <= 0) return null;

      const topPercent = (startMinutesOffset / totalDayMinutes) * 100;
      const heightPercent = (durationMinutes / totalDayMinutes) * 100;

      let bgColor =
        type === "task"
          ? "bg-purple-600 border-purple-400"
          : "bg-gray-600 border-gray-500";
      let hoverColor =
        type === "task" ? "hover:bg-purple-700" : "hover:bg-gray-700";

      return (
        <div
          key={`${type}-${eventId || title}-${startTimeStr}`} // Use eventId
          className={`absolute left-1 right-1 px-1.5 py-0.5 rounded-md ${bgColor} ${hoverColor} text-xs overflow-hidden shadow-md border ${type === "task" ? "text-white" : "text-gray-200"} transition-colors cursor-pointer pointer-events-auto`} // Ensure pointer-events-auto is set
          style={{
            top: `${topPercent}%`,
            height: `${heightPercent}%`,
            minHeight: "10px",
            zIndex: type === "task" ? 10 : 5,
          }}
          title={`${title}\n${format(start, "HH:mm")} - ${format(end, "HH:mm")}`}
          onClick={onClick} // Attach the handler
        >
          <div className="font-semibold truncate leading-tight">{title}</div>
          <div className="text-xs opacity-80 truncate leading-tight">
            {format(start, "HH:mm")} - {format(end, "HH:mm")}
          </div>
        </div>
      );
    } catch (e) {
      console.error("Error rendering calendar event:", title, e);
      return null;
    }
  };

  const renderCalendar = () => {
    const days = Array.from({ length: 7 }, (_, i) => addDays(currentWeek, i));
    const gridStartHour = 8;
    const gridEndHour = 22;
    const hours = Array.from(
      { length: gridEndHour - gridStartHour },
      (_, i) => gridStartHour + i,
    );

    return (
      <div className="bg-gray-800 p-6 rounded-xl shadow-lg overflow-hidden">
        <div className="flex flex-col sm:flex-row justify-between items-center mb-4 gap-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Calendar className="w-5 h-5 text-purple-400" />
            Weekly Schedule
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => setCurrentWeek((w) => addWeeks(w, -1))}
              className="bg-gray-700 hover:bg-gray-600 text-sm py-2 px-4 rounded-lg transition-colors"
            >
              Previous Week
            </button>
            <button
              onClick={() => setCurrentWeek((w) => addWeeks(w, 1))}
              className="bg-gray-700 hover:bg-gray-600 text-sm py-2 px-4 rounded-lg transition-colors"
            >
              Next Week
            </button>
          </div>
        </div>
        {/* Optimization Results Summary */}
        {isOptimized && optimizationResult.status && (
          <div
            className={`mb-4 p-3 rounded-lg text-sm ${optimizationResult.status === "Optimal" || optimizationResult.status === "Feasible" ? "bg-green-900 border border-green-700" : "bg-yellow-900 border border-yellow-700"}`} // Use yellow for non-optimal feasible?
          >
            <p>
              <strong>Status:</strong> {optimizationResult.status}
            </p>
            {optimizationResult.totalLeisure !== null && (
              <p>
                <strong>Total Leisure:</strong>{" "}
                {optimizationResult.totalLeisure.toFixed(1)} minutes
              </p>
            )}
            {optimizationResult.totalStress !== null && (
              <p>
                <strong>Total Stress Score:</strong>{" "}
                {optimizationResult.totalStress.toFixed(1)}
              </p>
            )}
            {optimizationResult.message &&
              optimizationResult.status !== "Optimal" &&
              optimizationResult.status !== "Feasible" && (
                <p className="mt-1">
                  <strong>Message:</strong> {optimizationResult.message}
                </p>
              )}
            {optimizationResult.warnings &&
              optimizationResult.warnings.length > 0 && (
                <div className="mt-2 pt-2 border-t border-opacity-50 border-gray-600">
                  <p>
                    <strong>Warnings:</strong>
                  </p>
                  <ul className="list-disc list-inside text-yellow-400 text-xs">
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
          ["Error", "Infeasible"].includes(optimizationResult.status) && (
            <div className="mb-4 p-3 rounded-lg text-sm bg-red-900 border border-red-700">
              <p>
                <strong>{optimizationResult.status}:</strong>{" "}
                {error || optimizationResult.message}
              </p>
            </div>
          )}
        <div className="overflow-x-auto">
          <div className="min-w-[1000px] relative">
            {/* Grid Background Structure */}
            <div className="grid grid-cols-[60px_repeat(7,1fr)]">
              {/* Header Row Placeholder */}
              <div className="sticky top-0 z-20 bg-gray-800 h-16"></div>
              {days.map((day) => (
                <div
                  key={day.toISOString()}
                  className="sticky top-0 z-20 bg-gray-800 h-16 p-2 text-center border-b border-l border-gray-700"
                >
                  <div className="font-medium text-sm">
                    {format(day, "EEE")}
                  </div>
                  <div className="text-xs text-gray-400">
                    {format(day, "MMM dd")}
                  </div>
                </div>
              ))}

              {/* Time Column Labels & Grid Cells */}
              {hours.map((hour, hourIndex) => (
                <React.Fragment key={hour}>
                  {/* Time Label */}
                  <div
                    className="row-start-[--row-start] h-16 pr-2 text-right text-xs text-gray-500 border-r border-gray-700 flex items-start justify-end pt-1"
                    style={
                      { "--row-start": hourIndex + 2 } as React.CSSProperties
                    }
                  >
                    {`${hour.toString().padStart(2, "0")}:00`}
                  </div>
                  {/* Grid Cells for the hour */}
                  {days.map((day) => (
                    <div
                      key={`${day.toISOString()}-${hour}`}
                      className="row-start-[--row-start] h-16 border-b border-l border-gray-700"
                      style={
                        { "--row-start": hourIndex + 2 } as React.CSSProperties
                      }
                    >
                      {/* Empty cell, events are overlaid */}
                    </div>
                  ))}
                </React.Fragment>
              ))}
            </div>
            {/* Events Overlay - Positioned absolutely */}
            <div className="absolute top-16 left-[60px] right-0 bottom-0 grid grid-cols-7 pointer-events-none">
              {" "}
              {/* Adjusted left offset */}
              {days.map((day) => (
                <div
                  key={`events-${day.toISOString()}`}
                  className="relative h-full pointer-events-auto border-l border-gray-700" // Ensure relative and pointer events enabled, add border for visual separation
                >
                  {/* Render Blocked Intervals for this day */}
                  {blockedIntervals
                    .filter((interval) => {
                      try {
                        return isSameDay(parseISO(interval.startTime), day);
                      } catch {
                        return false;
                      }
                    })
                    .map((interval) =>
                      renderCalendarEvent(
                        interval.startTime,
                        interval.endTime,
                        interval.activity,
                        "blocked",
                        interval.id,
                        () => handleEventClick("block", interval), // Add onClick handler
                      ),
                    )}
                  {/* Render Optimized Tasks for this day */}
                  {isOptimized &&
                    optimizedSchedule[format(day, "yyyy-MM-dd")]?.map(
                      (scheduled) =>
                        renderCalendarEvent(
                          scheduled.startTime,
                          scheduled.endTime,
                          scheduled.name, // <-- Corrected access
                          "task",
                          scheduled.id, // <-- Corrected access
                          () => handleEventClick("task", scheduled), // Add onClick handler
                        ),
                    )}
                </div>
              ))}
            </div>
          </div>{" "}
          {/* End min-w wrapper */}
        </div>{" "}
        {/* End overflow-x-auto */}
      </div>
    );
  }; // End renderCalendar

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-800 text-gray-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center gap-4 mb-8">
          <Sparkles className="w-8 h-8 text-purple-400" />
          <h1 className="text-3xl font-bold tracking-tight">
            Intelligent Task Scheduler
          </h1>
        </div>

        {/* Global Error Display (Non-Optimization Errors) */}
        {error &&
          !["Error", "Infeasible"].includes(
            optimizationResult.status || "",
          ) && (
            <div className="mb-4 p-3 rounded-lg text-sm bg-red-900 border border-red-700 flex justify-between items-center">
              <span>
                <strong>Error:</strong> {error}
              </span>
              <button
                onClick={() => setError(null)}
                className="text-red-300 hover:text-white"
              >
                <X size={18} />
              </button>
            </div>
          )}

        {!mode && !isLoading && renderModeSelection()}
        {isLoading && !mode && (
          <div className="flex justify-center items-center h-40">
            <Loader2 className="w-10 h-10 text-purple-400 animate-spin" />
          </div>
        )}

        {mode && (
          <>
            {renderTimeWindow()}
            {renderTasks()}
            {renderBlockedIntervals()}
            {renderCalendar()}
          </>
        )}

        {showNewTaskForm && renderNewTaskForm()}
        {showNewBlockForm && renderNewBlockForm()}

        {/* Basic Event Detail Modal Placeholder (Optional)
         {showEventDetailsModal && selectedEvent && (
             <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
                 <div className="bg-gray-800 p-6 rounded-xl w-full max-w-md shadow-2xl">
                     <h3 className="text-xl mb-4">Event Details</h3>
                     <pre className="text-xs bg-gray-700 p-2 rounded overflow-auto">{JSON.stringify(selectedEvent, null, 2)}</pre>
                     <button onClick={() => setShowEventDetailsModal(false)} className="mt-4 bg-gray-600 hover:bg-gray-500 py-2 px-4 rounded w-full">Close</button>
                 </div>
             </div>
         )}
         */}
      </div>
      <footer className="text-center text-xs text-gray-500 mt-12 pb-4">
        Schedule Optimizer v1.0 - Powered by React, Flask, and PuLP
      </footer>
    </div>
  );
}

export default App;
