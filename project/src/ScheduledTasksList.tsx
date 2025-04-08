import React from "react";
import { format, parseISO } from "date-fns";
import { ListChecks, Clock } from "lucide-react";

// Interface matching App.tsx
interface ScheduledTaskItem {
  id: string;
  name: string;
  startTime: string; // Naive local ISO format string
  endTime: string; // Naive local ISO format string
  priority: number;
  duration_min: number;
  // Add other properties if needed for display
}

// Matches the OptimizedSchedule type in App.tsx
type OptimizedSchedule = Record<string, ScheduledTaskItem[]>;

// Helper matching App.tsx
const parseLocalISO = (dateString: string | null | undefined): Date | null => {
  if (!dateString) return null;
  try {
    let adjustedString = dateString;
    if (dateString.length === 16) adjustedString = dateString + ":00";
    else if (dateString.length === 10)
      adjustedString = dateString + "T00:00:00";
    const parsed = parseISO(adjustedString);
    return parsed instanceof Date && !isNaN(parsed.valueOf()) ? parsed : null;
  } catch (e) {
    console.error("Error parsing date string:", dateString, e);
    return null;
  }
};

interface ScheduledTasksListProps {
  schedule: OptimizedSchedule;
}

const ScheduledTasksList: React.FC<ScheduledTasksListProps> = ({
  schedule,
}) => {
  // Get sorted dates from the schedule keys
  const sortedDates = Object.keys(schedule).sort((a, b) => {
    const dateA = parseLocalISO(a)?.getTime() || 0;
    const dateB = parseLocalISO(b)?.getTime() || 0;
    return dateA - dateB;
  });

  if (sortedDates.length === 0) {
    return null; // Don't render anything if the schedule is empty
  }

  return (
    <div className="bg-gray-800 p-4 sm:p-6 rounded-xl shadow-lg mt-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <ListChecks className="w-5 h-5 text-purple-400" />
        Allocated Tasks List
      </h2>
      <div className="space-y-6 max-h-[50vh] overflow-y-auto pr-2">
        {" "}
        {/* Add scroll */}
        {sortedDates.map((dateKey) => {
          const tasksForDate = schedule[dateKey];
          const displayDate = parseLocalISO(dateKey);

          // Tasks within each day are already sorted by time in App.tsx
          // but we can double-check or re-sort if needed:
          // tasksForDate.sort((a, b) => (parseLocalISO(a.startTime)?.getTime() || 0) - (parseLocalISO(b.startTime)?.getTime() || 0));

          return (
            <div key={dateKey}>
              <h3 className="text-lg font-medium mb-3 text-purple-300 border-b border-gray-700 pb-1.5">
                {displayDate
                  ? format(displayDate, "EEEE, MMMM dd, yyyy")
                  : dateKey}
              </h3>
              <ul className="space-y-2">
                {tasksForDate.map((task) => {
                  const startTime = parseLocalISO(task.startTime);
                  const endTime = parseLocalISO(task.endTime);
                  return (
                    <li
                      key={task.id}
                      className="flex items-start gap-3 p-2 bg-gray-750 rounded-md hover:bg-gray-700 transition-colors"
                    >
                      <Clock
                        size={16}
                        className="mt-1 text-gray-400 flex-shrink-0"
                      />
                      <div>
                        <p className="font-medium">{task.name}</p>
                        <p className="text-xs text-gray-400">
                          {startTime ? format(startTime, "HH:mm") : "N/A"} -{" "}
                          {endTime ? format(endTime, "HH:mm") : "N/A"}
                          <span className="mx-2 text-gray-600">|</span>
                          {task.duration_min} min
                          <span className="mx-2 text-gray-600">|</span>
                          Prio: {task.priority}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
      {sortedDates.length === 0 && (
        <p className="text-gray-400 text-center py-4 italic">
          No tasks have been scheduled yet. Optimize first.
        </p>
      )}
    </div>
  );
};

export default ScheduledTasksList;
