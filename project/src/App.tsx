// bc2411/project/src/App.tsx

import React, { useState, useEffect, useMemo } from "react";
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
  ArrowLeft,
  ArrowRight,
  Info,
  Trash2,
  Edit,
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
  startOfDay,
  parse,
} from "date-fns";

// --- Import the new component ---
import ScheduledTasksList from "./ScheduledTasksList";

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
    // Handle potential lack of seconds
    let adjustedString = dateString;
    if (dateString.length === 16) {
      // YYYY-MM-DDTHH:MM
      adjustedString = dateString + ":00";
    } else if (dateString.length === 10) {
      // YYYY-MM-DD
      adjustedString = dateString + "T00:00:00"; // Assume start of day if only date
    }

    const parsed = parseISO(adjustedString);
    return isValid(parsed) ? parsed : null;
  } catch (e) {
    console.error("Error parsing date string:", dateString, e);
    return null;
  }
};

// --- Types for Form Data ---
interface TaskFormData {
  name: string;
  priority: number;
  duration: number;
  deadline: string | number; // For relative days input
  deadlineType: "days" | "date";
  preference: Task["preference"];
  deadlineDate: string; // For specific date input YYYY-MM-DD
}

interface BlockFormData {
  activity: string;
  startTime: string; // HH:mm
  endTime: string; // HH:mm
  date: string; // YYYY-MM-DD
}

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

  // --- Form States ---
  const [showNewTaskForm, setShowNewTaskForm] = useState(false);
  const [showNewBlockForm, setShowNewBlockForm] = useState(false);
  const [showEditTaskForm, setShowEditTaskForm] = useState(false);
  const [showEditBlockForm, setShowEditBlockForm] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [editingBlock, setEditingBlock] = useState<BlockedInterval | null>(
    null,
  );

  // --- Memoized Default Form Data ---
  const defaultTaskData = useMemo<TaskFormData>(
    () => ({
      name: "",
      priority: 3,
      duration: 60,
      deadline: 3, // Default to 3 days from now (for relative input)
      deadlineType: "days",
      preference: "any" as Task["preference"],
      // Set default date to 3 days from now
      deadlineDate: format(addDays(new Date(), 3), "yyyy-MM-dd"),
    }),
    [],
  );

  const defaultBlockData = useMemo<BlockFormData>(
    () => ({
      activity: "",
      startTime: "09:00",
      endTime: "10:00",
      date: format(new Date(), "yyyy-MM-dd"), // Default to today
    }),
    [],
  );

  const [newTaskData, setNewTaskData] = useState<TaskFormData>(defaultTaskData);
  const [newBlockData, setNewBlockData] =
    useState<BlockFormData>(defaultBlockData);
  // State to hold data for the *currently editing* forms
  const [editTaskData, setEditTaskData] = useState<TaskFormData | null>(null);
  const [editBlockData, setEditBlockData] = useState<BlockFormData | null>(
    null,
  );

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

  // Populate edit form when editingTask changes
  useEffect(() => {
    if (editingTask) {
      let deadlineType: "days" | "date" = "date";
      let deadlineValue: string | number = editingTask.deadline;
      let deadlineDateValue = format(new Date(), "yyyy-MM-dd"); // Default

      if (typeof editingTask.deadline === "number") {
        deadlineType = "days";
        deadlineValue = editingTask.deadline;
        deadlineDateValue = format(
          addDays(new Date(), editingTask.deadline),
          "yyyy-MM-dd",
        );
      } else {
        const parsedDate = parseLocalISO(editingTask.deadline);
        if (parsedDate) {
          deadlineDateValue = format(parsedDate, "yyyy-MM-dd");
          const relativeDays = Math.ceil(
            differenceInMinutes(parsedDate, startOfDay(new Date())) / (60 * 24),
          );
          deadlineValue = Math.max(0, relativeDays);
        } else {
          console.warn(
            "Invalid deadline string found while editing task:",
            editingTask.deadline,
          );
          deadlineType = "days";
          deadlineValue = 3;
          deadlineDateValue = format(addDays(new Date(), 3), "yyyy-MM-dd");
        }
      }

      setEditTaskData({
        name: editingTask.name,
        priority: editingTask.priority,
        duration: editingTask.duration,
        deadline: deadlineValue,
        deadlineType: deadlineType,
        preference: editingTask.preference,
        deadlineDate: deadlineDateValue,
      });
      setShowEditTaskForm(true);
    } else {
      setEditTaskData(null);
      setShowEditTaskForm(false);
    }
  }, [editingTask]);

  // Populate edit form when editingBlock changes
  useEffect(() => {
    if (editingBlock) {
      const start = parseLocalISO(editingBlock.startTime);
      const end = parseLocalISO(editingBlock.endTime);
      setEditBlockData({
        activity: editingBlock.activity,
        date: start
          ? format(start, "yyyy-MM-dd")
          : format(new Date(), "yyyy-MM-dd"),
        startTime: start ? format(start, "HH:mm") : "09:00",
        endTime: end ? format(end, "HH:mm") : "10:00",
      });
      setShowEditBlockForm(true);
    } else {
      setEditBlockData(null);
      setShowEditBlockForm(false);
    }
  }, [editingBlock]);

  // --- Form Data Reset Functions ---
  const resetNewTaskForm = () => setNewTaskData(defaultTaskData);
  const resetNewBlockForm = () => setNewBlockData(defaultBlockData);
  const closeAndResetEditTaskForm = () => {
    setEditingTask(null);
    setError(null);
  };
  const closeAndResetEditBlockForm = () => {
    setEditingBlock(null);
    setError(null);
  };

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
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.error || `HTTP error! status: ${response.status}`,
        );
      }
      const data = await response.json();
      console.log("Auto-generated data:", data);
      setTasks(data.tasks);
      setBlockedIntervals(data.blockedIntervals);
      setMode("auto");
    } catch (err) {
      console.error("Failed to auto-generate:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to fetch auto-generated data.",
      );
      setTasks([]);
      setBlockedIntervals([]);
      setMode(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOptimize = async () => {
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

    const tasksToSend = tasks.map((task) => ({
      ...task,
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
          result.error ||
            result.message ||
            `HTTP error! status: ${response.status}`,
        );
      }

      if (
        (result.status === "Optimal" || result.status === "Feasible") &&
        result.schedule
      ) {
        const scheduleByDate: OptimizedSchedule = {};
        result.schedule.forEach((item: ScheduledTaskItem) => {
          const startTime = parseLocalISO(item.startTime);
          if (startTime) {
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
    setTasks([]);
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
    formType: "new" | "edit",
  ) => {
    const { name, value, type } = e.target;
    const updateFn = formType === "new" ? setNewTaskData : setEditTaskData;

    updateFn((prev: any) => {
      if (!prev) return null;

      if (name === "deadlineType") {
        return { ...prev, deadlineType: value };
      }

      const isNumeric =
        ["priority", "duration", "deadline"].includes(name) &&
        type !== "select" &&
        name !== "deadlineDate";

      if (name === "deadlineType" && value === "days") {
        const parsedDate = parseLocalISO(`${prev.deadlineDate}T00:00:00`);
        let relativeDays = 3;
        if (parsedDate) {
          relativeDays = Math.max(
            0,
            Math.ceil(
              differenceInMinutes(parsedDate, startOfDay(new Date())) /
                (60 * 24),
            ),
          );
        }
        return { ...prev, deadlineType: value, deadline: relativeDays };
      }

      if (name === "deadlineType" && value === "date") {
        let dateValue = prev.deadlineDate;
        if (typeof prev.deadline === "number" && prev.deadline >= 0) {
          dateValue = format(addDays(new Date(), prev.deadline), "yyyy-MM-dd");
        }
        return { ...prev, deadlineType: value, deadlineDate: dateValue };
      }

      return {
        ...prev,
        [name]: isNumeric ? parseInt(value) || "" : value,
      };
    });
  };

  const handleBlockFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    formType: "new" | "edit",
  ) => {
    const { name, value } = e.target;
    const updateFn = formType === "new" ? setNewBlockData : setEditBlockData;
    updateFn((prev: any) => {
      if (!prev) return null;
      return { ...prev, [name]: value };
    });
  };

  // --- Add/Edit Submit Handlers ---

  const processTaskData = (taskData: TaskFormData): Omit<Task, "id"> | null => {
    setError(null);

    let deadlineValue: string | number;
    if (taskData.deadlineType === "date") {
      const datePart = taskData.deadlineDate;
      if (!datePart || datePart.length !== 10) {
        setError("Invalid deadline date format selected. Use YYYY-MM-DD.");
        return null;
      }
      deadlineValue = `${datePart}T23:59:59`;
      const parsedDeadline = parseLocalISO(deadlineValue);
      if (!parsedDeadline || parsedDeadline < startOfDay(new Date())) {
        setError("Deadline date cannot be in the past.");
        return null;
      }
    } else {
      const days = parseInt(taskData.deadline.toString());
      if (isNaN(days) || days < 0) {
        setError("Deadline days must be a non-negative number.");
        return null;
      }
      deadlineValue = days;
    }

    if (!taskData.name.trim()) {
      setError("Task name cannot be empty.");
      return null;
    }
    const duration = parseInt(taskData.duration.toString());
    if (isNaN(duration) || duration <= 0) {
      setError("Task duration must be a positive number.");
      return null;
    }

    return {
      name: taskData.name.trim(),
      priority: taskData.priority || 1,
      duration: duration,
      deadline: deadlineValue,
      preference: taskData.preference,
    };
  };

  const processBlockData = (
    blockData: BlockFormData,
  ): Omit<BlockedInterval, "id"> | null => {
    setError(null);

    const startDT = parse(
      `${blockData.date} ${blockData.startTime}`,
      "yyyy-MM-dd HH:mm",
      new Date(),
    );
    const endDT = parse(
      `${blockData.date} ${blockData.endTime}`,
      "yyyy-MM-dd HH:mm",
      new Date(),
    );

    if (!isValid(startDT) || !isValid(endDT)) {
      setError(
        "Invalid date or time format for blocked interval. Use YYYY-MM-DD and HH:MM.",
      );
      return null;
    }

    if (endDT <= startDT) {
      setError("End time must be after start time for the blocked interval.");
      return null;
    }
    if (!blockData.activity.trim()) {
      setError("Blocked interval activity name cannot be empty.");
      return null;
    }

    return {
      activity: blockData.activity.trim(),
      startTime: format(startDT, "yyyy-MM-dd'T'HH:mm:ss"),
      endTime: format(endDT, "yyyy-MM-dd'T'HH:mm:ss"),
    };
  };

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    const processedData = processTaskData(newTaskData);
    if (processedData) {
      const newTask: Task = {
        id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        ...processedData,
      };
      setTasks((prev) => [...prev, newTask]);
      setShowNewTaskForm(false);
      resetNewTaskForm();
    }
  };

  const handleEditTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTask || !editTaskData) return;

    const processedData = processTaskData(editTaskData);
    if (processedData) {
      setTasks((prevTasks) =>
        prevTasks.map((task) =>
          task.id === editingTask.id ? { ...task, ...processedData } : task,
        ),
      );
      closeAndResetEditTaskForm();
    }
  };

  const handleAddBlock = (e: React.FormEvent) => {
    e.preventDefault();
    const processedData = processBlockData(newBlockData);
    if (processedData) {
      const newBlock: BlockedInterval = {
        id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        ...processedData,
      };
      setBlockedIntervals((prev) => [...prev, newBlock]);
      setShowNewBlockForm(false);
      resetNewBlockForm();
    }
  };

  const handleEditBlock = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingBlock || !editBlockData) return;

    const processedData = processBlockData(editBlockData);
    if (processedData) {
      setBlockedIntervals((prevBlocks) =>
        prevBlocks.map((block) =>
          block.id === editingBlock.id ? { ...block, ...processedData } : block,
        ),
      );
      closeAndResetEditBlockForm();
    }
  };

  // --- Delete Handlers ---
  const handleDeleteTask = (taskId: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId));
  };

  const handleDeleteBlock = (blockId: string) => {
    setBlockedIntervals((prev) => prev.filter((block) => block.id !== blockId));
  };

  // --- Edit Click Handlers ---
  const handleEditTaskClick = (task: Task) => {
    setEditingTask(task);
  };

  const handleEditBlockClick = (block: BlockedInterval) => {
    setEditingBlock(block);
  };

  // --- Event Click Handler ---
  const handleEventClick = (eventData: ScheduledTaskItem | BlockedInterval) => {
    console.log(`Clicked event:`, eventData);
    setSelectedEvent(eventData);
    setShowEventDetailsModal(true);
  };

  // --- Helper to get deadline display string ---
  const getDeadlineDisplay = (deadline: string | number): string => {
    if (typeof deadline === "number") {
      return `In ${deadline} day(s)`;
    }
    const dt = parseLocalISO(deadline);
    if (dt) {
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
            onChange={(e) =>
              setEndHour(Math.max(startHour + 1, parseInt(e.target.value)))
            }
            className="bg-gray-700 rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-purple-400 appearance-none cursor-pointer border border-gray-600"
          >
            {Array.from({ length: 24 }, (_, i) => i + 1).map((hour) => (
              <option key={hour} value={hour} disabled={hour <= startHour}>
                {`${hour === 24 ? "24" : hour.toString().padStart(2, "0")}:00`}
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

  const TaskFormFields: React.FC<{
    formData: TaskFormData;
    onChange: (
      e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    ) => void;
    formIdPrefix: string;
  }> = ({ formData, onChange, formIdPrefix }) => (
    <>
      <div>
        <label
          htmlFor={`${formIdPrefix}TaskName`}
          className="block text-sm font-medium text-gray-300 mb-1"
        >
          Task Name
        </label>
        <input
          id={`${formIdPrefix}TaskName`}
          name="name"
          type="text"
          value={formData.name}
          onChange={onChange}
          required
          className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label
            htmlFor={`${formIdPrefix}TaskPriority`}
            className="block text-sm font-medium text-gray-300 mb-1"
          >
            Priority (1=Low, 5=High)
          </label>
          <input
            id={`${formIdPrefix}TaskPriority`}
            name="priority"
            type="number"
            min="1"
            max="5"
            value={formData.priority}
            onChange={onChange}
            required
            className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <div>
          <label
            htmlFor={`${formIdPrefix}TaskDuration`}
            className="block text-sm font-medium text-gray-300 mb-1"
          >
            Duration (minutes)
          </label>
          <input
            id={`${formIdPrefix}TaskDuration`}
            name="duration"
            type="number"
            min="15"
            step="15"
            value={formData.duration}
            onChange={onChange}
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
              checked={formData.deadlineType === "days"}
              onChange={onChange}
              className="form-radio h-4 w-4 text-purple-500 bg-gray-600 border-gray-500 focus:ring-purple-500 focus:ring-offset-gray-800"
            />
            Relative (Days from now)
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="radio"
              name="deadlineType"
              value="date"
              checked={formData.deadlineType === "date"}
              onChange={onChange}
              className="form-radio h-4 w-4 text-purple-500 bg-gray-600 border-gray-500 focus:ring-purple-500 focus:ring-offset-gray-800"
            />
            Specific Date
          </label>
        </div>
        <div className="mt-2">
          {formData.deadlineType === "days" ? (
            <input
              name="deadline"
              type="number"
              min="0"
              value={formData.deadline}
              onChange={onChange}
              required
              className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="Days from today"
            />
          ) : (
            <input
              name="deadlineDate"
              type="date"
              value={formData.deadlineDate}
              min={format(new Date(), "yyyy-MM-dd")}
              onChange={onChange}
              required
              className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          )}
        </div>
      </div>

      <div>
        <label
          htmlFor={`${formIdPrefix}TaskPreference`}
          className="block text-sm font-medium text-gray-300 mb-1"
        >
          Time Preference
        </label>
        <select
          id={`${formIdPrefix}TaskPreference`}
          name="preference"
          value={formData.preference}
          onChange={onChange}
          className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent appearance-none cursor-pointer"
        >
          <option value="any">Any Time</option>
          <option value="morning">Morning (8am - 12pm)</option>
          <option value="afternoon">Afternoon (12pm - 4pm)</option>
          <option value="evening">Evening (4pm - 10pm)</option>
        </select>
      </div>
    </>
  );

  const BlockFormFields: React.FC<{
    formData: BlockFormData;
    onChange: (
      e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    ) => void;
    formIdPrefix: string;
  }> = ({ formData, onChange, formIdPrefix }) => (
    <>
      <div>
        <label
          htmlFor={`${formIdPrefix}BlockActivity`}
          className="block text-sm font-medium text-gray-300 mb-1"
        >
          Activity Name
        </label>
        <input
          id={`${formIdPrefix}BlockActivity`}
          name="activity"
          type="text"
          value={formData.activity}
          onChange={onChange}
          required
          className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label
            htmlFor={`${formIdPrefix}BlockDate`}
            className="block text-sm font-medium text-gray-300 mb-1"
          >
            Date
          </label>
          <input
            id={`${formIdPrefix}BlockDate`}
            name="date"
            type="date"
            value={formData.date}
            onChange={onChange}
            required
            className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label
              htmlFor={`${formIdPrefix}BlockStartTime`}
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Start Time
            </label>
            <input
              id={`${formIdPrefix}BlockStartTime`}
              name="startTime"
              type="time"
              step="900"
              value={formData.startTime}
              onChange={onChange}
              required
              className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
          <div>
            <label
              htmlFor={`${formIdPrefix}BlockEndTime`}
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              End Time
            </label>
            <input
              id={`${formIdPrefix}BlockEndTime`}
              name="endTime"
              type="time"
              step="900"
              value={formData.endTime}
              onChange={onChange}
              required
              className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>
    </>
  );

  const renderModalWrapper = (
    title: string,
    onClose: () => void,
    onSubmit: (e: React.FormEvent) => void,
    submitText: string,
    children: React.ReactNode,
    currentError: string | null,
  ) => (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-lg shadow-2xl border border-gray-700 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6 sticky top-0 bg-gray-800 pt-1 pb-3 -mt-1 z-10">
          <h3 className="text-2xl font-semibold">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-full hover:bg-gray-700"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        <form onSubmit={onSubmit} className="space-y-4 pb-2">
          {children}
          {currentError && (
            <div className="bg-red-900 border border-red-700 text-red-300 px-3 py-2 rounded text-sm mt-2">
              {currentError}
            </div>
          )}
          <button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700 py-2.5 rounded-lg mt-6 transition-colors font-semibold text-base"
          >
            {submitText}
          </button>
        </form>
      </div>
    </div>
  );

  const renderNewTaskForm = () =>
    renderModalWrapper(
      "Add New Task",
      () => {
        setShowNewTaskForm(false);
        resetNewTaskForm();
        setError(null);
      },
      handleAddTask,
      "Add Task",
      <TaskFormFields
        formData={newTaskData}
        onChange={(e) => handleTaskFormChange(e, "new")}
        formIdPrefix="new"
      />,
      error,
    );

  const renderEditTaskForm = () =>
    editTaskData &&
    renderModalWrapper(
      "Edit Task",
      closeAndResetEditTaskForm,
      handleEditTask,
      "Save Changes",
      <TaskFormFields
        formData={editTaskData}
        onChange={(e) => handleTaskFormChange(e, "edit")}
        formIdPrefix="edit"
      />,
      error,
    );

  const renderNewBlockForm = () =>
    renderModalWrapper(
      "Add Blocked Time",
      () => {
        setShowNewBlockForm(false);
        resetNewBlockForm();
        setError(null);
      },
      handleAddBlock,
      "Add Blocked Time",
      <BlockFormFields
        formData={newBlockData}
        onChange={(e) => handleBlockFormChange(e, "new")}
        formIdPrefix="new"
      />,
      error,
    );

  const renderEditBlockForm = () =>
    editBlockData &&
    renderModalWrapper(
      "Edit Blocked Time",
      closeAndResetEditBlockForm,
      handleEditBlock,
      "Save Changes",
      <BlockFormFields
        formData={editBlockData}
        onChange={(e) => handleBlockFormChange(e, "edit")}
        formIdPrefix="edit"
      />,
      error,
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
        <table className="w-full min-w-[700px] border-separate border-spacing-y-1">
          <thead className="sticky top-0 bg-gray-800 z-10">
            <tr className="text-left text-sm text-gray-400">
              <th className="pb-2 px-3 font-medium">Name</th>
              <th className="pb-2 px-3 font-medium text-center">Prio</th>
              <th className="pb-2 px-3 font-medium text-center">Dur</th>
              <th className="pb-2 px-3 font-medium">Deadline</th>
              <th className="pb-2 px-3 font-medium">Pref</th>
              <th className="pb-2 px-1 font-medium text-center w-20">
                Actions
              </th>
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
                <td className="py-2.5 px-3 text-center">
                  {task.duration}
                  <span className="text-xs text-gray-400">m</span>
                </td>
                <td className="py-2.5 px-3 text-xs">
                  {getDeadlineDisplay(task.deadline)}
                </td>
                <td className="py-2.5 px-3 capitalize text-xs">
                  {task.preference}
                </td>
                <td className="py-2.5 px-1 text-center rounded-r-lg">
                  <div className="flex justify-center items-center gap-1.5">
                    <button
                      onClick={() => handleEditTaskClick(task)}
                      title="Edit Task"
                      className="p-1 text-gray-400 hover:text-blue-400 transition-colors rounded-full hover:bg-gray-600"
                    >
                      <Edit size={16} />
                    </button>
                    <button
                      onClick={() => handleDeleteTask(task.id)}
                      title="Delete Task"
                      className="p-1 text-gray-400 hover:text-red-400 transition-colors rounded-full hover:bg-gray-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
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
        <table className="w-full min-w-[600px] border-separate border-spacing-y-1">
          <thead className="sticky top-0 bg-gray-800 z-10">
            <tr className="text-left text-sm text-gray-400">
              <th className="pb-2 px-3 font-medium">Activity</th>
              <th className="pb-2 px-3 font-medium">Start Time</th>
              <th className="pb-2 px-3 font-medium">End Time</th>
              <th className="pb-2 px-1 font-medium text-center w-20">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {blockedIntervals
              .sort((a, b) => {
                const timeA = parseLocalISO(a.startTime)?.getTime() || 0;
                const timeB = parseLocalISO(b.startTime)?.getTime() || 0;
                return timeA - timeB;
              })
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
                    <div className="flex justify-center items-center gap-1.5">
                      <button
                        onClick={() => handleEditBlockClick(interval)}
                        title="Edit Blocked Time"
                        className="p-1 text-gray-400 hover:text-blue-400 transition-colors rounded-full hover:bg-gray-600"
                      >
                        <Edit size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteBlock(interval.id)}
                        title="Delete Blocked Time"
                        className="p-1 text-gray-400 hover:text-red-400 transition-colors rounded-full hover:bg-gray-600"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
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
    eventId: string,
    onClick: () => void,
  ) => {
    const start = parseLocalISO(startTimeStr);
    const end = parseLocalISO(endTimeStr);

    if (!start || !end || end <= start) {
      console.warn(
        `Invalid date range for event: ${title} (ID: ${eventId}), Start: ${startTimeStr}, End: ${endTimeStr}. Skipping render.`,
      );
      return null;
    }

    const dayViewStartHour = GRID_START_HOUR;
    const dayViewEndHour = GRID_END_HOUR;
    const totalDayViewMinutes = (dayViewEndHour - dayViewStartHour) * 60;

    if (totalDayViewMinutes <= 0) return null;

    const startMinutesOffset = Math.max(
      0,
      start.getHours() * 60 + start.getMinutes() - dayViewStartHour * 60,
    );
    const endMinutesOffset = Math.min(
      totalDayViewMinutes,
      end.getHours() * 60 + end.getMinutes() - dayViewStartHour * 60,
    );

    const durationMinutesInView = endMinutesOffset - startMinutesOffset;

    if (durationMinutesInView <= 0) {
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
        key={`${type}-${eventId}`}
        className={`absolute left-1 right-1 px-1.5 py-0.5 rounded ${bgColor} ${hoverColor} ${textColor} text-xs overflow-hidden shadow border cursor-pointer transition-colors duration-150 pointer-events-auto`}
        style={{
          top: `${topPercent}%`,
          height: `${Math.max(heightPercent, 2)}%`,
          minHeight: "16px",
          zIndex: type === "task" ? 10 : 5,
        }}
        title={`${title}\n${format(start, "HH:mm")} - ${format(end, "HH:mm")}`}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <div
          className={`font-semibold truncate ${heightPercent < 5 ? "leading-tight" : ""}`}
        >
          {title}
        </div>
        {heightPercent >= 5 && (
          <div className="text-[10px] opacity-80 truncate leading-tight">
            {format(start, "HH:mm")} - {format(end, "HH:mm")}
          </div>
        )}
      </div>
    );
  };

  const renderCalendar = () => {
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

        {isOptimized && optimizationResult.status && (
          <div
            className={`mb-4 p-3 rounded-lg text-sm border ${
              optimizationResult.status === "Optimal" ||
              optimizationResult.status === "Feasible"
                ? "bg-green-900 border-green-700 text-green-200"
                : "bg-yellow-900 border-yellow-700 text-yellow-200"
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

        <div className="overflow-x-auto relative">
          <div className="grid grid-cols-[45px_repeat(7,minmax(110px,1fr))] min-w-[800px]">
            <div className="sticky top-0 z-30 bg-gray-800 h-14 border-b border-r border-gray-700"></div>
            {days.map((day) => (
              <div
                key={`header-${day.toISOString()}`}
                className="sticky top-0 z-30 bg-gray-800 h-14 p-2 text-center border-b border-r border-gray-700 flex flex-col justify-center items-center"
              >
                <div className="font-medium text-sm leading-tight">
                  {format(day, "EEE")}
                </div>
                <div className="text-xs text-gray-400 leading-tight">
                  {format(day, "d MMM")}
                </div>
              </div>
            ))}
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
            {days.map((day, dayIndex) => (
              <div
                key={`day-col-${day.toISOString()}`}
                className="col-start-[--col-start] row-start-2 row-span-auto relative border-r border-gray-700 bg-gray-850/30"
                style={{ "--col-start": dayIndex + 2 } as React.CSSProperties}
              >
                {hours.map((_, hourIndex) => (
                  <div
                    key={`line-${dayIndex}-${hourIndex}`}
                    className="h-12 border-b border-gray-700/50"
                  ></div>
                ))}
                <div className="absolute inset-0 top-0 left-0 right-0 bottom-0 pointer-events-none">
                  {blockedIntervals
                    .filter((interval) => {
                      const start = parseLocalISO(interval.startTime);
                      return start && isSameDay(start, day);
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

    const isTask = "priority" in selectedEvent;
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

        {error &&
          !showNewBlockForm &&
          !showNewTaskForm &&
          !showEditBlockForm &&
          !showEditTaskForm &&
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
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {renderTasks()}
              {renderBlockedIntervals()}
            </div>
            {renderCalendar()}

            {/* --- Add the Scheduled Tasks List Here --- */}
            {isOptimized && Object.keys(optimizedSchedule).length > 0 && (
              <ScheduledTasksList schedule={optimizedSchedule} />
            )}
            {/* ----------------------------------------- */}
          </>
        )}

        {showNewTaskForm && renderNewTaskForm()}
        {showNewBlockForm && renderNewBlockForm()}
        {showEditTaskForm && renderEditTaskForm()}
        {showEditBlockForm && renderEditBlockForm()}
        {renderEventDetailsModal()}
      </div>
      <footer className="text-center text-xs text-gray-500 mt-12 pb-4">
        IntelliSchedule v1.2 - React + Flask + PuLP
      </footer>
    </div>
  );
}

export default App;
