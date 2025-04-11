import React from "react";
import { HelpCircle } from "lucide-react";
import { TaskFormData, Task } from "../types";
import { format, addDays } from "date-fns";

interface TaskFormProps {
  formData: TaskFormData;
  onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  formIdPrefix: string;
  minDurationHint?: number | null;
}

const TaskFormFields: React.FC<TaskFormProps> = ({
  formData,
  onChange,
  formIdPrefix,
  minDurationHint,
}) => (
  <>
    {/* Task Name */}
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
    {/* Priority & Difficulty */}
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label
          htmlFor={`${formIdPrefix}TaskPriority`}
          className="block text-sm font-medium text-gray-300 mb-1"
        >
          Priority (1-5)
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
          htmlFor={`${formIdPrefix}TaskDifficulty`}
          className="block text-sm font-medium text-gray-300 mb-1"
        >
          Difficulty (1-5)
        </label>
        <input
          id={`${formIdPrefix}TaskDifficulty`}
          name="difficulty"
          type="number"
          min="1"
          max="5"
          value={formData.difficulty}
          onChange={onChange}
          required
          className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        />
      </div>
    </div>
    {/* Duration with Hint */}
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          className={`w-full bg-gray-700 rounded px-3 py-2 border ${
            minDurationHint && formData.duration < minDurationHint
              ? "border-yellow-500"
              : "border-gray-600"
          } focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent`}
        />
        {minDurationHint && (
          <p className="text-xs text-yellow-400 mt-1 flex items-center gap-1">
            <HelpCircle size={14} /> Suggestion: Minimum {minDurationHint}{" "}
            minutes needed for scheduling.
          </p>
        )}
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
    </div>
    {/* Deadline */}
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
          />{" "}
          Relative (Days)
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="radio"
            name="deadlineType"
            value="date"
            checked={formData.deadlineType === "date"}
            onChange={onChange}
            className="form-radio h-4 w-4 text-purple-500 bg-gray-600 border-gray-500 focus:ring-purple-500 focus:ring-offset-gray-800"
          />{" "}
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
  </>
);

// Utility functions related to task form
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

export default TaskFormFields;