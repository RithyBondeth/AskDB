import { CalendarRange, ChartColumn, Crown, Globe, Trophy, Users } from "lucide-react";

export const EXAMPLES = [
  { icon: Crown, text: "Which artist has the most albums?" },
  { icon: Globe, text: "Total revenue by country, top 10" },
  { icon: CalendarRange, text: "Revenue per month in 2013" },
  { icon: Trophy, text: "Who are the top 5 customers by total spend?" },
  { icon: ChartColumn, text: "How many tracks are in each genre?" },
  { icon: Users, text: "What was our revenue last quarter?" },
];

/** Suggested follow-ups shown under an answer. */
export const FOLLOW_UPS = ["Show only the top 3", "Sort it the other way round"];
