import React from "react";
import { X } from "lucide-react";
import { ScheduledTaskItem, BlockedInterval } from "../types";
import { parseLocalISO } from "../utils/dateUtils";
import { format } from "date-fns";

interface EventDetailsModalProps {
  showModal: boolean;
  selectedEvent: ScheduledTaskItem | BlockedInterval | null;
  onClose: () => void;
}

const EventDetailsModal: React.FC<EventDetailsModalProps> = ({
  showModal,
  selectedEvent,
  onClose,
}) => {
  if (!showModal || !selectedEvent) return null;
  
  const isTask = "priority" in selectedEvent;
  const title = isTask ? selectedEvent.name : selectedEvent.activity;
  const startTime = parseLocalISO(selectedEvent.startTime);
  const endTime = parseLocalISO(
    (selectedEvent as ScheduledTaskItem).endTime ||
      (selectedEvent as BlockedInterval).endTime
  );

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-gray-800 p-6 rounded-xl w-full max-w-md shadow-2xl border border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-semibold">
            {isTask ? "Task Details" : "Blocked Time Details"}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 rounded-full hover:bg-gray-700 transition-colors"
          >
            <X size={20} />
          </button>
        </div>
        <div className="space-y-2 text-sm">
          <p>
            <strong className="font-medium text-gray-300 w-24 inline-block">
              {isTask ? "Task:" : "Activity:"}
            </strong>{" "}
            {title}
          </p>
          <p>
            <strong className="font-medium text-gray-300 w-24 inline-block">
              Start Time:
            </strong>{" "}
            {startTime ? format(startTime, "EEE, MMM dd HH:mm") : "N/A"}
          </p>
          <p>
            <strong className="font-medium text-gray-300 w-24 inline-block">
              End Time:
            </strong>{" "}
            {endTime ? format(endTime, "HH:mm") : "N/A"}
          </p>
          {isTask && (
            <>
              <p>
                <strong className="font-medium text-gray-300 w-24 inline-block">
                  Duration:
                </strong>{" "}
                {(selectedEvent as ScheduledTaskItem).duration_min} min
              </p>
              <p>
                <strong className="font-medium text-gray-300 w-24 inline-block">
                  Priority:
                </strong>{" "}
                {selectedEvent.priority}
              </p>
              <p>
                <strong className="font-medium text-gray-300 w-24 inline-block">
                  Difficulty:
                </strong>{" "}
                {selectedEvent.difficulty}
              </p>
              <p>
                <strong className="font-medium text-gray-300 w-24 inline-block">
                  Preference:
                </strong>{" "}
                <span className="capitalize">{selectedEvent.preference}</span>
              </p>
            </>
          )}
        </div>
        <button
          onClick={onClose}
          className="mt-6 w-full bg-gray-600 hover:bg-gray-500 py-2 px-4 rounded-lg transition-colors font-medium"
        >
          Close
        </button>
      </div>
    </div>
  );
};

export default EventDetailsModal;