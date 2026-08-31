export function denyUntrustedWrite(isTrusted: boolean): string | undefined {
  if (!isTrusted) return "Trust this workspace to write files.";
  return undefined;
}
