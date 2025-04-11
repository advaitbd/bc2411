import React from "react";
import { Clock, Plus, Edit, Trash2 } from "lucide-react";
import { BlockedInterval } from "../types";
import { parseLocalISO } from "../utils/dateUtils";
import { format } from "date-fns";

interface BlockedIntervalsListProps {
  blockedIntervals: BlockedInterval[];
  isLoading: boolean;
  onAddBlock: () => void;
  onEditBlock: (block: BlockedInterval) => void;
  onDeleteBlock: (blockId: string) => void;
}

const BlockedIntervalsList: React.FC<BlockedIntervalsListProps> = ({
  blockedIntervals,
  isLoading,
  onAddBlock,
  onEditBlock,
  onDeleteBlock,
}) => {
  return (
    <div className="bg-gray-800 p-6 rounded-xl shadow-lg">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Clock className="w-5 h-5 text-purple-400 flex-shrink-0" /> Blocked
          Times ({blockedIntervals.length})
        </h2>
        <button
          onClick={onAddBlock}
          disabled={isLoading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-sm py-2 px-4 rounded-lg flex items-center gap-2 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Block
        </button>
      </div>
      {blockedIntervals.length === 0 && (
        <p className="text-gray-400 text-center py-4 italic">
          No blocked times added yet.
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
              .sort(
                (a, b) =>
                  (parseLocalISO(a.startTime)?.getTime() || 0) -
                  (parseLocalISO(b.startTime)?.getTime() || 0)
              )
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
                      "MMM dd, HH:mm"
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-sm">
                    {format(
                      parseLocalISO(interval.endTime) || new Date(),
                      "HH:mm"
                    )}
                  </td>
                  <td className="py-2.5 px-1 text-center rounded-r-lg">
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
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default BlockedIntervalsList;