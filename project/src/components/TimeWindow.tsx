import React from "react";
import { Settings, Info } from "lucide-react";

interface TimeWindowProps {
  startHour: number;
  endHour: number;
  onStartHourChange: (hour: number) => void;
  onEndHourChange: (hour: number) => void;
}

const TimeWindow: React.FC<TimeWindowProps> = ({
  startHour,
  endHour,
  onStartHourChange,
  onEndHourChange,
}) => {
  return (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Settings className="w-5 h-5 text-purple-400" />
        Scheduling Window Preference
      </h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <label htmlFor="startHour" className="block text-sm text-gray-400 mb-2">
            Start Hour (00:00 - 23:00)
          </label>
          <select
            id="startHour"
            value={startHour}
            onChange={(e) => onStartHourChange(parseInt(e.target.value))}
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
              onEndHourChange(Math.max(startHour + 1, parseInt(e.target.value)))
            }
            className="bg-gray-700 rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-purple-400 appearance-none cursor-pointer border border-gray-600"
          >
            {Array.from({ length: 24 }, (_, i) => i + 1).map((hour) => (
              <option
                key={hour}
                value={hour}
                disabled={hour <= startHour}
              >{`${hour === 24 ? "24" : hour.toString().padStart(2, "0")}:00`}</option>
            ))}
          </select>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
        <Info size={12} /> Note: Backend currently uses 8am-10pm (22:00) internally.
      </p>
    </div>
  );
};

export default TimeWindow;