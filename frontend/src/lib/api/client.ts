import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type User = components["schemas"]["UserOut"];

/** Typed API client. Types come from `make gen-types` (backend OpenAPI). */
export const api = createClient<paths>({
  baseUrl: "/api",
  credentials: "include",
});

/** Backend errors are `{detail: "<code>"}`; validation errors are `{detail: [...]}`. */
export function errorCode(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const { detail } = error as { detail: unknown };
    if (typeof detail === "string") return detail;
    return "validation_error";
  }
  return "unknown_error";
}
