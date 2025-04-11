// Types for IntelliSchedule application

// Main task interface
export interface Task {
  id: string;
  name: string;
  priority: number;
  difficulty: number;
  duration: number; // Duration in minutes
  deadline: string | number; // ISO string (local assumed) or relative days
  preference: "morning" | "afternoon" | "evening" | "any";
}

// Blocked time intervals
export interface BlockedInterval {
  id: string;
  startTime: string; // Naive local ISO format string (e.g., YYYY-MM-DDTHH:MM:SS)
  endTime: string; // Naive local ISO format string
  activity: string;
}

// Matches the backend response format for scheduled items
export interface ScheduledTaskItem {
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

// Interface for filtered task info from backend
export interface FilteredTaskInfo {
  id: string;
  name: string;
  reason: string;
  required_duration_min: number | null; // Can be null if filtered for other reasons
  current_duration_min: number;
}

// Keep track of scheduled tasks per day (key: 'yyyy-MM-dd')
export type OptimizedSchedule = Record<string, ScheduledTaskItem[]>;

// Form data types
export interface TaskFormData {
  name: string;
  priority: number;
  difficulty: number;
  duration: number;
  deadline: string | number; // For relative days input
  deadlineType: "days" | "date";
  preference: Task["preference"];
  deadlineDate: string; // For specific date input YYYY-MM-DD
}

export interface BlockFormData {
  activity: string;
  startTime: string; // HH:mm
  endTime: string; // HH:mm
  date: string; // YYYY-MM-DD
}

// Optimization result type
export interface OptimizationResult {
  totalLeisure: number | null;
  totalStress: number | null;
  status: string | null;
  message: string | null;
  warnings: string[] | null;
  filteredTasksInfo: FilteredTaskInfo[] | null;
}