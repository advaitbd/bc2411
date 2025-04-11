import React from "react";
import { BlockFormData, BlockedInterval } from "../types";
import { parse, isValid, format } from "date-fns";

interface BlockFormProps {
  formData: BlockFormData;
  onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  formIdPrefix: string;
}

const BlockFormFields: React.FC<BlockFormProps> = ({
  formData,
  onChange,
  formIdPrefix,
}) => (
  <>
    <div>
      <label
        htmlFor={`${formIdPrefix}BlockActivity`}
        className="block text-sm font-medium text-gray-300 mb-1"
      >
        Activity Name
      </label>
      <input
        id={`${formIdPrefix}BlockActivity`}
        name="activity"
        type="text"
        value={formData.activity}
        onChange={onChange}
        required
        className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
      />
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label
          htmlFor={`${formIdPrefix}BlockDate`}
          className="block text-sm font-medium text-gray-300 mb-1"
        >
          Date
        </label>
        <input
          id={`${formIdPrefix}BlockDate`}
          name="date"
          type="date"
          value={formData.date}
          onChange={onChange}
          required
          className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label
            htmlFor={`${formIdPrefix}BlockStartTime`}
            className="block text-sm font-medium text-gray-300 mb-1"
          >
            Start Time
          </label>
          <input
            id={`${formIdPrefix}BlockStartTime`}
            name="startTime"
            type="time"
            step="900"
            value={formData.startTime}
            onChange={onChange}
            required
            className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
        <div>
          <label
            htmlFor={`${formIdPrefix}BlockEndTime`}
            className="block text-sm font-medium text-gray-300 mb-1"
          >
            End Time
          </label>
          <input
            id={`${formIdPrefix}BlockEndTime`}
            name="endTime"
            type="time"
            step="900"
            value={formData.endTime}
            onChange={onChange}
            required
            className="w-full bg-gray-700 rounded px-3 py-2 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          />
        </div>
      </div>
    </div>
  </>
);

// Utility function to process block form data
export const processBlockData = (
  blockData: BlockFormData
): Omit<BlockedInterval, "id"> | null => {
  let modalError: string | null = null;

  const startDT = parse(
    `${blockData.date} ${blockData.startTime}`,
    "yyyy-MM-dd HH:mm",
    new Date()
  );
  const endDT = parse(
    `${blockData.date} ${blockData.endTime}`,
    "yyyy-MM-dd HH:mm",
    new Date()
  );

  if (!isValid(startDT) || !isValid(endDT)) {
    modalError = "Invalid date or time format. Use YYYY-MM-DD and HH:MM.";
  } else if (endDT <= startDT) {
    modalError = "End time must be after start time.";
  }
  if (!blockData.activity.trim()) {
    modalError = "Activity name cannot be empty.";
  }

  if (modalError) {
    return null;
  }

  return {
    activity: blockData.activity.trim(),
    startTime: format(startDT, "yyyy-MM-dd'T'HH:mm:ss"),
    endTime: format(endDT, "yyyy-MM-dd'T'HH:mm:ss"),
  };
};

export default BlockFormFields;