import React from "react";
import { Settings } from "lucide-react";
import ModelToggle from "./ModelToggle";
import TradeoffSlider from "./TradeoffSlider";
import DailyLimit from "./DailyLimit";

interface TimeWindowProps {
  startHour: number;
  endHour: number;
  modelType: "deadline_penalty" | "no_y";
  alpha: number;
  beta: number;
  dailyLimit: number | null;
  onStartHourChange: (hour: number) => void;
  onEndHourChange: (hour: number) => void;
  onModelTypeChange: (modelType: "deadline_penalty" | "no_y") => void;
  onAlphaChange: (value: number) => void;
  onBetaChange: (value: number) => void;
  onDailyLimitChange: (value: number | null) => void;
  onShowExplanation: () => void;
}

const TimeWindow: React.FC<TimeWindowProps> = ({
  startHour,
  endHour,
  modelType,
  alpha,
  beta,
  dailyLimit,
  onStartHourChange,
  onEndHourChange,
  onModelTypeChange,
  onAlphaChange,
  onBetaChange,
  onDailyLimitChange,
  onShowExplanation,
}) => {
  return (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <Settings className="w-5 h-5 text-purple-400" />
        Scheduling Preferences
      </h2>
      <div className="flex flex-col md:flex-row gap-6">
        <div className="flex-1 max-w-xs">
          <label
            htmlFor="startHour"
            className="block text-sm text-gray-400 mb-2"
          >
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
        <div className="flex-1 max-w-xs">
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
        <div className="flex-1 max-w-xs">
          <ModelToggle
            modelType={modelType}
            onChange={onModelTypeChange}
            onExplanationClick={onShowExplanation}
          />
        </div>
      </div>
      
      {/* Add optimization tradeoff slider */}
      <div className="mt-6 border-t border-gray-700 pt-6 space-y-6">
        <TradeoffSlider
          alpha={alpha}
          beta={beta}
          onAlphaChange={onAlphaChange}
          onBetaChange={onBetaChange}
        />
        
        {/* Add daily limit control */}
        <DailyLimit
          dailyLimit={dailyLimit}
          onDailyLimitChange={onDailyLimitChange}
        />
      </div>
    </div>
  );
};

export default TimeWindow;
