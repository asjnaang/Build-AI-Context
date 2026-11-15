import * as vscode from "vscode";
import { panelMarkup, type PanelSnapshot } from "./panelModel.ts";

export type PanelMessage =
  | { type: "search"; value: string }
  | { type: "format"; value: string }
  | { type: "selectAll"; checked: boolean }
  | { type: "toggleFile"; path: string; checked: boolean }
  | { type: "toggleCategory"; category: string }
  | { type: "export" }
  | { type: "restore" }
  | { type: "refresh" }
  | { type: "transport"; value: string }
  | { type: "keywords"; value: string }
  | { type: "paths"; value: string }
  | { type: "setting"; key: "forceBundle" | "forceIgnored" | "split"; checked: boolean }
  | { type: "excludePaths"; value: string }
  | { type: "extraFormats"; value: string }
  | { type: "openFolder" }
  | { type: "openManifest" }
  | { type: "openPrompt" };

export class BaicPanelView implements vscode.WebviewViewProvider {
  static readonly viewId = "baic.panel";
  private view?: vscode.WebviewView;

  constructor(
    private readonly getSnapshot: () => PanelSnapshot,
    private readonly onMessage: (message: PanelMessage) => void,
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage((message: PanelMessage) => this.onMessage(message));
    this.refresh(true);
  }

  refresh(full = false): void {
    if (!this.view) return;
    const snapshot = this.getSnapshot();
    if (full || !this.view.webview.html) {
      this.view.webview.html = renderPanelPage(this.view.webview, snapshot);
      return;
    }
    void this.view.webview.postMessage({ type: "snapshot", snapshot, markup: panelMarkup(snapshot) });
  }
}

function nonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function renderPanelPage(webview: vscode.Webview, snapshot: PanelSnapshot): string {
  const n = nonce();
  const csp = `default-src 'none'; img-src ${webview.cspSource} data:; style-src 'nonce-${n}'; script-src 'nonce-${n}';`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta http-equiv="Content-Security-Policy" content="${csp}"/>
<style nonce="${n}">
:root { color-scheme: light dark; }
html, body { margin: 0; padding: 0; height: 100%; }
body {
  font: 13px/1.4 var(--vscode-font-family);
  color: var(--vscode-foreground);
  background: var(--vscode-sideBar-background);
}
.wrap { padding: 10px 12px 16px; box-sizing: border-box; }
.meta { font-size: 12px; color: var(--vscode-descriptionForeground); margin: 8px 0; }
.hint { color: var(--vscode-descriptionForeground); font-size: 12px; }
.primary {
  width: 100%;
  background: var(--vscode-button-background);
  color: var(--vscode-button-foreground);
  border: 0;
  border-radius: 4px;
  padding: 8px 12px;
  font-weight: 650;
  cursor: pointer;
}
.primary:disabled { opacity: .55; cursor: default; }
.primary:hover:not(:disabled) { background: var(--vscode-button-hoverBackground); }
.actions { display: flex; gap: 12px; margin: 8px 0 12px; align-items: center; flex-wrap: wrap; }
.link {
  background: none; border: 0; padding: 0; color: var(--vscode-textLink-foreground);
  cursor: pointer; font: inherit;
}
.label {
  font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
  color: var(--vscode-descriptionForeground); border-top: 1px solid var(--vscode-widget-border);
  padding-top: 10px; margin: 4px 0 8px;
}
.option { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin: 6px 0; }
.option.wrap { align-items: flex-start; }
input[type="search"], input:not([type="checkbox"]), select {
  width: 100%; box-sizing: border-box;
  background: var(--vscode-input-background); color: var(--vscode-input-foreground);
  border: 1px solid var(--vscode-input-border, var(--vscode-widget-border));
  border-radius: 4px; padding: 6px 8px; font: inherit;
}
select { width: auto; min-width: 88px; }
.tree { max-height: 42vh; overflow: auto; padding-bottom: 8px; }
.file, .chip { display: flex; gap: 6px; align-items: center; white-space: nowrap; }
.file { margin: 3px 0 3px 2px; }
.dir { margin: 2px 0 2px 6px; }
.dir > summary { cursor: pointer; }
.warning { color: var(--vscode-editorWarning-foreground); }
.section { padding-top: 2px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px 10px; justify-content: flex-end; }
.field-label { display: block; margin: 8px 0 4px; color: var(--vscode-descriptionForeground); }
.advanced { margin-top: 8px; color: var(--vscode-descriptionForeground); font-size: 12px; }
.advanced > * { margin: 6px 0; display: block; }
</style>
</head>
<body>
<div class="wrap" id="root">${panelMarkup(snapshot)}</div>
<script nonce="${n}">
const vscode = acquireVsCodeApi();
const root = document.getElementById('root');
function send(msg) { vscode.postMessage(msg); }
function bind() {
  const search = document.getElementById('search');
  search?.addEventListener('input', (e) => send({ type: 'search', value: e.target.value }));
  document.getElementById('format')?.addEventListener('change', (e) => send({ type: 'format', value: e.target.value }));
  document.getElementById('selectAll')?.addEventListener('change', (e) => send({ type: 'selectAll', checked: e.target.checked }));
  document.getElementById('export')?.addEventListener('click', () => send({ type: 'export' }));
  document.getElementById('refresh')?.addEventListener('click', () => send({ type: 'refresh' }));
  document.getElementById('restore')?.addEventListener('click', () => send({ type: 'restore' }));
  document.getElementById('transport')?.addEventListener('change', (e) => send({ type: 'transport', value: e.target.value }));
  document.getElementById('keywords')?.addEventListener('change', (e) => send({ type: 'keywords', value: e.target.value }));
  document.getElementById('paths')?.addEventListener('change', (e) => send({ type: 'paths', value: e.target.value }));
  document.getElementById('forceBundle')?.addEventListener('change', (e) => send({ type: 'setting', key: 'forceBundle', checked: e.target.checked }));
  document.getElementById('forceIgnored')?.addEventListener('change', (e) => send({ type: 'setting', key: 'forceIgnored', checked: e.target.checked }));
  document.getElementById('split')?.addEventListener('change', (e) => send({ type: 'setting', key: 'split', checked: e.target.checked }));
  document.getElementById('excludePaths')?.addEventListener('change', (e) => send({ type: 'excludePaths', value: e.target.value }));
  document.getElementById('extraFormats')?.addEventListener('change', (e) => send({ type: 'extraFormats', value: e.target.value }));
  root.querySelectorAll('input[data-path]').forEach((el) => {
    el.addEventListener('change', (e) => send({ type: 'toggleFile', path: e.target.dataset.path, checked: e.target.checked }));
  });
  root.querySelectorAll('input[data-category]').forEach((el) => {
    el.addEventListener('change', (e) => send({ type: 'toggleCategory', category: e.target.dataset.category }));
  });
  root.querySelectorAll('[data-action]').forEach((el) => {
    el.addEventListener('click', (e) => send({ type: e.currentTarget.dataset.action }));
  });
}
bind();
window.addEventListener('message', (event) => {
  const data = event.data;
  if (data?.type !== 'snapshot') return;
  const active = document.activeElement;
  const keep = active && (active.id === 'search' || active.id === 'keywords' || active.id === 'paths' || active.id === 'excludePaths' || active.id === 'extraFormats') ? { id: active.id, start: active.selectionStart, end: active.selectionEnd, value: active.value } : null;
  root.innerHTML = data.markup;
  bind();
  if (keep) {
    const el = document.getElementById(keep.id);
    if (el) { el.value = keep.value; el.focus(); try { el.setSelectionRange(keep.start, keep.end); } catch (_) {} }
  }
});
</script>
</body>
</html>`;
}
