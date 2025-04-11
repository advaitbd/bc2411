import React, { useState } from "react";
import { X, UploadCloud } from "lucide-react";

interface ImportScheduleModalProps {
  onClose: () => void;
  onImport: (scheduleText: string) => void;
  importErrors: string[];
}

const ImportScheduleModal: React.FC<ImportScheduleModalProps> = ({
  onClose,
  onImport,
  importErrors,
}) => {
  const [scheduleText, setScheduleText] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (scheduleText.trim()) {
      onImport(scheduleText);
      // Keep modal open if there are errors, otherwise it will be closed by parent
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-2xl shadow-2xl border border-gray-700 max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-center mb-4 flex-shrink-0">
          <h3 className="text-xl font-semibold flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-purple-400" /> Import NTU
            Schedule
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-full hover:bg-gray-700"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        <p className="text-sm text-gray-400 mb-4 flex-shrink-0">
          Paste your schedule text directly from the NTU registration system
          (STARS). The parser will attempt to extract class timings and add them
          as blocked intervals for the currently viewed week.
        </p>
        <form
          onSubmit={handleSubmit}
          className="flex flex-col flex-grow min-h-0"
        >
          <textarea
            value={scheduleText}
            onChange={(e) => setScheduleText(e.target.value)}
            placeholder="Paste your schedule here..."
            className="w-full flex-grow bg-gray-900 rounded p-3 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm font-mono resize-none custom-scrollbar min-h-[200px]"
            rows={15}
          />
          {importErrors.length > 0 && (
            <div className="mt-4 p-3 rounded-lg bg-red-900 border border-red-700 text-red-200 text-xs max-h-24 overflow-y-auto custom-scrollbar flex-shrink-0">
              <p className="font-semibold mb-1">Parsing Errors:</p>
              <ul className="list-disc list-inside">
                {importErrors.map((err, idx) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            </div>
          )}
          <button
            type="submit"
            disabled={!scheduleText.trim()}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed py-2.5 rounded-lg mt-4 transition-colors font-semibold text-base flex-shrink-0"
          >
            Import Schedule
          </button>
        </form>
      </div>
    </div>
  );
};

export default ImportScheduleModal;
