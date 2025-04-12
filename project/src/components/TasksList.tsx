import React from "react";
import {
  AlertCircle,
  Plus,
  Sparkles,
  Loader2,
  Edit,
  Trash2,
  HelpCircle,
  CheckCircle,
  Wand2, // Icon for auto-generate
} from "lucide-react";
import { Task, FilteredTaskInfo } from "../types";
import { getDeadlineDisplay } from "../utils/dateUtils";

interface TasksListProps {
  tasks: Task[];
  filteredTasksInfo: FilteredTaskInfo[] | null;
  isLoading: boolean;
  // isManualMode: boolean; // <-- REMOVE
  onAddTask: () => void;
  onEditTask: (task: Task) => void;
  onDeleteTask: (taskId: string) => void;
  onOptimize: () => void;
  onEditFilteredTask: (filteredTask: FilteredTaskInfo) => void;
  onAutoAdjustDuration: (filteredTask: FilteredTaskInfo) => void;
  onGenerateTasks: () => void; // <-- ADD Prop
}

const TasksList: React.FC<TasksListProps> = ({
  tasks,
  filteredTasksInfo,
  isLoading,
  // isManualMode, // <-- REMOVE
  onAddTask,
  onEditTask,
  onDeleteTask,
  onOptimize,
  onEditFilteredTask,
  onAutoAdjustDuration,
  onGenerateTasks, // <-- ADD Prop
}) => {
  return (
    <div className="bg-gray-800 p-6 rounded-xl shadow-lg">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-purple-400 flex-shrink-0" />{" "}
          Tasks ({tasks.length})
        </h2>
        <div className="flex gap-2 flex-wrap">
          {" "}
          {/* Add flex-wrap for smaller screens */}
          <button
            onClick={onGenerateTasks} // <-- Use the new handler
            disabled={isLoading}
            className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
            title="Replace current tasks with a sample set"
          >
            <Wand2 className="w-4 h-4" /> Generate Sample
          </button>
          {/* Always show Add button now */}
          <button
            onClick={onAddTask}
            disabled={isLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Manually
          </button>
          <button
            onClick={onOptimize}
            disabled={isLoading || tasks.length === 0}
            className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:text-gray-400 disabled:cursor-not-allowed text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}{" "}
            Optimize
          </button>
        </div>
      </div>

      {/* Display Filtered Task Info */}
      {filteredTasksInfo && filteredTasksInfo.length > 0 && (
        <div className="mb-4 p-3 rounded-lg bg-yellow-900 border border-yellow-700 text-yellow-200">
          <p className="font-semibold mb-2 text-yellow-100 flex items-center gap-2">
            <HelpCircle size={18} /> Some tasks require more time to meet the
            scheduling criteria:
          </p>
          <ul className="space-y-2 list-none">
            {filteredTasksInfo.map((filteredTask) => (
              <li
                key={filteredTask.id}
                className="flex justify-between items-center text-sm gap-2 flex-wrap"
              >
                <span className="flex-1 min-w-[200px]">
                  <span className="font-medium">{filteredTask.name}</span>
                  <span className="text-xs opacity-80 block">
                    {filteredTask.reason}
                  </span>
                </span>
                {/* Actions for Filtered Tasks */}
                {filteredTask.required_duration_min !== null && (
                  <div className="flex gap-1.5 flex-shrink-0">
                    <button
                      onClick={() => onAutoAdjustDuration(filteredTask)}
                      className="text-xs bg-green-700 hover:bg-green-600 text-green-100 py-1 px-2 rounded transition-colors flex items-center gap-1"
                      title={`Set duration to ${filteredTask.required_duration_min} min`}
                    >
                      <CheckCircle size={12} /> Adjust
                    </button>
                    <button
                      onClick={() => onEditFilteredTask(filteredTask)}
                      className="text-xs bg-yellow-700 hover:bg-yellow-600 text-yellow-100 py-1 px-2 rounded transition-colors flex items-center gap-1"
                    >
                      <Edit size={12} /> Edit
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {tasks.length === 0 && !isLoading && (
        <p className="text-gray-400 text-center py-4 italic">
          No tasks added yet. Add manually or generate a sample.
        </p>
      )}

      <div className="overflow-x-auto max-h-96 custom-scrollbar">
        <table className="w-full min-w-[700px] border-separate border-spacing-y-1">
          <thead className="sticky top-0 bg-gray-800 z-10">
            <tr className="text-left text-sm text-gray-400">
              <th className="pb-2 px-1 font-medium text-center w-20">
                Actions
              </th>
              <th className="pb-2 px-3 font-medium">Name</th>
              <th className="pb-2 px-3 font-medium text-center">Prio</th>
              <th className="pb-2 px-3 font-medium text-center">Diff</th>
              <th className="pb-2 px-3 font-medium text-center">Dur</th>
              <th className="pb-2 px-3 font-medium">Deadline</th>
              <th className="pb-2 px-3 font-medium">Pref</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr
                key={task.id}
                className="bg-gray-750 hover:bg-gray-700 transition-colors rounded-lg"
              >
                <td className="py-2.5 px-1 text-center rounded-l-lg">
                  {" "}
                  {/* Adjusted padding and rounded corner */}
                  <div className="flex justify-center items-center gap-1.5">
                    <button
                      onClick={() => onEditTask(task)}
                      title="Edit Task"
                      className="p-1 text-gray-400 hover:text-blue-400 transition-colors rounded-full hover:bg-gray-600"
                    >
                      <Edit size={16} />
                    </button>
                    <button
                      onClick={() => onDeleteTask(task.id)}
                      title="Delete Task"
                      className="p-1 text-gray-400 hover:text-red-400 transition-colors rounded-full hover:bg-gray-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
                <td className="py-2.5 px-3">{task.name}</td>{" "}
                {/* Removed rounded corner */}
                <td className="py-2.5 px-3 text-center">{task.priority}</td>
                <td className="py-2.5 px-3 text-center">{task.difficulty}</td>
                <td className="py-2.5 px-3 text-center">
                  {task.duration}
                  <span className="text-xs text-gray-400">m</span>
                </td>
                <td className="py-2.5 px-3 text-xs">
                  {getDeadlineDisplay(task.deadline)}
                </td>
                <td className="py-2.5 px-3 capitalize text-xs rounded-r-lg">
                  {" "}
                  {/* Added rounded corner */}
                  {task.preference}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TasksList;
