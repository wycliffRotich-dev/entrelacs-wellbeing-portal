import type { Wellbeing } from "../api/types";

export const INSUFFICIENT = "Insufficient responses";
export const NO_ELIGIBLE = "No eligible employees";

/** The API withholds the average below five respondents, so a null average is never shown as 0. */
export function formatAverage(w: Wellbeing): string {
  if (w.suppressed || w.average_score === null) return INSUFFICIENT;
  return w.average_score.toFixed(1);
}

/** A zero denominator has no percentage. Whole numbers drop the trailing ".0". */
export function formatParticipation(w: Wellbeing): string {
  if (w.eligible_count === 0 || w.participation_rate === null) return NO_ELIGIBLE;
  return `${Number(w.participation_rate.toFixed(1))}%`;
}
