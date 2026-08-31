import assert from "node:assert/strict";
import test from "node:test";
import { redactText } from "../src/redact.ts";

test("redacts jwt", () => {
  const jwt =
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.signaturexx";
  assert.equal(redactText(jwt), "<REDACTED>");
});

test("redacts bearer header", () => {
  const out = redactText("Authorization: Bearer abcdefghijklmnop");
  assert.match(out, /Authorization: Bearer <REDACTED>/i);
});

test("redacts aws key", () => {
  assert.equal(redactText("AKIAIOSFODNN7EXAMPLE"), "<REDACTED>");
});

test("redacts github token", () => {
  const tok = "ghp_" + "a".repeat(36);
  assert.equal(redactText(tok), "<REDACTED>");
});

test("redacts env assignment", () => {
  assert.equal(redactText("API_KEY=supersecretvalue"), "API_KEY=<REDACTED>");
});
