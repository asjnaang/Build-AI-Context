import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, posix as pathPosix } from "node:path";
import { gunzipSync, gzipSync } from "node:zlib";
import { packUstar, sha256, unpackUstar, type TarEntry } from "./tar.ts";

export const SPLIT_PAYLOAD_MAX_BYTES = 19_900_000;
const GZIP_LEVEL = 1;

export class RestoreError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RestoreError";
  }
}

export interface GzipSource {
  relPath: string;
  category: string;
  sizeBytes: number;
  sha256: string;
  data: Buffer;
  mode: number;
  encoding: "text" | "binary";
}

export interface PayloadRecord {
  part: number;
  part_count: number;
  payload: string;
  payload_size_bytes: number;
  payload_sha256: string;
  base64_body_size_bytes: number;
  base64_body_sha256: string;
  archive_name: string;
  archive_size_bytes: number;
  archive_sha256: string;
  entries: string[];
}

export interface ReassemblyRecord {
  path: string;
  size_bytes: number;
  sha256: string;
  mode: number;
  members: string[];
}

function wrapBase64(body: Buffer): Buffer {
  const chunks: Buffer[] = [];
  for (let i = 0; i < body.length; i += 76) {
    if (chunks.length) chunks.push(Buffer.from("\n"));
    chunks.push(body.subarray(i, i + 76));
  }
  return Buffer.concat(chunks);
}

export function gzipArchive(tarBytes: Buffer): Buffer {
  return gzipSync(tarBytes, { level: GZIP_LEVEL });
}

export function encodePayload(archiveName: string, archiveBytes: Buffer): { payload: Buffer; body: Buffer } {
  const body = Buffer.from(archiveBytes.toString("base64"), "ascii");
  const wrapped = wrapBase64(body);
  const header = Buffer.from(
    "BAIC-ENCODED-CONTEXT-V1\n" +
      `archive-name: ${archiveName}\n` +
      "content-format: tar+gzip\n" +
      "transport-encoding: base64\n" +
      `archive-size-bytes: ${archiveBytes.length}\n` +
      `archive-sha256: ${sha256(archiveBytes)}\n` +
      `base64-body-size-bytes: ${body.length}\n` +
      `base64-body-sha256: ${sha256(body)}\n\n`,
    "ascii",
  );
  return { payload: Buffer.concat([header, wrapped, Buffer.from("\n")]), body };
}

export function packSources(sources: GzipSource[]): Buffer {
  const entries: TarEntry[] = sources
    .slice()
    .sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0))
    .map((source) => ({ path: source.relPath, data: source.data, mode: source.mode }));
  return gzipArchive(packUstar(entries));
}

function payloadSizeFor(sources: GzipSource[]): number {
  return encodePayload("probe.tar.gz", packSources(sources)).payload.length;
}

function partSource(source: GzipSource, partData: Buffer, memberPath: string): GzipSource {
  return {
    relPath: memberPath,
    category: source.category,
    sizeBytes: partData.length,
    sha256: sha256(partData),
    data: partData,
    mode: source.mode,
    encoding: "binary",
  };
}

export function splitOversizedFiles(
  sources: GzipSource[],
  limit = SPLIT_PAYLOAD_MAX_BYTES,
): { physical: GzipSource[]; reassembly: ReassemblyRecord[] } {
  const physical: GzipSource[] = [];
  const reassembly: ReassemblyRecord[] = [];
  const framingReserve = Math.min(128 * 1024, Math.floor(limit / 8));
  const maxMember = Math.max(1, Math.floor((limit * 3) / 8) - framingReserve);
  for (const source of sources) {
    if (source.data.length <= maxMember && payloadSizeFor([source]) <= limit) {
      physical.push(source);
      continue;
    }
    const partCount = Math.ceil(source.data.length / maxMember);
    const fileKey = sha256(Buffer.from(source.relPath, "utf8")).slice(0, 16);
    const members: string[] = [];
    for (let i = 0; i < partCount; i++) {
      const start = i * maxMember;
      const partData = source.data.subarray(start, start + maxMember);
      const memberPath = `.baic-file-parts/${fileKey}/${String(i + 1).padStart(6, "0")}-of-${String(partCount).padStart(6, "0")}.part`;
      members.push(memberPath);
      physical.push(partSource(source, partData, memberPath));
    }
    reassembly.push({
      path: source.relPath,
      size_bytes: source.sizeBytes,
      sha256: source.sha256,
      mode: source.mode,
      members,
    });
  }
  return { physical, reassembly };
}

export function groupSourcesForSplit(sources: GzipSource[], limit = SPLIT_PAYLOAD_MAX_BYTES): GzipSource[][] {
  if (!sources.length) return [[]];
  const ordered = sources.slice().sort((a, b) => (a.relPath < b.relPath ? -1 : a.relPath > b.relPath ? 1 : 0));
  const groups: GzipSource[][] = [];
  let current: GzipSource[] = [];
  for (const source of ordered) {
    const trial = [...current, source];
    if (current.length && payloadSizeFor(trial) > limit) {
      groups.push(current);
      current = [source];
    } else {
      current = trial;
    }
  }
  if (current.length) groups.push(current);
  return groups;
}

export function writeGzipExport(options: {
  outputDir: string;
  folderName: string;
  timestamp: string;
  sources: GzipSource[];
  split: boolean;
}): {
  payloadPaths: string[];
  payloadRecords: PayloadRecord[];
  archiveEntries: Record<string, unknown>[];
  reassembly: ReassemblyRecord[];
  logicalPaths: string[];
} {
  const logicalPaths = options.sources.map((s) => s.relPath);
  const splitPrep = options.split
    ? splitOversizedFiles(options.sources)
    : { physical: options.sources, reassembly: [] as ReassemblyRecord[] };
  const groups = options.split ? groupSourcesForSplit(splitPrep.physical) : [splitPrep.physical];
  const partCount = Math.max(groups.length, 1);
  const payloadRecords: PayloadRecord[] = [];
  const payloadPaths: string[] = [];
  const entryPart = new Map<string, number>();
  groups.forEach((group, index0) => {
    const part = index0 + 1;
    const suffix = options.split ? `_part_${String(part).padStart(3, "0")}_of_${String(partCount).padStart(3, "0")}` : "";
    const archiveName = `${options.folderName}_context${suffix}_${options.timestamp}.tar.gz`;
    const payloadName = `${options.folderName}_payload${suffix}_${options.timestamp}.txt`;
    const archiveBytes = packSources(group);
    const encoded = encodePayload(archiveName, archiveBytes);
    if (options.split && encoded.payload.length > SPLIT_PAYLOAD_MAX_BYTES) {
      throw new Error(`Generated payload exceeds split limit: ${payloadName}`);
    }
    const payloadPath = join(options.outputDir, payloadName);
    writeFileSync(payloadPath, encoded.payload);
    payloadPaths.push(payloadPath);
    const paths = group.map((s) => s.relPath);
    for (const path of paths) entryPart.set(path, part);
    payloadRecords.push({
      part,
      part_count: partCount,
      payload: payloadName,
      payload_size_bytes: encoded.payload.length,
      payload_sha256: sha256(encoded.payload),
      base64_body_size_bytes: encoded.body.length,
      base64_body_sha256: sha256(encoded.body),
      archive_name: archiveName,
      archive_size_bytes: archiveBytes.length,
      archive_sha256: sha256(archiveBytes),
      entries: paths,
    });
  });
  const archiveEntries = splitPrep.physical.map((source) => ({
    path: source.relPath,
    category: source.category,
    content_kind: source.encoding === "text" ? "text" : "binary",
    source_format: source.relPath.toLowerCase().endsWith(".gz") ? "gzip" : null,
    transport_encoding: "identity",
    size_bytes: source.sizeBytes,
    sha256: source.sha256,
    mode: source.mode,
    payload_part: entryPart.get(source.relPath) ?? 1,
  }));
  return {
    payloadPaths,
    payloadRecords,
    archiveEntries,
    reassembly: splitPrep.reassembly,
    logicalPaths,
  };
}

function digest(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}

function safePath(name: string): string {
  if (
    !name ||
    name.includes("\\") ||
    name.startsWith("/") ||
    name.split("/").some((part) => part === "" || part === "." || part === "..")
  ) {
    throw new RestoreError(`Unsafe archive path: ${JSON.stringify(name)}`);
  }
  return name;
}

function manifestFor(source: string): string {
  const st = statSync(source);
  if (st.isFile()) {
    if (!source.toLowerCase().endsWith(".json")) {
      throw new RestoreError(`Restore source must be a manifest JSON file or export directory: ${source}`);
    }
    return source;
  }
  const names = readdirSync(source)
    .filter((n) => n.includes("_manifest_") && n.endsWith(".json"))
    .sort();
  const fallback = names.length
    ? names
    : readdirSync(source)
        .filter((n) => n.includes("manifest") && n.endsWith(".json"))
        .sort();
  if (fallback.length !== 1) {
    throw new RestoreError(
      `Expected exactly one manifest in ${source}; found ${fallback.length}. Pass the exact manifest path when a directory contains multiple manifests.`,
    );
  }
  return join(source, fallback[0]);
}

function payloadRecords(transport: Record<string, unknown>): PayloadRecord[] {
  const raw = (transport.payloads as PayloadRecord[] | undefined) ?? [transport as unknown as PayloadRecord];
  const records = raw.slice().sort((a, b) => Number(a.part ?? 1) - Number(b.part ?? 1));
  const parts = records.map((item) => Number(item.part ?? 1));
  if (parts.join(",") !== records.map((_, i) => i + 1).join(",")) {
    throw new RestoreError("Manifest has missing, duplicate, or reordered payload parts");
  }
  return records;
}

function decodePayload(
  manifestPath: string,
  record: PayloadRecord,
  expected: Record<string, { size_bytes: number; sha256: string }>,
): Record<string, Buffer> {
  const payloadPath = join(dirname(manifestPath), record.payload);
  let payloadBytes: Buffer;
  try {
    payloadBytes = readFileSync(payloadPath);
  } catch {
    throw new RestoreError(`Missing payload: ${payloadPath}`);
  }
  if (payloadBytes.length !== Number(record.payload_size_bytes) || digest(payloadBytes) !== record.payload_sha256) {
    throw new RestoreError(`Payload size or SHA-256 mismatch: ${record.payload}`);
  }
  const splitAt = payloadBytes.indexOf(Buffer.from("\n\n"));
  if (splitAt < 0) throw new RestoreError(`Invalid payload header: ${record.payload}`);
  const header = payloadBytes.subarray(0, splitAt);
  const body = payloadBytes.subarray(splitAt + 2);
  if (!header.toString("ascii").startsWith("BAIC-ENCODED-CONTEXT-V1\n")) {
    throw new RestoreError(`Invalid payload header: ${record.payload}`);
  }
  const encoded = Buffer.from(body.toString("ascii").replace(/\s+/g, ""), "ascii");
  if (encoded.length !== Number(record.base64_body_size_bytes) || digest(encoded) !== record.base64_body_sha256) {
    throw new RestoreError(`Base64 body size or SHA-256 mismatch: ${record.payload}`);
  }
  const archiveBytes = Buffer.from(encoded.toString("ascii"), "base64");
  if (archiveBytes.length !== Number(record.archive_size_bytes) || digest(archiveBytes) !== record.archive_sha256) {
    throw new RestoreError(`Decoded archive size or SHA-256 mismatch: ${record.payload}`);
  }
  let tarBytes: Buffer;
  try {
    tarBytes = gunzipSync(archiveBytes);
  } catch {
    throw new RestoreError(`Invalid tar+gzip archive: ${record.payload}`);
  }
  const files: Record<string, Buffer> = {};
  for (const member of unpackUstar(tarBytes)) {
    const name = safePath(member.path);
    const meta = expected[name];
    if (name in files || !meta) throw new RestoreError(`Unexpected or unsafe archive member: ${name}`);
    if (member.data.length !== Number(meta.size_bytes) || digest(member.data) !== meta.sha256) {
      throw new RestoreError(`Archive entry size or SHA-256 mismatch: ${name}`);
    }
    files[name] = member.data;
  }
  const recordEntries = new Set(record.entries.map(String));
  if (Object.keys(files).length !== recordEntries.size || Object.keys(files).some((n) => !recordEntries.has(n))) {
    throw new RestoreError(`Payload path-set mismatch: ${record.payload}`);
  }
  return files;
}

export function restoreExport(
  source: string,
  output?: string,
  force = false,
): { destination: string; restoredCount: number } {
  const manifestPath = manifestFor(source);
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as Record<string, unknown>;
  const transport = (manifest.transport ?? {}) as Record<string, unknown>;
  if (transport.format !== "tar+gzip+base64") {
    throw new RestoreError("Only tar+gzip+base64 exports can be restored byte-for-byte");
  }
  const archiveEntries = (manifest.archive_entries as Array<Record<string, unknown>>) ?? [];
  const expected: Record<string, { size_bytes: number; sha256: string; mode: number }> = {};
  for (const entry of archiveEntries) {
    const name = safePath(String(entry.path));
    if (name in expected) throw new RestoreError("Manifest has no archive entries or contains duplicate paths");
    expected[name] = {
      size_bytes: Number(entry.size_bytes),
      sha256: String(entry.sha256),
      mode: Number(entry.mode ?? 0o644),
    };
  }
  if (!Object.keys(expected).length) {
    throw new RestoreError("Manifest has no archive entries or contains duplicate paths");
  }
  const physical: Record<string, Buffer> = {};
  for (const record of payloadRecords(transport)) {
    const partFiles = decodePayload(manifestPath, record, expected);
    for (const name of Object.keys(partFiles)) {
      if (name in physical) throw new RestoreError(`Archive members appear in multiple payloads: ${name}`);
      physical[name] = partFiles[name];
    }
  }
  if (Object.keys(physical).length !== Object.keys(expected).length) {
    const missing = Object.keys(expected).filter((n) => !(n in physical)).sort();
    throw new RestoreError(`Archive path-set mismatch; missing: ${missing.join(", ")}`);
  }
  const consumed = new Set<string>();
  const restored: Record<string, Buffer> = {};
  const modes: Record<string, number> = {};
  for (const [name, entry] of Object.entries(expected)) modes[name] = entry.mode;
  for (const record of (transport.reassembly as ReassemblyRecord[] | undefined) ?? []) {
    const name = safePath(String(record.path));
    const members = record.members.map((m) => safePath(String(m)));
    if (!members.length || name in restored || members.some((m) => consumed.has(m) || !(m in physical))) {
      throw new RestoreError(`Invalid reassembly record: ${name}`);
    }
    const data = Buffer.concat(members.map((m) => physical[m]));
    if (data.length !== Number(record.size_bytes) || digest(data) !== String(record.sha256)) {
      throw new RestoreError(`Reassembled file size or SHA-256 mismatch: ${name}`);
    }
    restored[name] = data;
    modes[name] = Number(record.mode ?? 0o644);
    for (const m of members) consumed.add(m);
  }
  for (const [name, data] of Object.entries(physical)) {
    if (!consumed.has(name)) restored[name] = data;
  }
  let destination: string;
  if (!output) {
    const projectName = String(manifest.project_root || "")
      .split(/[/\\]/)
      .filter(Boolean)
      .pop();
    if (!projectName || projectName === "." || projectName === "..") {
      throw new RestoreError("Manifest project_root has no usable project name; pass --restore-output");
    }
    destination = join(process.cwd(), projectName);
  } else {
    destination = output;
  }
  const sourceDirectory = dirname(manifestPath);
  if (join(sourceDirectory) === join(destination)) {
    throw new RestoreError(
      "Restore output cannot be the export source directory; omit --restore-output to use the PROJECT_NAME default or choose another directory",
    );
  }
  if (existsSync(destination)) {
    const occupied = statSync(destination).isDirectory() ? readdirSync(destination).length > 0 : true;
    if (!force && occupied) throw new RestoreError(`Output is not empty; use --restore-force: ${destination}`);
    rmSync(destination, { recursive: true, force: true });
  }
  const stage = join(dirname(destination), `.${pathPosix.basename(destination)}.restore-${process.pid}-${Date.now()}`);
  mkdirSync(stage, { recursive: true });
  try {
    for (const [name, data] of Object.entries(restored)) {
      const target = join(stage, ...safePath(name).split("/"));
      mkdirSync(dirname(target), { recursive: true });
      writeFileSync(target, data);
    }
    mkdirSync(dirname(destination), { recursive: true });
    renameSync(stage, destination);
  } finally {
    if (existsSync(stage)) rmSync(stage, { recursive: true, force: true });
  }
  return { destination, restoredCount: Object.keys(restored).length };
}
