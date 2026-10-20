import type { components } from "@/lib/api/schema";

export type Profile = components["schemas"]["ProfileOut"];
export type Fact = components["schemas"]["FactOut"];
export type Question = components["schemas"]["QuestionOut"];
export type CvDocument = components["schemas"]["DocumentOut"];
export type FactValue = Record<string, string | string[] | null>;

/** Editable fields per fact type, in display order. Arrays are edited one item per line. */
export const FIELDS: Record<string, string[]> = {
  personal: ["full_name"],
  location: ["city", "postcode", "country"],
  profession: ["name"],
  desired_role: ["name"],
  experience: ["title", "employer", "location", "start", "end", "details"],
  education: [
    "qualification",
    "institution",
    "location",
    "start",
    "end",
    "details",
  ],
  skill: ["name"],
  language: ["language", "cefr", "level_text"],
  certificate: ["name", "issuer", "date"],
  driving_license: ["class"],
  answer: ["text"],
  other: ["text"],
};

export const LIST_FIELDS = new Set(["details"]);
export const CEFR = ["A1", "A2", "B1", "B2", "C1", "C2", "native"];

export function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function list(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}
