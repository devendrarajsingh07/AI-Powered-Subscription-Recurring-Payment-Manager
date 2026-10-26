// Local synthetic integration workload, not frontend financial calculations or capacity proof.
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Counter } from "k6/metrics";

const input = JSON.parse(open("/private/load-input.json"));
const csv = open("/fixtures/sample_transactions.csv", "b");
const textPdf = open("/fixtures/extraction/text_single.pdf", "b");
const scannedPdf = open("/fixtures/extraction/scanned.pdf", "b");
const manifest = JSON.parse(open("/fixtures/extraction/manifest.json"));
const api = "http://web:8080/api/v1";
const endToEnd = new Trend("flow_duration", true);
const completed = new Counter("verified_flows");
export const options = {
  scenarios: {
    synthetic: { executor: "per-vu-iterations", vus: 3, iterations: 3, maxDuration: "3m" },
  },
  thresholds: { http_req_failed: ["rate==0"], checks: ["rate==1"], verified_flows: ["count==9"] },
  summaryTrendStats: ["avg", "min", "med", "max", "p(50)", "p(95)"],
  discardResponseBodies: false,
  tags: { environment: "local-synthetic-drill" },
};

function requireResponse(response, status, label) {
  if (!check(response, { [label]: (r) => r.status === status }))
    throw new Error("Local workload request failed: " + label);
  return response;
}
function jsonGet(path, token, name) {
  return requireResponse(http.get(api + path, { headers: { Authorization: "Bearer " + token }, tags: { name } }), 200, name).json();
}
function waitFor(path, token, final, name) {
  for (let attempt = 0; attempt < 160; attempt++) {
    const value = jsonGet(path, token, name);
    if (value.status === final) return value;
    if (["failed", "dead_letter", "cancelled"].includes(value.status))
      throw new Error("Synthetic job ended unsuccessfully");
    sleep(0.25);
  }
  throw new Error("Synthetic job deadline exceeded");
}

export default function () {
  const start = Date.now();
  const user = input.users[__VU - 1];
  const login = requireResponse(http.post(api + "/auth/login", JSON.stringify({ email: user.email, password: user.password }), {
    headers: { "Content-Type": "application/json" }, tags: { name: "login" },
  }), 200, "login").json();
  const token = login.access_token;
  const headers = { Authorization: "Bearer " + token };
  const upload = requireResponse(http.post(api + "/uploads", {
    mapping: JSON.stringify({ date: "date", description: "description", amount: "amount", type: "type" }),
    file: http.file(csv, "synthetic.csv", "text/csv"),
  }, { headers, tags: { name: "csv-upload" } }), 202, "CSV accepted").json();
  waitFor("/uploads/" + upload.id, token, "done", "CSV progress");

  const name = __ITER % 2 === 0 ? "text_single.pdf" : "scanned.pdf";
  const source = name === "text_single.pdf" ? textPdf : scannedPdf;
  const preview = requireResponse(http.post(api + "/uploads/preview", {
    file: http.file(source, name, "application/pdf"),
  }, { headers, tags: { name: name === "scanned.pdf" ? "ocr-preview" : "text-preview" } }), 202, "PDF accepted").json();
  const ready = waitFor("/uploads/previews/" + preview.id, token, "ready", "extraction progress");
  const truth = manifest.variants.find((item) => item.file === name).rows;
  if (!check(ready, { "extracted row count matches source labels": (v) => v.result.rows.length === truth.length }))
    throw new Error("Extraction row count differs from labelled synthetic source");
  // Scripted, explicit synthetic review: correct fields from independently labelled source.
  // The real parser/worker still runs; no extracted or detected response is mocked.
  const edits = ready.result.rows.map((row, index) => ({ index: row.index, ...truth[index], verified: true }));
  const imported = requireResponse(http.post(api + "/uploads", {
    preview_id: preview.id, edits: JSON.stringify(edits),
  }, { headers, tags: { name: "reviewed-import" } }), 202, "review accepted").json();
  waitFor("/uploads/" + imported.id, token, "done", "import progress");

  const summary = jsonGet("/summary", token, "summary");
  check(summary, { "exact independently computed monthly total": (v) => v.monthly_equivalent === input.expected_monthly });
  const chat = requireResponse(http.post(api + "/chat", JSON.stringify({ message: "monthly spend" }), {
    headers: { ...headers, "Content-Type": "application/json" }, tags: { name: "offline-chat" },
  }), 200, "chat accepted");
  const finals = chat.body.split("\n\n").filter((event) => event.startsWith("event: final\n"));
  const final = finals.length === 1 ? JSON.parse(finals[0].split("\ndata: ")[1]) : null;
  if (check(final, { "verified offline chat final": (v) => v && v.verified === true && v.mode === "offline" }))
    completed.add(1);
  endToEnd.add(Date.now() - start);
  sleep(0.5);
}

export function handleSummary(data) {
  // No request bodies, headers, tokens, email addresses or financial figures in the report.
  return { "/reports/load-summary.json": JSON.stringify(data, null, 2) };
}
