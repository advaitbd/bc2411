import React from "react";
import { HelpCircle } from "lucide-react";

interface ModelToggleProps {
  modelType: "deadline_penalty" | "no_y";
  onChange: (modelType: "deadline_penalty" | "no_y") => void;
  onExplanationClick: () => void;
}

const ModelToggle: React.FC<ModelToggleProps> = ({
  modelType,
  onChange,
  onExplanationClick,
}) => {
  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-300">Model Type</span>
        <button
          onClick={onExplanationClick}
          className="text-gray-400 hover:text-purple-300 p-1 rounded-full hover:bg-gray-700"
          title="Learn about the different models"
        >
          <HelpCircle size={16} />
        </button>
      </div>
      <div className="bg-gray-700 p-1 rounded-lg flex">
        <button
          onClick={() => onChange("deadline_penalty")}
          className={`flex-1 py-2 px-3 rounded-md text-sm transition-colors ${
            modelType === "deadline_penalty"
              ? "bg-purple-600 text-white"
              : "text-gray-300 hover:bg-gray-600"
          }`}
        >
          Deadline Penalty
        </button>
        <button
          onClick={() => onChange("no_y")}
          className={`flex-1 py-2 px-3 rounded-md text-sm transition-colors ${
            modelType === "no_y"
              ? "bg-purple-600 text-white"
              : "text-gray-300 hover:bg-gray-600"
          }`}
        >
          Basic Model
        </button>
      </div>
      <p className="text-xs text-gray-400 mt-1">
        {modelType === "deadline_penalty"
          ? "Penalizes scheduling tasks close to deadlines"
          : "Standard model without deadline penalties"}
      </p>
    </div>
  );
};

export default ModelToggle;
