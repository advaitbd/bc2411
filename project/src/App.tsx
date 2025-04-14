// Import utilities
import { processTaskData } from "./utils/formUtils";
import Modal from "./components/Modal";
import EventDetailsModal from "./components/EventDetailsModal";
import CalendarComponent from "./components/Calendar";
import ImportScheduleModal from "./components/ImportScheduleModal";
import ScheduledTasksList from "./ScheduledTasksList";
import TimeWindow from "./components/TimeWindow";
import TasksList from "./components/TasksList";
import BlockedIntervalsList from "./components/BlockedIntervalsList";
// import ModeSelection from "./components/ModeSelection"; // <-- REMOVE
import ModelExplanation from "./components/ModelExplanation"; // <-- IMPORT NEW COMPONENT
import { useState, useMemo, useEffect, useCallback } from "react";
// Import types and utilities
import {
  Task,
  BlockedInterval,
  ScheduledTaskItem,
  FilteredTaskInfo,
  OptimizedSchedule,
  TaskFormData,
  BlockFormData,
  OptimizationResult,
} from "./types";
import { parseLocalISO } from "./utils/dateUtils";
import { API_BASE_URL } from "./utils/constants";
import { parseNtuSchedule } from "./utils/scheduleParser";
import {
  format,
  addDays,
  startOfWeek,
  differenceInMinutes,
  startOfDay,
} from "date-fns";
import { processBlockData } from "./components/BlockForm";
import BlockFormFields from "./components/BlockForm";
import { Sparkles, AlertCircle, X, HelpCircle } from "lucide-react"; // <-- Add HelpCircle
import TaskFormFields from "./components/TaskForm";

// Import custom CSS
import "./utils/scrollbar.css";

function App() {
  // --- State Hooks ---
  // const [mode, setMode] = useState<"auto" | "manual" | null>(null); // <-- REMOVE
  const [startHour, setStartHour] = useState(8); // User preference start
  const [endHour, setEndHour] = useState(22); // User preference end
  const [alpha, setAlpha] = useState(1.0); // Default alpha for leisure weight
  const [beta, setBeta] = useState(0.1); // Default beta for stress weight
  const [dailyLimit, setDailyLimit] = useState<number | null>(null); // Default: no daily limit
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
  // Add state for import modal
  const [showImportModal, setShowImportModal] = useState(false);
  const [importErrors, setImportErrors] = useState<string[]>([]);
  const [optimizationResult, setOptimizationResult] =
    useState<OptimizationResult>({
      totalLeisure: null,
      totalStress: null,
      status: null,
      message: null,
      warnings: null,
      filteredTasksInfo: null, // Initialize as null
    });
  const [modelType, setModelType] = useState<"deadline_penalty" | "no_y">(
    "deadline_penalty",
  );

  const [selectedEvent, setSelectedEvent] = useState<
    ScheduledTaskItem | BlockedInterval | null
  >(null);
  const [showEventDetailsModal, setShowEventDetailsModal] = useState(false);
  const [showExplanation, setShowExplanation] = useState(false); // <-- State for explanation modal

  // --- Form States ---
  const [showNewTaskForm, setShowNewTaskForm] = useState(false);
  const [showNewBlockForm, setShowNewBlockForm] = useState(false);
  const [showEditTaskForm, setShowEditTaskForm] = useState(false);
  const [showEditBlockForm, setShowEditBlockForm] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [editingBlock, setEditingBlock] = useState<BlockedInterval | null>(
    null,
  );

  // State to store the required duration hint for the edit form
  const [editTaskMinDurationHint, setEditTaskMinDurationHint] = useState<
    number | null
  >(null);

  // --- Memoized Default Form Data ---
  const defaultTaskData = useMemo<TaskFormData>(
    () => ({
      name: "",
      priority: 3,
      difficulty: 1, // Default difficulty (easy)
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

  // --- Effects ---
  // Reset optimized state when inputs change
  // Update the useEffect to reset optimized state when settings change
  useEffect(() => {
    setIsOptimized(false);
    setOptimizedSchedule({});
    setOptimizationResult((prev) => ({ ...prev, filteredTasksInfo: null })); // Clear filtered info too
    setError(null); // Also clear general errors
  }, [tasks, blockedIntervals, startHour, endHour, modelType, alpha, beta, dailyLimit]); // Include all optimization settings in deps

  // Helper to get task by ID
  const getTaskById = useCallback(
    (taskId: string): Task | undefined => {
      return tasks.find((task) => task.id === taskId);
    },
    [tasks],
  );

  // Populate edit form when editingTask changes
  useEffect(() => {
    if (editingTask) {
      let deadlineType: "days" | "date" = "date";
      let deadlineValue: string | number = editingTask.deadline;
      let deadlineDateValue = format(new Date(), "yyyy-MM-dd");

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
            "Invalid deadline string for edit:",
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
        difficulty: editingTask.difficulty, // Assume difficulty is always present now
        duration: editingTask.duration,
        deadline: deadlineValue,
        deadlineType: deadlineType,
        preference: editingTask.preference,
        deadlineDate: deadlineDateValue,
      });
      setShowEditTaskForm(true);
      // Clear hint initially, will be set if editing a filtered task
      setEditTaskMinDurationHint(null);
    } else {
      setEditTaskData(null);
      setShowEditTaskForm(false);
      setEditTaskMinDurationHint(null);
    }
  }, [editingTask]);

  // Populate edit block form when editingBlock changes
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
    setError(null); // Clear form-specific error on close
    setEditTaskMinDurationHint(null);
  };
  const closeAndResetEditBlockForm = () => {
    setEditingBlock(null);
    setError(null); // Clear form-specific error on close
  };

  // --- API Call Functions ---

  // Generic function to fetch auto-generated data
  const fetchAutoGeneratedData = async () => {
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
      filteredTasksInfo: null,
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
      console.log("Auto-generated data fetched:", data);
      return data; // Return the fetched data
    } catch (err) {
      console.error("Failed to auto-generate:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to fetch auto-generated data.",
      );
      // Don't reset tasks/blocks here, let the calling function decide
      return null; // Indicate failure
    } finally {
      setIsLoading(false);
    }
  };

  // Specific handler for generating tasks
  const handleGenerateTasks = async () => {
    const data = await fetchAutoGeneratedData();
    if (data && data.tasks) {
      const tasksWithDifficulty = data.tasks.map(
        (t: Omit<Task, "difficulty"> & { difficulty?: number }) => ({
          ...t,
          difficulty: t.difficulty ?? 1,
        }),
      );
      setTasks(tasksWithDifficulty); // Replace existing tasks
      setError(null); // Clear error on success
    }
  };

  // Specific handler for generating blocked intervals
  const handleGenerateBlocks = async () => {
    const data = await fetchAutoGeneratedData();
    if (data && data.blockedIntervals) {
      setBlockedIntervals(data.blockedIntervals); // Replace existing blocks
      setError(null); // Clear error on success
    }
  };

  // Update the optimize function to include modelType (around line 270)
  const handleOptimize = async () => {
    setIsLoading(true);
    setError(null); // Clear general error
    setOptimizedSchedule({});
    setIsOptimized(false);
    // Reset optimization results, keeping null for filtered tasks initially
    setOptimizationResult({
      totalLeisure: null,
      totalStress: null,
      status: null,
      message: null,
      warnings: null,
      filteredTasksInfo: null,
    });

    const tasksToSend = tasks.map((task) => ({
      id: task.id,
      name: task.name,
      priority: task.priority,
      difficulty: task.difficulty, // Send difficulty
      duration: task.duration, // Send original duration in minutes
      deadline: task.deadline,
      preference: task.preference,
    }));

    const payload = {
      tasks: tasksToSend,
      blockedIntervals: blockedIntervals,
      settings: {
        startHour: startHour,
        endHour: endHour,
        modelType: modelType,
        alpha: alpha, // Add alpha parameter for leisure weight
        beta: beta,   // Add beta parameter for stress weight
        dailyLimit: dailyLimit, // Add daily limit parameter
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
        // Keep filtered tasks info even on error if backend provides it
        setOptimizationResult((prev) => ({
          ...prev,
          status: result.status || "Error",
          message:
            result.error ||
            result.message ||
            `HTTP error! status: ${response.status}`,
          warnings: result.warnings || null,
          filteredTasksInfo: result.filtered_tasks_info || null, // Store filtered info
        }));
        setError(
          result.error ||
            result.message ||
            `HTTP error! status: ${response.status}`,
        );
        setIsLoading(false);
        return; // Stop processing further
      }

      // --- Process successful response ---
      const scheduleByDate: OptimizedSchedule = {};
      if (result.schedule && Array.isArray(result.schedule)) {
        result.schedule.forEach((item: ScheduledTaskItem) => {
          const startTime = parseLocalISO(item.startTime);
          if (startTime) {
            // Add deadline from the original task
            const originalTask = tasks.find(task => task.id === item.id);
            if (originalTask) {
              item.deadline = originalTask.deadline;
            }
            
            const dateKey = format(startTime, "yyyy-MM-dd");
            if (!scheduleByDate[dateKey]) {
              scheduleByDate[dateKey] = [];
            }
            scheduleByDate[dateKey].push(item);
          } else {
            console.warn("Could not parse start time, skipping item:", item);
          }
        });
        Object.keys(scheduleByDate).forEach((dateKey) => {
          scheduleByDate[dateKey].sort(
            (a, b) =>
              (parseLocalISO(a.startTime)?.getTime() || 0) -
              (parseLocalISO(b.startTime)?.getTime() || 0),
          );
        });
        setOptimizedSchedule(scheduleByDate);
        setIsOptimized(true); // Set optimized only if schedule data is present
      } else {
        console.warn("No valid schedule array received in response.");
        setOptimizedSchedule({});
        setIsOptimized(false);
      }

      // Update the full optimization result state, including filtered tasks
      setOptimizationResult({
        totalLeisure: result.total_leisure ?? null,
        totalStress: result.total_stress ?? null,
        status: result.status || "Unknown",
        message: result.message || null,
        warnings: result.warnings || null,
        filteredTasksInfo: result.filtered_tasks_info || null, // Store filtered info
      });

      // Set general error only if overall status indicates failure beyond just filtering
      if (
        result.status &&
        ![
          "Optimal",
          "Suboptimal",
          "Time Limit Reached",
          "Feasible",
          "No Schedulable Tasks",
        ].includes(result.status)
      ) {
        setError(
          result.message ||
            `Optimization finished with status: ${result.status}`,
        );
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
        filteredTasksInfo: null,
      });
    } finally {
      setIsLoading(false);
    }
  };

  // --- Schedule Import Handler ---
  const handleImport = (scheduleText: string) => {
    setImportErrors([]); // Clear previous errors
    const { blocks: newBlocksData, errors: parseErrors } = parseNtuSchedule(
      scheduleText,
      new Date(), // Use current date as reference to start generating weeks
      // Optional: Add numberOfWeeksToGenerate if you changed the default
    );

    if (parseErrors.length > 0) {
      setImportErrors(parseErrors);
      // Keep modal open if errors occurred
    } else if (newBlocksData.length > 0) {
      const fullNewBlocks: BlockedInterval[] = newBlocksData.map(
        (blockData) => ({
          ...blockData,
          id: `imported-${Date.now()}-${Math.random().toString(16).slice(2)}-${blockData.startTime}`, // Add startTime to help uniqueness
        }),
      );
      // Add new blocks to existing ones
      // Consider replacing instead of appending if the user imports again
      setBlockedIntervals((prevBlocks) => {
        // Filter out previously imported blocks before adding new ones
        const manualBlocks = prevBlocks.filter(
          (b) => !b.id.startsWith("imported-"),
        );
        return [...manualBlocks, ...fullNewBlocks];
      });
      // setBlockedIntervals(fullNewBlocks); // Replace existing blocks
      setShowImportModal(false); // Close modal on success
    } else {
      setImportErrors(["No valid class schedule details found in the text."]);
    }
  };

  // --- Form Handlers ---
  const handleTaskFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    formType: "new" | "edit",
  ) => {
    const { name, value, type } = e.target;

    if (formType === "new") {
      setNewTaskData((prev) => {
        // Handle deadlineType specifically due to typing constraints
        if (name === "deadlineType") {
          if (value === "days" || value === "date") {
            return { ...prev, deadlineType: value };
          }
          return prev;
        }

        // Special case for changing to days
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
          return { ...prev, deadlineType: "days", deadline: relativeDays };
        }

        // Special case for changing to date
        if (name === "deadlineType" && value === "date") {
          let dateValue = prev.deadlineDate;
          if (typeof prev.deadline === "number" && prev.deadline >= 0) {
            dateValue = format(
              addDays(new Date(), prev.deadline),
              "yyyy-MM-dd",
            );
          }
          return { ...prev, deadlineType: "date", deadlineDate: dateValue };
        }

        // Handle numeric fields
        const isNumeric =
          ["priority", "difficulty", "duration", "deadline"].includes(name) &&
          type !== "select" &&
          name !== "deadlineDate";

        return {
          ...prev,
          [name]: isNumeric ? parseInt(value) || 0 : value,
        };
      });
    } else if (editTaskData) {
      // Only update if we have existing data
      setEditTaskData((prev) => {
        if (!prev) return null;

        // Handle deadlineType specifically due to typing constraints
        if (name === "deadlineType") {
          if (value === "days" || value === "date") {
            return { ...prev, deadlineType: value };
          }
          return prev;
        }

        // Special case for changing to days
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
          return { ...prev, deadlineType: "days", deadline: relativeDays };
        }

        // Special case for changing to date
        if (name === "deadlineType" && value === "date") {
          let dateValue = prev.deadlineDate;
          if (typeof prev.deadline === "number" && prev.deadline >= 0) {
            dateValue = format(
              addDays(new Date(), prev.deadline),
              "yyyy-MM-dd",
            );
          }
          return { ...prev, deadlineType: "date", deadlineDate: dateValue };
        }

        // Handle numeric fields
        const isNumeric =
          ["priority", "difficulty", "duration", "deadline"].includes(name) &&
          type !== "select" &&
          name !== "deadlineDate";

        return {
          ...prev,
          [name]: isNumeric ? parseInt(value) || 0 : value,
        };
      });
    }
  };

  const handleBlockFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    formType: "new" | "edit",
  ) => {
    const { name, value } = e.target;

    if (formType === "new") {
      setNewBlockData((prev) => {
        return { ...prev, [name]: value };
      });
    } else if (editBlockData) {
      setEditBlockData((prev) => {
        if (!prev) return null;
        return { ...prev, [name]: value };
      });
    }
  };

  // --- Add/Edit Submit Handlers ---
  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null); // Clear modal error state at the beginning
    const processedData = processTaskData(newTaskData);
    if (processedData) {
      const newTask: Task = {
        id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        ...processedData,
      };
      setTasks((prev) => [...prev, newTask]);
      setShowNewTaskForm(false);
      resetNewTaskForm();
    } else {
      // If processTaskData returns null, there was an error in validation
      setError("Invalid task data. Please check your inputs.");
    }
  };

  const handleEditTask = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!editingTask || !editTaskData) return;

    const processedData = processTaskData(editTaskData);
    if (processedData) {
      setTasks((prevTasks) =>
        prevTasks.map((task) =>
          task.id === editingTask.id
            ? {
                ...task,
                ...processedData,
                difficulty: processedData.difficulty ?? task.difficulty,
              } // Ensure difficulty updates
            : task,
        ),
      );
      // Clear this specific task from filtered list if it was edited successfully
      setOptimizationResult((prev) => ({
        ...prev,
        filteredTasksInfo:
          prev.filteredTasksInfo?.filter((t) => t.id !== editingTask.id) ||
          null,
      }));
      closeAndResetEditTaskForm();
    } else {
      // If processTaskData returns null, there was an error in validation
      setError("Invalid task data. Please check your inputs.");
    }
  };

  const handleAddBlock = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const processedData = processBlockData(newBlockData);
    if (processedData) {
      const newBlock: BlockedInterval = {
        id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        ...processedData,
      };
      setBlockedIntervals((prev) => [...prev, newBlock]);
      setShowNewBlockForm(false);
      resetNewBlockForm();
    } else {
      // If processBlockData returns null, there was an error in validation
      setError("Invalid blocked time data. Please check your inputs.");
    }
  };

  const handleEditBlock = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!editingBlock || !editBlockData) return;

    const processedData = processBlockData(editBlockData);
    if (processedData) {
      setBlockedIntervals((prevBlocks) =>
        prevBlocks.map((block) =>
          block.id === editingBlock.id ? { ...block, ...processedData } : block,
        ),
      );
      closeAndResetEditBlockForm();
    } else {
      // If processBlockData returns null, there was an error in validation
      setError("Invalid blocked time data. Please check your inputs.");
    }
  };

  // --- Delete Handlers ---
  const handleDeleteTask = (taskId: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== taskId));
    // Also remove from filtered list if present
    setOptimizationResult((prev) => ({
      ...prev,
      filteredTasksInfo:
        prev.filteredTasksInfo?.filter((t) => t.id !== taskId) || null,
    }));
  };

  const handleDeleteBlock = (blockId: string) => {
    setBlockedIntervals((prev) => prev.filter((block) => block.id !== blockId));
  };

  // --- Edit Click Handlers ---
  const handleEditTaskClick = (task: Task) => {
    setEditingTask(task);
    // Reset hint, it will be set by handleEditFilteredTask if needed
    setEditTaskMinDurationHint(null);
  };

  const handleEditBlockClick = (block: BlockedInterval) => {
    setEditingBlock(block);
  };

  // --- Edit Click Handler for Filtered Tasks ---
  const handleEditFilteredTask = (filteredTaskInfo: FilteredTaskInfo) => {
    const originalTask = getTaskById(filteredTaskInfo.id);
    if (originalTask) {
      setEditingTask(originalTask); // Trigger the edit form population
      // Set the duration hint based on the filtered info
      setEditTaskMinDurationHint(filteredTaskInfo.required_duration_min);
    } else {
      console.error(
        "Could not find original task for filtered task:",
        filteredTaskInfo,
      );
      setError(
        `Could not find original task data for '${filteredTaskInfo.name}'.`,
      );
    }
  };

  // --- Auto Adjust Duration Handler ---
  const handleAutoAdjustDuration = (filteredTaskInfo: FilteredTaskInfo) => {
    if (filteredTaskInfo.required_duration_min === null) return; // Should not happen if button is shown

    setTasks((prevTasks) =>
      prevTasks.map((task) =>
        task.id === filteredTaskInfo.id
          ? { ...task, duration: filteredTaskInfo.required_duration_min! } // Update duration
          : task,
      ),
    );

    // Remove this task from the filtered list as it's now adjusted
    setOptimizationResult((prev) => ({
      ...prev,
      filteredTasksInfo:
        prev.filteredTasksInfo?.filter((t) => t.id !== filteredTaskInfo.id) ||
        null,
    }));

    console.log(
      `Auto-adjusted duration for task '${filteredTaskInfo.name}' to ${filteredTaskInfo.required_duration_min} minutes.`,
    );
  };

  // --- Event Click Handler ---
  const handleEventClick = (eventData: ScheduledTaskItem | BlockedInterval) => {
    console.log(`Clicked event:`, eventData);
    setSelectedEvent(eventData);
    setShowEventDetailsModal(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-slate-900 text-gray-100 p-4 md:p-8 font-sans">
      <div className="max-w-screen-2xl mx-auto">
        <header className="flex items-center justify-between gap-3 mb-8">
          <div className="flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-purple-400 flex-shrink-0" />
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-purple-400 to-pink-500 text-transparent bg-clip-text">
              IntelliSchedule
            </h1>
          </div>
          {/* Explanation Button */}
          <button
            onClick={() => setShowExplanation(true)}
            className="text-gray-400 hover:text-purple-300 transition-colors p-2 rounded-full hover:bg-gray-700 flex items-center gap-1.5 text-sm"
            title="Explain Scheduler Logic"
          >
            <HelpCircle size={18} /> How it Works
          </button>
        </header>

        {/* General Error Display */}
        {error &&
          !showNewBlockForm &&
          !showNewTaskForm &&
          !showEditBlockForm &&
          !showEditTaskForm && (
            <div className="mb-4 p-3 rounded-lg text-sm bg-red-900 border border-red-700 flex justify-between items-center">
              <span className="flex items-center gap-2">
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

        {/* Main Content Area */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* Left Column (1/4) */}
          <div className="xl:col-span-1 space-y-6">
            <TimeWindow
              startHour={startHour}
              endHour={endHour}
              modelType={modelType}
              alpha={alpha}
              beta={beta}
              dailyLimit={dailyLimit}
              onStartHourChange={setStartHour}
              onEndHourChange={setEndHour}
              onModelTypeChange={setModelType}
              onAlphaChange={setAlpha}
              onBetaChange={setBeta}
              onDailyLimitChange={setDailyLimit}
              onShowExplanation={() => setShowExplanation(true)}
            />

            <TasksList
              tasks={tasks}
              filteredTasksInfo={optimizationResult.filteredTasksInfo}
              isLoading={isLoading}
              onAddTask={() => setShowNewTaskForm(true)}
              onEditTask={handleEditTaskClick}
              onDeleteTask={handleDeleteTask}
              onOptimize={handleOptimize}
              onEditFilteredTask={handleEditFilteredTask}
              onAutoAdjustDuration={handleAutoAdjustDuration}
              onGenerateTasks={handleGenerateTasks}
            />

            <BlockedIntervalsList
              blockedIntervals={blockedIntervals}
              isLoading={isLoading}
              onAddBlock={() => setShowNewBlockForm(true)}
              onEditBlock={handleEditBlockClick}
              onDeleteBlock={handleDeleteBlock}
              onGenerateBlocks={handleGenerateBlocks}
            />
            {/* Keep Import Button */}
            <button
              onClick={() => {
                setShowImportModal(true);
                setImportErrors([]);
              }}
              disabled={isLoading}
              className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-800 text-sm py-2.5 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors"
            >
              Import NTU Schedule
            </button>
          </div>

          {/* Right Column (3/4) */}
          <div className="xl:col-span-3">
            <CalendarComponent
              currentWeekStart={currentWeekStart}
              setCurrentWeekStart={setCurrentWeekStart}
              optimizedSchedule={optimizedSchedule}
              blockedIntervals={blockedIntervals}
              isOptimized={isOptimized}
              optimizationResult={{
                totalLeisure: optimizationResult.totalLeisure,
                totalStress: optimizationResult.totalStress,
                status: optimizationResult.status,
                message: optimizationResult.message,
                warnings: optimizationResult.warnings,
              }}
              error={error}
              onEventClick={handleEventClick}
            />

            {/* Move ScheduledTasksList inside the right column, below the calendar */}
            {isOptimized && Object.keys(optimizedSchedule).length > 0 && (
              <ScheduledTasksList schedule={optimizedSchedule} />
            )}
          </div>
        </div>

        {/* Modals */}
        {showNewTaskForm && (
          <Modal
            title="Add New Task"
            onClose={() => {
              setShowNewTaskForm(false);
              resetNewTaskForm();
              setError(null);
            }}
            onSubmit={handleAddTask}
            submitText="Add Task"
            error={error}
          >
            <TaskFormFields
              formData={newTaskData}
              onChange={(e) => handleTaskFormChange(e, "new")}
              formIdPrefix="new"
            />
          </Modal>
        )}

        {showEditTaskForm && editTaskData && (
          <Modal
            title="Edit Task"
            onClose={closeAndResetEditTaskForm}
            onSubmit={handleEditTask}
            submitText="Save Changes"
            error={error}
          >
            <TaskFormFields
              formData={editTaskData}
              onChange={(e) => handleTaskFormChange(e, "edit")}
              formIdPrefix="edit"
              minDurationHint={editTaskMinDurationHint}
            />
          </Modal>
        )}

        {showNewBlockForm && (
          <Modal
            title="Add Blocked Time"
            onClose={() => {
              setShowNewBlockForm(false);
              resetNewBlockForm();
              setError(null);
            }}
            onSubmit={handleAddBlock}
            submitText="Add Blocked Time"
            error={error}
          >
            <BlockFormFields
              formData={newBlockData}
              onChange={(e) => handleBlockFormChange(e, "new")}
              formIdPrefix="new"
            />
          </Modal>
        )}

        {showEditBlockForm && editBlockData && (
          <Modal
            title="Edit Blocked Time"
            onClose={closeAndResetEditBlockForm}
            onSubmit={handleEditBlock}
            submitText="Save Changes"
            error={error}
          >
            <BlockFormFields
              formData={editBlockData}
              onChange={(e) => handleBlockFormChange(e, "edit")}
              formIdPrefix="edit"
            />
          </Modal>
        )}

        <EventDetailsModal
          showModal={showEventDetailsModal}
          selectedEvent={selectedEvent}
          onClose={() => setShowEventDetailsModal(false)}
        />

        {/* Import Schedule Modal */}
        {showImportModal && (
          <ImportScheduleModal
            onClose={() => setShowImportModal(false)}
            onImport={handleImport}
            importErrors={importErrors}
          />
        )}

        {/* Model Explanation Modal */}
        {showExplanation && (
          <ModelExplanation onClose={() => setShowExplanation(false)} />
        )}
      </div>

      <footer className="text-center text-xs text-gray-500 mt-12 pb-4">
        IntelliSchedule v1.5 - React + Flask + Gurobi
      </footer>
    </div>
  );
}

export default App;
