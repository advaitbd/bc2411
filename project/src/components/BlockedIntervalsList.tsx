import React from "react";
import {
  Clock,
  Plus,
  Edit,
  Trash2,
  Wand2, // Icon for auto-generate
} from "lucide-react";
import { BlockedInterval } from "../types";
import { parseLocalISO } from "../utils/dateUtils"; // Ensure this is imported
import { format } from "date-fns";
import { useMemo } from "react";

interface BlockedIntervalsListProps {
  blockedIntervals: BlockedInterval[];
  isLoading: boolean;
  onAddBlock: () => void;
  onEditBlock: (block: BlockedInterval) => void;
  onDeleteBlock: (blockId: string) => void;
  onGenerateBlocks: () => void; // <-- ADD Prop
}

const BlockedIntervalsList: React.FC<BlockedIntervalsListProps> = ({
  blockedIntervals,
  isLoading,
  onAddBlock,
  onEditBlock,
  onDeleteBlock,
  onGenerateBlocks, // <-- ADD Prop
}) => {
  // Sort intervals for consistent display
  const sortedIntervals = useMemo(() => {
    return [...blockedIntervals].sort(
      (a, b) =>
        (parseLocalISO(a.startTime)?.getTime() || 0) -
        (parseLocalISO(b.startTime)?.getTime() || 0),
    );
  }, [blockedIntervals]);

  return (
    <div className="bg-gray-800 p-6 rounded-xl shadow-lg">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Clock className="w-5 h-5 text-purple-400 flex-shrink-0" /> Blocked
          Times ({blockedIntervals.length})
        </h2>
        <div className="flex gap-2 flex-wrap">
          {" "}
          {/* Add flex-wrap */}
          <button
            onClick={onGenerateBlocks} // <-- Use the new handler
            disabled={isLoading}
            className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
            title="Replace current blocked times with a sample set (classes, meals etc.)"
          >
            <Wand2 className="w-4 h-4" /> Generate Sample
          </button>
          <button
            onClick={onAddBlock}
            disabled={isLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Manually
          </button>
        </div>
      </div>
      {sortedIntervals.length === 0 && (
        <p className="text-gray-400 text-center py-4 italic">
          No blocked times added yet. Add manually, import schedule, or generate
          a sample.
        </p>
      )}
      <div className="overflow-x-auto max-h-96 custom-scrollbar">
        <table className="w-full min-w-[600px] border-separate border-spacing-y-1">
          <thead className="sticky top-0 bg-gray-800 z-10">
            <tr className="text-left text-sm text-gray-400">
              <th className="pb-2 px-1 font-medium text-center w-20">
                Actions
              </th>
              <th className="pb-2 px-3 font-medium">Activity</th>
              <th className="pb-2 px-3 font-medium">Start Time</th>
              <th className="pb-2 px-3 font-medium">End Time</th>
            </tr>
          </thead>
          <tbody>
            {sortedIntervals.map((interval) => (
              <tr
                key={interval.id}
                className="bg-gray-750 hover:bg-gray-700 transition-colors rounded-lg"
              >
                <td className="py-2.5 px-1 text-center rounded-l-lg">
                  {" "}
                  {/* Adjusted padding and rounded corner */}
                  <div className="flex justify-center items-center gap-1.5">
                    <button
                      onClick={() => onEditBlock(interval)}
                      title="Edit Blocked Time"
                      className="p-1 text-gray-400 hover:text-blue-400 transition-colors rounded-full hover:bg-gray-600"
                    >
                      <Edit size={16} />
                    </button>
                    <button
                      onClick={() => onDeleteBlock(interval.id)}
                      title="Delete Blocked Time"
                      className="p-1 text-gray-400 hover:text-red-400 transition-colors rounded-full hover:bg-gray-600"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </td>
                <td className="py-2.5 px-3">{interval.activity}</td>{" "}
                {/* Removed rounded corner */}
                <td className="py-2.5 px-3 text-sm">
                  {format(
                    parseLocalISO(interval.startTime) || new Date(),
                    "MMM dd, HH:mm",
                  )}
                </td>
                <td className="py-2.5 px-3 text-sm rounded-r-lg">
                  {" "}
                  {/* Added rounded corner */}
                  {format(
                    parseLocalISO(interval.endTime) || new Date(),
                    "HH:mm",
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default BlockedIntervalsList;
