import React from "react";
import { Clock } from "lucide-react";

interface DailyLimitProps {
  dailyLimit: number | null;
  onDailyLimitChange: (value: number | null) => void;
}

const DailyLimit: React.FC<DailyLimitProps> = ({
  dailyLimit,
  onDailyLimitChange,
}) => {
  // Calculate slots for the current day based on 15-min intervals (4 slots per hour)
  // This is just for display purposes
  const calculateMinutes = (slots: number | null): number | null => {
    if (slots === null) return null;
    return slots * 15;
  };
  
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === "none") {
      onDailyLimitChange(null);
    } else {
      onDailyLimitChange(parseInt(value));
    }
  };

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-300 flex items-center gap-2">
          <Clock size={16} className="text-purple-400" /> Daily Task Limit
        </span>
      </div>
      
      <div className="flex items-center gap-2">
        <select
          id="dailyLimitSlots"
          value={dailyLimit === null ? "none" : dailyLimit.toString()}
          onChange={handleChange}
          className="bg-gray-700 rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-purple-400 appearance-none cursor-pointer border border-gray-600"
        >
          <option value="none">No Limit</option>
          {/* Offer range from 4 (1 hour) to 40 (10 hours) in different increments */}
          <option value="4">1 hour (4 slots)</option>
          <option value="8">2 hours (8 slots)</option>
          <option value="12">3 hours (12 slots)</option>
          <option value="16">4 hours (16 slots)</option>
          <option value="20">5 hours (20 slots)</option>
          <option value="24">6 hours (24 slots)</option>
          <option value="28">7 hours (28 slots)</option>
          <option value="32">8 hours (32 slots)</option>
          <option value="36">9 hours (36 slots)</option>
          <option value="40">10 hours (40 slots)</option>
        </select>
      </div>
      
      <p className="text-xs text-gray-400 mt-1">
        {dailyLimit === null 
          ? "No daily limit on scheduled tasks."
          : `Maximum of ${dailyLimit} slots (${calculateMinutes(dailyLimit)} minutes) of tasks per day.`}
      </p>
    </div>
  );
};

export default DailyLimit;