import { loadPolicy } from "./policy.ts";

const RE_JWT =
  /\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b/g;
const RE_BEARER = /(Authorization\s*:\s*Bearer\s+)([A-Za-z0-9\-_\.=]+)/gi;
const RE_BEARER_JSON = /("Authorization"\s*:\s*")Bearer\s+[^"]+(")/gi;
const RE_API_KEY_HEADER =
  /((?:x-api-key|api-key|apikey|api_key)["\s:=]+)(["']?[A-Za-z0-9_\-\.]{8,}["']?)/gi;
const RE_JSON_SECRET =
  /("(?:api[_-]?key|token|secret|password|client[_-]?secret|access[_-]?token|refresh[_-]?token|bearer|auth_token|private[_-]?key|credentials)"\s*:\s*)"[^"]*"/gi;
const RE_YAML_SECRET =
  /(api[_-]?key|token|secret|password|client[_-]?secret|access[_-]?token|refresh[_-]?token|bearer|auth_token|private[_-]?key|credentials|secret[_-]?key|signing[_-]?key)\s*:\s*(\S+)/gi;
const RE_URL_SECRET =
  /\b((?:token|access_token|refresh_token|api_key|apikey|secret|sig|signature|auth|bearer|password|passwd|pwd)=)([^&\s"]+)/gi;
const RE_PRIVATE_KEY_BLOCK =
  /-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----/gs;
const RE_ENV_SECRET =
  /^\s*(?:export\s+)?(?<key>(?:SECRET_KEY|API_KEY|PRIVATE_KEY|SIGNING_KEY|CLIENT_SECRET|API_SECRET|ACCESS_KEY|AUTH_TOKEN|BEARER_TOKEN|CREDENTIALS|TOKEN|PASSWORD|PASS|SIGNING_SECRET|API_PASSWORD|CLIENT_KEY)[A-Z0-9_]*)\s*=\s*(?<val>.*)$/gm;
const RE_BASE64_SECRET =
  /((?:secret|private|signing)[_-]?key(?:_[a-z]+)?)\s*=\s*['"]([A-Za-z0-9+/]{20,}={0,2})['"]/gi;
const RE_HEX_TOKEN =
  /((?:secret|token|password|auth)[_-]?(?:key|value|hash|secret)?)\s*=\s*['"]([0-9a-f]{32,})['"]/gi;
const RE_AWS_KEY = /(AKIA[0-9A-Z]{16})/g;
const RE_GITHUB_TOKEN = /(gh[pousr]_[A-Za-z0-9_]{36,251})/g;
const RE_SLACK_TOKEN = /(xox[bpors]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*)/g;
const RE_GOOGLE_API_KEY = /(AIza[0-9A-Za-z\-_]{35})/g;
const RE_STRIPE_KEY = /(sk_live_[0-9a-zA-Z]{24,})/g;
const RE_TWILIO_KEY = /(SK[0-9a-fA-F]{32})/g;

export function redactText(text: string): string {
  if (!text) return text ?? "";
  const mark = loadPolicy().redactionMark;

  text = text.replace(
    RE_PRIVATE_KEY_BLOCK,
    `-----BEGIN PRIVATE KEY-----\n${mark}\n-----END PRIVATE KEY-----`,
  );
  text = text.replace(RE_BEARER, `$1${mark}`);
  text = text.replace(RE_BEARER_JSON, `$1Bearer ${mark}$2`);
  text = text.replace(RE_API_KEY_HEADER, `$1${mark}`);
  text = text.replace(RE_JWT, mark);
  text = text.replace(RE_AWS_KEY, mark);
  text = text.replace(RE_GITHUB_TOKEN, mark);
  text = text.replace(RE_SLACK_TOKEN, mark);
  text = text.replace(RE_GOOGLE_API_KEY, mark);
  text = text.replace(RE_STRIPE_KEY, mark);
  text = text.replace(RE_TWILIO_KEY, mark);
  text = text.replace(RE_JSON_SECRET, `$1"${mark}"`);
  text = text.replace(RE_YAML_SECRET, (full, key: string, val: string) => {
    const v = val.trim();
    if (!v || v === '""' || v === "''" || v === "null" || v === "~") return full;
    return `${key}: ${mark}`;
  });
  text = text.replace(RE_URL_SECRET, `$1${mark}`);
  text = text.replace(RE_BASE64_SECRET, `$1="${mark}"`);
  text = text.replace(RE_HEX_TOKEN, `$1='${mark}'`);
  text = text.replace(RE_ENV_SECRET, (full, key: string, val: string) => {
    if (!val || val.trim() === "") return full;
    const v = val.trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      const q = v[0];
      return `${key}=${q}${mark}${q}`;
    }
    return `${key}=${mark}`;
  });
  return text;
}

export function redactLines(lines: string[]): string[] {
  return lines.map((line) => redactText(line));
}
