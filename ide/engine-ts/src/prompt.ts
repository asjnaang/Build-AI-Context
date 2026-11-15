import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";

export type Transport = "tar-gz" | "text";

const TASK_PLACEHOLDER = "[PASTE THE SPECIFIC FEATURE / BUGFIX / REFACTOR REQUEST HERE]";
const OUTPUT_NAME = "baic_prompt.md";

let promptDirOverride: string | undefined;

export function setPromptDir(path: string): void {
  promptDirOverride = path;
}

export function promptOutputName(): string {
  return OUTPUT_NAME;
}

export function assertTransport(transport: string): Transport {
  if (transport === "tar-gz" || transport === "text") return transport;
  throw new Error("transport must be 'tar-gz' or 'text'");
}

function bundledPromptPath(transport: Transport): string {
  const name = transport === "text" ? "baic_prompt_text.md" : "baic_prompt_gzip.md";
  const candidates = [
    promptDirOverride ? join(promptDirOverride, name) : undefined,
    join(process.cwd(), name),
    join(process.cwd(), "ide", "engine-ts", name),
    join(process.cwd(), "..", "engine-ts", name),
    join(dirname(process.argv[1] ?? process.cwd()), "..", name),
  ].filter((p): p is string => Boolean(p));
  for (const candidate of candidates) {
    try {
      readFileSync(candidate);
      return candidate;
    } catch {
      /* try next */
    }
  }
  throw new Error(`Bundled prompt is missing: ${name}`);
}

export function promptContentForTransport(transport: Transport, task?: string): string {
  const content = readFileSync(bundledPromptPath(transport), "utf8");
  if (task === undefined) return content;
  return content.replace(TASK_PLACEHOLDER, task);
}
