import { Task, TaskFormData } from "../types";
import { addDays, isValid, startOfDay } from "date-fns";

// Function to process task form data and convert it to task object
export const processTaskData = (taskData: TaskFormData): Omit<Task, "id"> | null => {
  let modalError: string | null = null;

  let deadlineValue: string | number;
  if (taskData.deadlineType === "date") {
    const datePart = taskData.deadlineDate;
    if (!datePart || datePart.length !== 10) {
      modalError = "Invalid deadline date format. Use YYYY-MM-DD.";
    } else {
      deadlineValue = `${datePart}T23:59:59`; // Set to end of day
      const parsedDeadline = new Date(deadlineValue);
      if (!parsedDeadline || parsedDeadline < new Date(new Date().setHours(0, 0, 0, 0))) {
        modalError = "Deadline date cannot be in the past.";
      }
    }
  } else {
    const days = parseInt(String(taskData.deadline), 10);
    if (isNaN(days) || days < 0) {
      modalError = "Deadline days must be a non-negative number.";
    } else {
      deadlineValue = days;
    }
  }

  if (!taskData.name.trim()) {
    modalError = "Task name cannot be empty.";
  }
  const duration = parseInt(String(taskData.duration), 10);
  if (isNaN(duration) || duration <= 0) {
    modalError = "Task duration must be a positive number.";
  }
  const priority = parseInt(String(taskData.priority), 10);
  if (isNaN(priority) || priority < 1 || priority > 5) {
    modalError = "Priority must be between 1 and 5.";
  }
  const difficulty = parseInt(String(taskData.difficulty), 10);
  if (isNaN(difficulty) || difficulty < 1 || difficulty > 5) {
    modalError = "Difficulty must be between 1 and 5.";
  }

  if (modalError) {
    // Return error for handling by parent
    return null;
  }

  return {
    name: taskData.name.trim(),
    priority: priority || 1,
    difficulty: difficulty || 1,
    duration: duration,
    deadline: deadlineValue!,
    preference: taskData.preference,
  };
};