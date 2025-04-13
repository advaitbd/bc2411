import React from "react";
import { Scale } from "lucide-react";

interface TradeoffSliderProps {
  alpha: number;
  beta: number;
  onAlphaChange: (value: number) => void;
  onBetaChange: (value: number) => void;
}

const TradeoffSlider: React.FC<TradeoffSliderProps> = ({
  alpha,
  beta,
  onAlphaChange,
  onBetaChange,
}) => {
  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-300 flex items-center gap-2">
          <Scale size={16} className="text-purple-400" /> Optimization Balance
        </span>
      </div>
      
      <div className="space-y-4">
        <div>
          <div className="flex justify-between mb-1">
            <label htmlFor="alphaSlider" className="text-xs text-gray-400">
              Leisure (α): {alpha.toFixed(1)}
            </label>
            <span className="text-xs text-gray-400">
              {alpha < 1 ? "Less" : alpha > 1 ? "More" : "Default"} free time
            </span>
          </div>
          <input
            id="alphaSlider"
            type="range"
            min="0.5"
            max="2"
            step="0.1"
            value={alpha}
            onChange={(e) => onAlphaChange(parseFloat(e.target.value))}
            className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
          />
        </div>
        
        <div>
          <div className="flex justify-between mb-1">
            <label htmlFor="betaSlider" className="text-xs text-gray-400">
              Stress (β): {beta.toFixed(2)}
            </label>
            <span className="text-xs text-gray-400">
              {beta < 0.1 ? "Less" : beta > 0.1 ? "More" : "Default"} weight
            </span>
          </div>
          <input
            id="betaSlider"
            type="range"
            min="0.01"
            max="0.5"
            step="0.01"
            value={beta}
            onChange={(e) => onBetaChange(parseFloat(e.target.value))}
            className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
          />
        </div>
        
        <div className="text-xs text-gray-400 mt-1 bg-gray-750 p-2 rounded">
          <p>Higher α emphasizes more leisure time in the schedule.</p>
          <p>Higher β increases the penalty for high-stress tasks.</p>
        </div>
      </div>
    </div>
  );
};

export default TradeoffSlider;