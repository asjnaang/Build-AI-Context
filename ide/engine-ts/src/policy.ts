import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { EnginePolicy } from "./types.ts";

// The VS Code host supplies its packaged policy with setPolicyPath(). The
// working-directory fallback is for direct engine use and tests.
const defaultPolicyPath = join(process.cwd(), "..", "policy", "policy.json");

let policyPath = defaultPolicyPath;
let cached: EnginePolicy | undefined;

export function setPolicyPath(path: string): void {
  policyPath = path;
  cached = undefined;
}

export function loadPolicy(): EnginePolicy {
  if (!cached) {
    cached = JSON.parse(readFileSync(policyPath, "utf-8")) as EnginePolicy;
  }
  return cached;
}
