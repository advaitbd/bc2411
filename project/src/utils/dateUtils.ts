import { parseISO, isValid, format, differenceInMinutes } from "date-fns";

// Helper function to parse potentially naive ISO strings safely
export const parseLocalISO = (dateString: string | null | undefined): Date | null => {
  if (!dateString) return null;
  try {
    // parseISO handles strings without timezone info as local time
    // Handle potential lack of seconds
    let adjustedString = dateString;
    if (dateString.length === 16) {
      // YYYY-MM-DDTHH:MM
      adjustedString = dateString + ":00";
    } else if (dateString.length === 10) {
      // YYYY-MM-DD
      adjustedString = dateString + "T00:00:00"; // Assume start of day if only date
    }

    const parsed = parseISO(adjustedString);
    return isValid(parsed) ? parsed : null;
  } catch (e) {
    console.error("Error parsing date string:", dateString, e);
    return null;
  }
};

// Helper to get deadline display string
export const getDeadlineDisplay = (deadline: string | number): string => {
  if (typeof deadline === "number") {
    return `In ${deadline} day(s)`;
  }
  const dt = parseLocalISO(deadline);
  if (dt) {
    const now = new Date();
    const diffDays = differenceInMinutes(dt, now) / (60 * 24);
    if (diffDays < 0) return `Overdue (${format(dt, "MMM d, HH:mm")})`;
    if (diffDays < 1) return `Today ${format(dt, "HH:mm")}`;
    if (diffDays < 2) return `Tomorrow ${format(dt, "HH:mm")}`;
    if (diffDays < 7) return `${format(dt, "EEE, HH:mm")}`;
    return format(dt, "MMM dd, yyyy HH:mm");
  }
  return "Invalid Date";
};