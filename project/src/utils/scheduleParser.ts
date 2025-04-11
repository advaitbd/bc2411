import { BlockedInterval } from "../types";
import {
  format,
  parse,
  addDays,
  startOfWeek,
  Day,
  addWeeks,
  isValid,
} from "date-fns"; // Added addWeeks and isValid

// Helper to map day strings to date-fns day index (0=Sun, 1=Mon, ...)
const dayMap: { [key: string]: Day } = {
  SUN: 0,
  MON: 1,
  TUE: 2,
  WED: 3,
  THU: 4,
  FRI: 5,
  SAT: 6,
};

// --- Teaching Week Parsing (Optional Enhancement - currently unused) ---
// const parseTeachingWeeks = (remark: string): number[] | null => {
//     const teachingWkMatch = remark.match(/Teaching Wk([\d,-]+)/i);
//     if (!teachingWkMatch) return Array.from({ length: 13 }, (_, i) => i + 1); // Default to 13 weeks if not specified

//     const weekRanges = teachingWkMatch[1].split(',');
//     const weeks: number[] = [];

//     weekRanges.forEach(range => {
//         if (range.includes('-')) {
//             const [start, end] = range.split('-').map(Number);
//             if (!isNaN(start) && !isNaN(end)) {
//                 for (let i = start; i <= end; i++) {
//                     weeks.push(i);
//                 }
//             }
//         } else {
//             const weekNum = parseInt(range, 10);
//             if (!isNaN(weekNum)) {
//                 weeks.push(weekNum);
//             }
//         }
//     });
//     return weeks.length > 0 ? [...new Set(weeks)].sort((a, b) => a - b) : null;
// };
// --- End Teaching Week Parsing ---

export function parseNtuSchedule(
  scheduleText: string,
  // Reference date determines the *start* of the week generation.
  // Usually, using the current date is sufficient for near-term planning.
  referenceDate: Date = new Date(),
  numberOfWeeksToGenerate: number = 14, // Generate for 13 weeks + current/buffer
): { blocks: Omit<BlockedInterval, "id">[]; errors: string[] } {
  const lines = scheduleText.split("\n").map((line) => line.trim());
  const blocks: Omit<BlockedInterval, "id">[] = [];
  const errors: string[] = [];
  let currentCourse = "";

  // Determine the start of the week containing the referenceDate
  const semesterReferenceWeekStart = startOfWeek(referenceDate, {
    weekStartsOn: 1,
  }); // Monday

  lines.forEach((line, index) => {
    const parts = line.split(/\s{2,}|\t/); // Split by multiple spaces or tabs

    // Heuristic to find course code/title lines
    // Updated Regex: Match typical NTU course code format (e.g., AB1201, BC2411)
    if (parts.length >= 2 && /^[A-Z]{2,}\d{4,}/.test(parts[0])) {
      currentCourse = `${parts[0]} ${parts[1]}`;
    }

    const dayAndTimeMatch = line.match(
      /\b(MON|TUE|WED|THU|FRI|SAT|SUN)\b\s+(\d{4})-(\d{4})\b/,
    );
    const venueMatch = line.match(/Venue:\s*(.*?)\s*Remark:/i);
    const remarkMatch = line.match(/Remark:\s*(.*)/i); // Match remark separately
    const venueText = venueMatch ? venueMatch[1].trim() : "";
    const remarkText = remarkMatch ? remarkMatch[1].trim() : "";

    if (dayAndTimeMatch) {
      // Determine activity name based on currentCourse and Venue
      // If venue is ONLINE, use "(Class)". Otherwise include venue.
      // Only try to build activity name if a course context exists
      let activityName = "Class (Unknown Course)"; // Default if no course context
      if (currentCourse) {
        const isOnline = venueText.toUpperCase().includes("ONLINE");
        // Check if remarkText *also* indicates online, e.g., if Venue column is empty but remark says ONLINE
        const remarkIsOnline = remarkText.toUpperCase().includes("ONLINE");

        if (isOnline || remarkIsOnline) {
          activityName = `${currentCourse} (Class)`;
        } else if (venueText) {
          // Clean up venue text by removing brackets
          activityName = `${currentCourse} (${venueText.replace(/\[|\]/g, "").trim()})`;
        } else {
          // If no venue text and not online, use a generic name
          activityName = `${currentCourse} (Class)`;
        }
      }

      const dayStr = dayAndTimeMatch[1];
      const startTimeStr = dayAndTimeMatch[2];
      const endTimeStr = dayAndTimeMatch[3];
      // const venueText = venueMatch ? venueMatch[1].trim() : ""; // Moved up
      // const activityName = `${currentCourse}${venueText && !venueText.toUpperCase().includes("ONLINE") ? ` (${venueText.replace(/\[|\]/g, "")})` : " (Class)"}`; // Replaced with logic above

      const dayIndex = dayMap[dayStr]; // 0 for SUN, 1 for MON...
      if (dayIndex === undefined) {
        errors.push(`Line ${index + 1}: Invalid day format "${dayStr}".`);
        return; // Use continue instead of return if you want to process other parts of the line
      }

      // --- Generate blocks for multiple weeks ---
      // const teachingWeeks = parseTeachingWeeks(remarkText); // Use this if implementing week filtering

      for (
        let weekOffset = 0;
        weekOffset < numberOfWeeksToGenerate;
        weekOffset++
      ) {
        // Calculate the specific date for this day in the target week
        const targetWeekStart = addWeeks(
          semesterReferenceWeekStart,
          weekOffset,
        );
        // Correct calculation: addDays needs the date-fns index (0=Sun, 1=Mon...)
        // If weekStartsOn: 1 (Monday), then Monday is index 0 for addDays relative to startOfWeek
        // So, dayIndex 1 (MON) maps to offset 0, 2 (TUE) maps to offset 1 etc.
        const targetDate = addDays(
          targetWeekStart,
          dayIndex - (semesterReferenceWeekStart.getDay() || 7),
        ); // Adjust dayIndex based on actual start day
        // Alternative, potentially simpler if always starting Monday: addDays(targetWeekStart, dayIndex - 1) if dayMap starts MON=1
        // Let's stick to the original calculation for now which seems correct if dayMap[MON]=1 and weekStartsOn=1
        // Check the logic: startOfWeek(date, {weekStartsOn: 1}) gives Monday.
        // dayMap[MON]=1. addDays(Monday, 1-1) = addDays(Monday, 0) -> Correct.
        // dayMap[TUE]=2. addDays(Monday, 2-1) = addDays(Monday, 1) -> Correct.
        // dayMap[SUN]=0. addDays(Monday, 0-1) = addDays(Monday, -1) -> Sunday of previous week?? This is likely wrong.
        // date-fns Day index: SUN=0, MON=1, TUE=2... SAT=6
        // startOfWeek(date, { weekStartsOn: 1 }) gives the preceding Monday.
        // We need to add the difference between the target day and Monday.
        // Target Day (date-fns index) | dayMap value | Difference from Monday (index 1)
        // MON = 1                     | 1            | 0
        // TUE = 2                     | 2            | 1
        // WED = 3                     | 3            | 2
        // THU = 4                     | 4            | 3
        // FRI = 5                     | 5            | 4
        // SAT = 6                     | 6            | 5
        // SUN = 0                     | 0            | 6 (Need Sun of *that* week, not previous)

        let dayOffset = dayIndex - 1; // Offset from Monday (0=Mon, 1=Tue, ..., 5=Sat)
        if (dayIndex === 0) {
          // Sunday
          dayOffset = 6; // Sunday is 6 days after Monday
        }
        const specificTargetDate = addDays(targetWeekStart, dayOffset);

        // Combine date with time
        const startTime = parse(
          `${format(specificTargetDate, "yyyy-MM-dd")} ${startTimeStr}`,
          "yyyy-MM-dd HHmm",
          new Date(),
        );
        const endTime = parse(
          `${format(specificTargetDate, "yyyy-MM-dd")} ${endTimeStr}`,
          "yyyy-MM-dd HHmm",
          new Date(),
        );

        if (!isValid(startTime) || !isValid(endTime) || endTime <= startTime) {
          // Only report error once per line, not per week generated
          if (weekOffset === 0) {
            errors.push(
              `Line ${index + 1}: Invalid time range ${startTimeStr}-${endTimeStr} for ${dayStr}.`,
            );
          }
          continue; // Skip this week instance if time is invalid
        }

        // TODO: Optionally filter based on parsed teachingWeeks if needed
        // if (teachingWeeks && !teachingWeeks.includes(weekOffset + 1)) {
        //    continue;
        // }

        blocks.push({
          activity: activityName || "Class", // Use the determined activityName
          startTime: format(startTime, "yyyy-MM-dd'T'HH:mm:ss"),
          endTime: format(endTime, "yyyy-MM-dd'T'HH:mm:ss"),
        });
      }
      // --- End multi-week generation ---
    }
  });

  // Deduplicate blocks (in case parsing generates overlaps)
  const uniqueBlocks = Array.from(
    new Map(blocks.map((b) => [`${b.activity}-${b.startTime}`, b])).values(),
  );

  return { blocks: uniqueBlocks, errors };
}
