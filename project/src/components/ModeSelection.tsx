import React from "react";
import { Loader2, Plus, Wand2 } from "lucide-react";

interface ModeSelectionProps {
  onAutoGenerate: () => void;
  onManualMode: () => void;
  isLoading: boolean;
  mode: "auto" | "manual" | null;
}

const ModeSelection: React.FC<ModeSelectionProps> = ({
  onAutoGenerate,
  onManualMode,
  isLoading,
  mode,
}) => {
  return (
    <div className="bg-gray-800 p-6 rounded-xl mb-6 shadow-lg text-center">
      <h2 className="text-xl font-semibold mb-6">
        How would you like to start?
      </h2>
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <button
          onClick={onAutoGenerate}
          disabled={isLoading}
          className="flex-1 max-w-xs bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:text-gray-400 disabled:cursor-not-allowed py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors duration-150 text-base font-medium"
        >
          {isLoading && mode === null ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Wand2 className="w-5 h-5" />
          )}{" "}
          Auto-generate Sample
        </button>
        <button
          onClick={onManualMode}
          disabled={isLoading}
          className="flex-1 max-w-xs bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-400 disabled:cursor-not-allowed py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors duration-150 text-base font-medium"
        >
          <Plus className="w-5 h-5" /> Start Manually
        </button>
      </div>
    </div>
  );
};

export default ModeSelection;