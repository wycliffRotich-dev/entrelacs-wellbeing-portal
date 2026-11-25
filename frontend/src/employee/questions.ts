export const QUESTIONS = [
  { key: "connectedness", label: "How connected do you feel to the people around you?" },
  { key: "support", label: "How supported do you feel at work?" },
  { key: "workload", label: "How manageable does your workload feel?" },
] as const;

export type QuestionKey = (typeof QUESTIONS)[number]["key"];
export type Answers = Record<QuestionKey, number | null>;

export const SCALE: number[] = Array.from({ length: 11 }, (_, i) => i);
