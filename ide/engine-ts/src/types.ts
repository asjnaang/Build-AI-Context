export class EngineCanceled extends Error {
  constructor() {
    super("canceled");
    this.name = "EngineCanceled";
  }
}

export interface ScanOptions {
  includeSecretFiles: boolean;
  isCanceled?: () => boolean;
}

export interface SourceFile {
  relPath: string;
  absPath: string;
  category: string;
  lineCount: number;
  sizeBytes: number;
  sha256: string;
  lines: string[];
}

export interface Catalog {
  workspace: string;
  files: SourceFile[];
  skipped: Record<string, number>;
}

export interface Filters {
  categories: string[];
  /** When true, an empty categories list means no files (explicit opt-out). */
  categoriesConstrained?: boolean;
  paths: string[];
  nameFilters: string[];
  keywords: string[];
}

export interface SelectionMetadata {
  selectionMode: string;
  selectedCategories: string[];
  selectedPaths: string[];
  nameFilters: string[];
  missingPaths: string[];
}

export interface Selection {
  files: SourceFile[];
  metadata: SelectionMetadata;
}

export interface ExportOptions {
  outputDir?: string;
  maxFileLines: number;
  redact: boolean;
  projectOverview: boolean;
  writeGraph?: "txt" | "json";
  updateGitignore: boolean;
  includeSecretFiles?: boolean;
  isCanceled?: () => boolean;
}

export interface ExportResult {
  outputDir: string;
  manifestPath: string;
  bundlePaths: string[];
  filetreeEmbedded: true;
  graphPath?: string;
  overviewPath?: string;
  promptPath: string;
  filesExported: number;
  bundlesCreated: number;
  warnings: Array<Record<string, unknown>>;
  skippedDuringPack: Array<Record<string, unknown>>;
}

export interface FileChunk {
  relPath: string;
  category: string;
  chunkIndex: number;
  chunkCount: number;
  startLine: number;
  endLine: number;
  totalFileLines: number;
  lines: string[];
}

export interface EnginePolicy {
  bundleMaxLines: number;
  largeFileWarnLines: number;
  largeFileSkipLines: number;
  textEncoding: string;
  defaultOutputDir: string;
  categoryExtensions: Record<string, string[]>;
  categoryAliases: Record<string, string>;
  categoryDescriptions: Record<string, string>;
  specialFilenames: string[];
  defaultExcludedDirs: string[];
  defaultExcludedPrefixes: string[];
  extraExcludedPatterns: string[];
  defaultSecretPatterns: string[];
  redactionMark: string;
}
