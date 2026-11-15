import { createHash } from "node:crypto";

const BLOCK = 512;

export interface TarEntry {
  path: string;
  data: Buffer;
  mode: number;
}

function octalField(value: number, width: number): Buffer {
  const body = value.toString(8).padStart(width - 1, "0");
  return Buffer.from(body + "\0", "ascii");
}

function splitName(name: string): { name: string; prefix: string } {
  if (name.length <= 100) return { name, prefix: "" };
  for (let i = name.length - 1; i >= 0; i--) {
    if (name[i] !== "/") continue;
    const prefix = name.slice(0, i);
    const base = name.slice(i + 1);
    if (base.length <= 100 && prefix.length <= 155 && base.length > 0) {
      return { name: base, prefix };
    }
  }
  throw new Error(`path too long for ustar: ${name}`);
}

function headerFor(entry: TarEntry): Buffer {
  const header = Buffer.alloc(BLOCK);
  const split = splitName(entry.path);
  header.write(split.name, 0, 100, "utf8");
  octalField(entry.mode & 0o7777, 8).copy(header, 100);
  octalField(0, 8).copy(header, 108);
  octalField(0, 8).copy(header, 116);
  octalField(entry.data.length, 12).copy(header, 124);
  octalField(0, 12).copy(header, 136);
  header.write("        ", 148, 8, "ascii");
  header.write("0", 156, 1, "ascii");
  header.write("ustar\0", 257, 6, "ascii");
  header.write("00", 263, 2, "ascii");
  if (split.prefix) header.write(split.prefix, 345, 155, "utf8");
  let sum = 0;
  for (const byte of header) sum += byte;
  const checksum = Buffer.from(sum.toString(8).padStart(6, "0") + "\0 ", "ascii");
  checksum.copy(header, 148);
  return header;
}

function padToBlock(size: number): number {
  const rem = size % BLOCK;
  return rem === 0 ? 0 : BLOCK - rem;
}

export function packUstar(entries: TarEntry[]): Buffer {
  const parts: Buffer[] = [];
  for (const entry of entries) {
    parts.push(headerFor(entry));
    parts.push(entry.data);
    const pad = padToBlock(entry.data.length);
    if (pad) parts.push(Buffer.alloc(pad));
  }
  parts.push(Buffer.alloc(BLOCK * 2));
  return Buffer.concat(parts);
}

function readOctal(buf: Buffer, start: number, width: number): number {
  const raw = buf.subarray(start, start + width).toString("ascii").replace(/\0/g, " ").trim();
  if (!raw) return 0;
  return Number.parseInt(raw, 8);
}

function cString(buf: Buffer, start: number, width: number): string {
  const slice = buf.subarray(start, start + width);
  const end = slice.indexOf(0);
  return slice.subarray(0, end === -1 ? width : end).toString("utf8").replace(/\0+$/, "");
}

export function unpackUstar(archive: Buffer): TarEntry[] {
  const entries: TarEntry[] = [];
  let offset = 0;
  while (offset + BLOCK <= archive.length) {
    const header = archive.subarray(offset, offset + BLOCK);
    if (header.every((b) => b === 0)) break;
    offset += BLOCK;
    const name = cString(header, 0, 100);
    const prefix = cString(header, 345, 155);
    const path = prefix ? `${prefix}/${name}` : name;
    const size = readOctal(header, 124, 12);
    const mode = readOctal(header, 100, 8) || 0o644;
    const type = header[156] === 0 ? 0 : header[156];
    const data = Buffer.from(archive.subarray(offset, offset + size));
    offset += size + padToBlock(size);
    if (type === 0 || type === 48) {
      entries.push({ path, data, mode });
    }
  }
  return entries;
}

export function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}
