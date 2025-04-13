import React, { useMemo } from "react";
import { Calendar as CalendarIcon, ArrowLeft, ArrowRight } from "lucide-react";
import {
  BlockedInterval,
  OptimizedSchedule,
  ScheduledTaskItem,
} from "../types";
import { parseLocalISO } from "../utils/dateUtils";
import { format, addDays, isSameDay, addWeeks } from "date-fns";
import { GRID_START_HOUR, GRID_END_HOUR } from "../utils/constants";

interface CalendarProps {
  currentWeekStart: Date;
  setCurrentWeekStart: React.Dispatch<React.SetStateAction<Date>>;
  optimizedSchedule: OptimizedSchedule;
  blockedIntervals: BlockedInterval[];
  isOptimized: boolean;
  optimizationResult: {
    totalLeisure: number | null;
    totalStress: number | null;
    status: string | null;
    message: string | null;
    warnings: string[] | null;
  };
  error: string | null;
  onEventClick: (event: ScheduledTaskItem | BlockedInterval) => void;
}

const CalendarComponent: React.FC<CalendarProps> = ({
  currentWeekStart,
  setCurrentWeekStart,
  optimizedSchedule,
  blockedIntervals,
  isOptimized,
  optimizationResult,
  error,
  onEventClick,
}) => {
  // Generate days and hours for the calendar
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(currentWeekStart, i)),
    [currentWeekStart],
  );

  const hours = useMemo(
    () =>
      Array.from(
        { length: GRID_END_HOUR - GRID_START_HOUR },
        (_, i) => GRID_START_HOUR + i,
      ),
    [],
  );

  const renderCalendarEvent = (
    startTimeStr: string,
    endTimeStr: string,
    title: string,
    type: "task" | "blocked",
    eventId: string,
    onClick: () => void,
    difficulty?: number,
  ) => {
    const start = parseLocalISO(startTimeStr);
    const end = parseLocalISO(endTimeStr);
    if (!start || !end || end <= start) {
      console.warn(`Invalid date range for event: ${title} (ID: ${eventId})`);
      return null;
    }
    const dayViewStartHour = GRID_START_HOUR;
    const dayViewEndHour = GRID_END_HOUR;
    const totalDayViewMinutes = (dayViewEndHour - dayViewStartHour) * 60;
    if (totalDayViewMinutes <= 0) return null;
    const startMinutesOffset = Math.max(
      0,
      start.getHours() * 60 + start.getMinutes() - dayViewStartHour * 60,
    );
    const endMinutesOffset = Math.min(
      totalDayViewMinutes,
      end.getHours() * 60 + end.getMinutes() - dayViewStartHour * 60,
    );
    const durationMinutesInView = endMinutesOffset - startMinutesOffset;
    if (durationMinutesInView <= 0) return null;
    const topPercent = (startMinutesOffset / totalDayViewMinutes) * 100;
    const heightPercent = (durationMinutesInView / totalDayViewMinutes) * 100;

    // Determine if this is a hard task (difficulty >= 4)
    const isHardTask = type === "task" && difficulty && difficulty >= 4;

    const bgColor =
      type === "task"
        ? isHardTask
          ? "bg-amber-600 border-amber-400" // Changed to a gentler amber/orange color for hard tasks
          : "bg-purple-600 border-purple-400"
        : "bg-gray-600 border-gray-500";

    const hoverColor =
      type === "task"
        ? isHardTask
          ? "hover:bg-amber-700" // Matching hover effect
          : "hover:bg-purple-700"
        : "hover:bg-gray-700";

    const textColor = type === "task" ? "text-white" : "text-gray-200";

    return (
      <div
        key={`${type}-${eventId}`}
        className={`absolute left-1 right-1 px-1.5 py-0.5 rounded ${bgColor} ${hoverColor} ${textColor} text-xs overflow-hidden shadow border cursor-pointer transition-colors duration-150 pointer-events-auto mb-px`}
        style={{
          top: `${topPercent}%`,
          height: `calc(${Math.max(heightPercent, 2)}% - 1px)`,
          minHeight: "16px",
          zIndex: type === "task" ? 10 : 5,
        }}
        title={`${title}\n${format(start, "HH:mm")} - ${format(end, "HH:mm")}`}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <div
          className={`font-semibold truncate ${heightPercent < 5 ? "leading-tight" : ""}`}
        >
          {title}
        </div>
        {heightPercent >= 5 && (
          <div className="text-[10px] opacity-80 truncate leading-tight">
            {format(start, "HH:mm")} - {format(end, "HH:mm")}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-gray-800 p-4 sm:p-6 rounded-xl shadow-lg overflow-hidden">
      <div className="flex flex-col sm:flex-row justify-between items-center mb-4 gap-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <CalendarIcon className="w-5 h-5 text-purple-400" /> Optimized Weekly
          Schedule
        </h2>
        <div className="flex gap-2 items-center bg-gray-700 p-1 rounded-lg">
          <button
            onClick={() => setCurrentWeekStart((w) => addWeeks(w, -1))}
            className="p-2 text-gray-300 hover:bg-gray-600 rounded-md transition-colors"
            title="Previous Week"
          >
            <ArrowLeft size={18} />
          </button>
          <span className="text-sm font-medium px-2 w-32 text-center">
            {format(currentWeekStart, "MMM dd")} -{" "}
            {format(addDays(currentWeekStart, 6), "MMM dd, yyyy")}
          </span>
          <button
            onClick={() => setCurrentWeekStart((w) => addWeeks(w, 1))}
            className="p-2 text-gray-300 hover:bg-gray-600 rounded-md transition-colors"
            title="Next Week"
          >
            <ArrowRight size={18} />
          </button>
        </div>
      </div>

      {/* Display Optimization Status/Messages */}
      {optimizationResult.status && (
        <div
          className={`mb-4 p-3 rounded-lg text-sm border ${
            [
              "Optimal",
              "Feasible",
              "Suboptimal",
              "Time Limit Reached",
            ].includes(optimizationResult.status) && isOptimized
              ? "bg-green-900 border-green-700 text-green-200"
              : ["Infeasible", "Error", "No Schedulable Tasks"].includes(
                    optimizationResult.status,
                  )
                ? "bg-red-900 border-red-700 text-red-200"
                : "bg-gray-700 border-gray-600 text-gray-300" // Default/other statuses
          }`}
        >
          <p className="flex items-center gap-1.5">
            <span className="font-semibold">Status:</span>{" "}
            {optimizationResult.status}
            {optimizationResult.totalLeisure !== null && (
              <span className="ml-auto mr-4 text-xs opacity-80">
                Leisure: {optimizationResult.totalLeisure.toFixed(0)} min
              </span>
            )}
            {optimizationResult.totalStress !== null && (
              <span className="text-xs opacity-80">
                Stress: {optimizationResult.totalStress.toFixed(1)}
              </span>
            )}
          </p>
          {optimizationResult.message && (
            <p className="mt-1 text-xs opacity-90">
              <span className="font-semibold">Message:</span>{" "}
              {optimizationResult.message}
            </p>
          )}
          {optimizationResult.warnings &&
            optimizationResult.warnings.length > 0 && (
              <div className="mt-2 pt-2 border-t border-opacity-30 border-current">
                <p className="font-semibold text-xs mb-1">Warnings:</p>
                <ul className="list-disc list-inside text-yellow-300 text-xs space-y-0.5">
                  {optimizationResult.warnings.map((warn, idx) => (
                    <li key={idx}>{warn}</li>
                  ))}
                </ul>
              </div>
            )}
        </div>
      )}

      {/* Display general error if not handled by optimization status */}
      {error && !optimizationResult.status && (
        <div className="mb-4 p-3 rounded-lg text-sm bg-red-900 border border-red-700 text-red-200">
          <p>
            <strong className="font-semibold">Error:</strong> {error}
          </p>
        </div>
      )}

      <div className="overflow-x-auto relative w-full custom-scrollbar">
        <div className="grid grid-cols-[45px_repeat(7,1fr)] min-w-[800px] w-full">
          {/* Calendar Headers and Grid Lines */}
          <div className="sticky top-0 z-30 bg-gray-800 h-14 border-b border-r border-gray-700"></div>
          {days.map((day) => (
            <div
              key={`header-${day.toISOString()}`}
              className="sticky top-0 z-30 bg-gray-800 h-14 p-2 text-center border-b border-r border-gray-700 flex flex-col justify-center items-center"
            >
              <div className="font-medium text-sm leading-tight">
                {format(day, "EEE")}
              </div>
              <div className="text-xs text-gray-400 leading-tight">
                {format(day, "d MMM")}
              </div>
            </div>
          ))}
          <div className="col-start-1 row-start-2 row-span-auto">
            {hours.map((hour) => (
              <div
                key={`time-${hour}`}
                className="h-12 pr-2 text-right text-[10px] text-gray-500 border-r border-gray-700 flex items-center justify-end"
              >{`${hour.toString().padStart(2, "0")}:00`}</div>
            ))}
          </div>
          {days.map((day, dayIndex) => (
            <div
              key={`day-col-${day.toISOString()}`}
              className="col-start-[--col-start] row-start-2 row-span-auto relative border-r border-gray-700 bg-gray-850/30"
              style={{ "--col-start": dayIndex + 2 } as React.CSSProperties}
            >
              {hours.map((_, hourIndex) => (
                <div
                  key={`line-${dayIndex}-${hourIndex}`}
                  className="h-12 border-b border-gray-700/50"
                ></div>
              ))}
              <div className="absolute inset-0 top-0 left-0 right-0 bottom-0 pointer-events-none">
                {/* Render Blocked Intervals */}
                {blockedIntervals
                  .filter((interval) => {
                    const start = parseLocalISO(interval.startTime);
                    return start && isSameDay(start, day);
                  })
                  .map((interval) =>
                    renderCalendarEvent(
                      interval.startTime,
                      interval.endTime,
                      interval.activity,
                      "blocked",
                      interval.id,
                      () => onEventClick(interval),
                      undefined,
                    ),
                  )}
                {/* Render Scheduled Tasks */}
                {isOptimized &&
                  optimizedSchedule[format(day, "yyyy-MM-dd")]?.map(
                    (scheduled) =>
                      renderCalendarEvent(
                        scheduled.startTime,
                        scheduled.endTime,
                        scheduled.name,
                        "task",
                        scheduled.id,
                        () => onEventClick(scheduled),
                        scheduled.difficulty,
                      ),
                  )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CalendarComponent;
