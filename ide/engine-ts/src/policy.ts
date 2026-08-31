import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { EnginePolicy } from "./types.ts";

const here = dirname(fileURLToPath(import.meta.url));
const policyPath = join(here, "..", "..", "policy", "policy.json");

let cached: EnginePolicy | undefined;

export function loadPolicy(): EnginePolicy {
  if (!cached) {
    cached = JSON.parse(readFileSync(policyPath, "utf-8")) as EnginePolicy;
  }
  return cached;
}
