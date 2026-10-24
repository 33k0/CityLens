#!/usr/bin/env node
// Pipeline step e: voice taxonomy + category/stance labels via IBM Bob's /categorize-comments skill.
//
//   node scripts/run_bob.mjs [item|all] [--offline] [--rebuild-taxonomy] [--probe] [--dry-run]
//
// --offline           NO Bob and NO Ollama calls, nothing spent: keeps the committed data/categories.json and
//                     replays labels from data/classify_cache.json (classify.py --cache-only, which fails loudly if
//                     a row is missing). Provenance step "pipeline_offline", engine "cache".
// (warm, default)     Bob runs only when needed: if data/categories.json is already authored_by "ibm-bob" and the
//                     voice corpus fingerprint is unchanged, Bob is skipped (unless --rebuild-taxonomy) and only
//                     classify.py runs (Granite via Ollama, cached). Otherwise, if `bob` is installed, BOB_API_KEY is
//                     set (env or .env.local, parsed here) and the user's license consent is recorded in
//                     ~/.bob/settings/settings.json, runs
//                       bob run --mode agent --format json --max-turns 25 --max-cost 3 --trust -w <repo> "<prompt>"
//                     under the BOB_MAX_RUNS budget (default 6, counted in data/bob_runs.json). This script NEVER
//                     passes --accept-license. If Bob is unusable, a loud warning is printed and classify.py runs
//                     on the existing taxonomy, recorded as engine "fallback" with the reason.
// --rebuild-taxonomy  Bob derives the taxonomy from scratch: the current categories.json / prompts/classify.txt /
//                     labels are moved into the gitignored data/raw/pre_bob/ (Bob is told not to read data/raw/),
//                     and afterwards the old taxonomy is restored as data/categories.pre_bob.json for the diff.
// --probe             one Bob turn asking which workspace skills it sees (records cost).
// --dry-run           print what would happen and exit; no calls.
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { delimiter, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = dirname(dirname(fileURLToPath(import.meta.url)));
const DATA = join(REPO, "data");
const RUNS_PATH = join(DATA, "bob_runs.json");
const PROV_PATH = join(REPO, "public", "data", "provenance.json");
const CATS_PATH = join(DATA, "categories.json");
const PROMPT_PATH = join(REPO, "prompts", "classify.txt");
const PRE_BOB_DIR = join(DATA, "raw", "pre_bob");
const argv = process.argv.slice(2);
const flag = (f) => argv.includes(f);
const OFFLINE = flag("--offline");
const PROBE = flag("--probe");
const DRY = flag("--dry-run");
const REBUILD = flag("--rebuild-taxonomy");
const target = argv.find((a) => !a.startsWith("--")) || "all";
const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");

function loadEnvLocal() {
  const p = join(REPO, ".env.local");
  if (!existsSync(p)) return {};
  const out = {};
  for (const line of readFileSync(p, "utf8").split("\n")) {
    const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (m) out[m[1]] = m[2].replace(/^(["'])(.*)\1$/, "$2");
  }
  return out;
}
const envLocal = loadEnvLocal();
const env = (k, d = "") => process.env[k] || envLocal[k] || d;
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const redact = (s) => {
  let out = String(s || "").replace(/bob_prod_[A-Za-z0-9_-]+/g, "[REDACTED]");
  const key = env("BOB_API_KEY");
  if (key) out = out.replace(new RegExp(escapeRe(key), "g"), "[REDACTED]");
  return out;
};

function loud(msg) {
  const bar = "!".repeat(78);
  console.error(`\n${bar}\n!! WARNING: ${msg}\n${bar}\n`);
}
function readJson(p, dflt) {
  try {
    return JSON.parse(readFileSync(p, "utf8"));
  } catch {
    return dflt;
  }
}
function writeJson(p, obj) {
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(obj, null, 2) + "\n");
}
function upsertProvenance(rec) {
  const prov = readJson(PROV_PATH, {});
  const recs = (prov.records || []).filter((r) => r.step !== rec.step);
  recs.push(rec);
  recs.sort((a, b) => (a.started_at || "").localeCompare(b.started_at || ""));
  writeJson(PROV_PATH, {
    schema: 1,
    note: "One record per pipeline step, latest run. Bob run history: data/bob_runs.json.",
    updated_at: now(),
    records: recs,
  });
}
const python = () => (existsSync(join(REPO, ".venv", "bin", "python")) ? join(REPO, ".venv", "bin", "python") : "python3");
function classify(args, extraEnv = {}) {
  return spawnSync(python(), [join(REPO, "scripts", "classify.py"), ...args], {
    cwd: REPO,
    stdio: "inherit",
    env: { ...process.env, ...extraEnv },
  }).status;
}
function fingerprint() {
  const r = spawnSync(python(), [join(REPO, "scripts", "classify.py"), "--fingerprint"], { cwd: REPO, encoding: "utf8" });
  try {
    return JSON.parse(r.stdout.trim().split("\n").pop());
  } catch {
    return null;
  }
}
function findBob() {
  for (const dir of (process.env.PATH || "").split(delimiter)) {
    if (dir && existsSync(join(dir, "bob"))) return join(dir, "bob");
  }
  const local = join(homedir(), ".local", "bin", "bob");
  return existsSync(local) ? local : null;
}
function licenseAccepted() {
  // Bob records the user's own license acceptance as "licenseConsent": true in ~/.bob/settings/settings.json.
  return readJson(join(homedir(), ".bob", "settings", "settings.json"), {}).licenseConsent === true;
}
function parseBobJson(stdout) {
  // --format json prints JSON objects line by line; the {"type":"result"} line carries status and stats.
  let result = null;
  for (const line of String(stdout || "").split("\n")) {
    const t = line.trim();
    if (!t.startsWith("{")) continue;
    try {
      const o = JSON.parse(t);
      if (o.type === "result" || o.stats) result = o;
    } catch {
      /* not a JSON line */
    }
  }
  return result;
}

const started = now();
const cats = readJson(CATS_PATH, null);

// ---------------------------------------------------------------- offline: replay only, spend nothing
if (OFFLINE) {
  console.log("== run_bob.mjs --offline: no Bob or Ollama calls; replaying cached labels");
  if (!cats) {
    loud("--offline needs a committed data/categories.json; run a warm build (npm run data) first");
    process.exit(2);
  }
  if (DRY) {
    console.log(`dry-run: would run classify.py --cache-only --item ${target} on taxonomy ${cats.version} (${cats.authored_by})`);
    process.exit(0);
  }
  const status = classify(["--cache-only", "--item", target]);
  upsertProvenance({
    step: "pipeline_offline",
    engine: "cache",
    model: null,
    reason: "--offline: no Bob or Ollama calls; committed categories.json kept, labels replayed from data/classify_cache.json",
    started_at: started,
    finished_at: now(),
    counts: { target, classify_exit_code: status, taxonomy_version: cats.version, taxonomy_authored_by: cats.authored_by },
    categories_source: cats.source || null,
  });
  if (status !== 0) loud("offline replay failed: a voice row is missing from data/classify_cache.json (see above)");
  process.exit(status ?? 1);
}

// ---------------------------------------------------------------- warm: decide whether Bob is needed
const fp = fingerprint();
const taxonomyCurrent =
  cats && cats.authored_by === "ibm-bob" && fp && cats.corpus_fingerprint && cats.corpus_fingerprint.sha256 === fp.sha256;
const needBob = PROBE || REBUILD || !taxonomyCurrent;
const runs = readJson(RUNS_PATH, { runs: [] });
const bobRunsUsed = runs.runs.filter((r) => r.engine === "bob").length;
const maxRuns = Number(env("BOB_MAX_RUNS", "10"));
const bob = findBob();
const reasons = [];
if (!bob) reasons.push("bob CLI not installed (not on PATH or ~/.local/bin)");
if (!env("BOB_API_KEY")) reasons.push("BOB_API_KEY is not set");
if (bob && !licenseAccepted()) reasons.push("IBM license not accepted by the user (this script never passes --accept-license)");
if (bobRunsUsed >= maxRuns) reasons.push(`Bob budget exhausted (${bobRunsUsed}/${maxRuns} runs in data/bob_runs.json)`);

if (DRY) {
  console.log(JSON.stringify({ target, needBob, taxonomyCurrent, rebuild: REBUILD, bobUsable: reasons.length === 0, reasons, bobRunsUsed, maxRuns, fingerprint: fp }, null, 2));
  process.exit(0);
}

if (!needBob) {
  console.log(`== taxonomy ${cats.version} authored by IBM Bob is current for this corpus (${fp.sha256}); skipping Bob`);
  const status = classify(["--item", target]);
  upsertProvenance({
    step: "taxonomy_check",
    engine: "cache",
    model: null,
    reason: "categories.json already authored by ibm-bob for an unchanged corpus; Bob not called (pass --rebuild-taxonomy to force)",
    started_at: started,
    finished_at: now(),
    counts: { target, classify_exit_code: status, bob_task_ids: cats.bob_task_ids || [] },
    categories_source: cats.source || null,
  });
  process.exit(status ?? 1);
}

const form = env("BOB_PROMPT_FORM", "slash");
const prompt = PROBE
  ? "Without using any tools, list in one line the names of the skills you have available in this workspace " +
    "(for example from .bob/skills), and say whether '/categorize-comments' would invoke one of them."
  : form === "prompt"
    ? `Follow the instructions in .bob/skills/categorize-comments/SKILL.md for ${target === "all" ? "all items" : `item ${target}`}. Obey .bob/rules/civic-data.md.`
    : `/categorize-comments ${target}`;

let bobRun = null;
let hidden = [];
if (reasons.length === 0) {
  // A fresh derivation must not see the previous taxonomy or labels: move them out of Bob's view.
  if (!PROBE && (REBUILD || !cats || cats.authored_by !== "ibm-bob")) {
    mkdirSync(PRE_BOB_DIR, { recursive: true });
    const stamp = started.replace(/[:]/g, "");
    for (const [src, name] of [
      [CATS_PATH, `categories.${stamp}.json`],
      [PROMPT_PATH, `classify.${stamp}.txt`],
      [join(DATA, "classifications.csv"), `classifications.${stamp}.csv`],
      [join(DATA, "labeled_sample_template.csv"), `labeled_sample_template.${stamp}.csv`],
      [join(DATA, "categories.pre_bob.json"), `categories.pre_bob.${stamp}.json`],
    ]) {
      if (existsSync(src)) {
        renameSync(src, join(PRE_BOB_DIR, name));
        hidden.push([src, join(PRE_BOB_DIR, name)]);
      }
    }
  }
  const args = ["run", "--mode", "agent", "--format", "json", "--max-turns", PROBE ? "1" : env("BOB_MAX_TURNS", "25"),
    "--max-cost", env("BOB_MAX_COST", "3"), "--trust", "-w", REPO, prompt];
  console.log(`== bob ${args.map((a) => (a.includes(" ") ? JSON.stringify(a) : a)).join(" ")}`);
  const t0 = Date.now();
  const r = spawnSync(bob, args, {
    cwd: REPO,
    encoding: "utf8",
    env: { ...process.env, BOB_API_KEY: env("BOB_API_KEY") },
    maxBuffer: 256 * 1024 * 1024,
    timeout: 90 * 60 * 1000,
  });
  const stdout = redact(r.stdout);
  const parsed = parseBobJson(stdout);
  const st = parsed?.stats || {};
  bobRun = {
    engine: parsed ? "bob" : "bob_failed", // every call that reached Bob counts against the budget
    kind: PROBE ? "probe" : "categorize",
    status: parsed?.status ?? `exit ${r.status}${r.error ? ` (${r.error.code})` : ""}`,
    prompt_form: PROBE ? "probe" : form,
    prompt,
    target,
    started_at: started,
    finished_at: now(),
    seconds: Math.round((Date.now() - t0) / 1000),
    exit_code: r.status,
    task_id: st.task_id ?? null,
    duration_ms: st.duration_ms ?? null,
    session_costs: st.session_costs ?? null,
    stats: st,
    last_message: parsed?.last_message ?? null,
    output_excerpt: parsed ? null : redact(`${r.stdout || ""}${r.stderr || ""}`).slice(-3000),
  };
  runs.runs.push(bobRun);
  writeJson(RUNS_PATH, runs);
  writeFileSync(join(DATA, `bob_last_output${PROBE ? "_probe" : ""}.jsonl`), stdout);
  if (PROBE) {
    console.log(JSON.stringify({ status: bobRun.status, session_costs: bobRun.session_costs, last_message: bobRun.last_message }, null, 2));
    process.exit(parsed?.status === "success" ? 0 : 1);
  }
  const wroteCats = existsSync(CATS_PATH) && statSync(CATS_PATH).mtimeMs >= t0;
  const wrotePrompt = existsSync(PROMPT_PATH) && statSync(PROMPT_PATH).mtimeMs >= t0;
  if (parsed?.status !== "success") reasons.push(`bob run did not succeed (${bobRun.status})`);
  if (!wroteCats) reasons.push("Bob did not write data/categories.json");
  if (!wrotePrompt) reasons.push("Bob did not write prompts/classify.txt");
  if (wroteCats && wrotePrompt) {
    // Stamp authorship from the real run stats (Bob cannot know its own task id).
    const c = readJson(CATS_PATH, null);
    if (c) {
      const prev = c.authored_by === "ibm-bob" && Array.isArray(c.bob_task_ids) ? c.bob_task_ids : [];
      c.authored_by = "ibm-bob";
      c.bob_task_ids = [...new Set([...prev, bobRun.task_id].filter(Boolean))];
      c.authored_on = new Date().toLocaleDateString("en-CA"); // local YYYY-MM-DD
      c.corpus_fingerprint = fp;
      writeJson(CATS_PATH, c);
    } else {
      reasons.push("data/categories.json written by Bob is not valid JSON");
    }
  }
}

// Restore the hidden draft: old taxonomy becomes data/categories.pre_bob.json (visible, for the diff) when Bob
// produced a new one; otherwise everything goes back where it was.
const bobAuthored = bobRun && reasons.length === 0;
for (const [orig, moved] of hidden) {
  if (!existsSync(moved)) continue;
  if (orig === CATS_PATH) {
    copyFileSync(moved, bobAuthored ? join(DATA, "categories.pre_bob.json") : CATS_PATH);
  } else if (orig === PROMPT_PATH) {
    if (!bobAuthored) copyFileSync(moved, PROMPT_PATH);
  } else if (orig.endsWith("categories.pre_bob.json")) {
    if (!bobAuthored) copyFileSync(moved, orig);
  } else if (!bobAuthored) {
    copyFileSync(moved, orig);
  }
}

if (bobAuthored) {
  // Make sure labels match Bob's taxonomy even if Bob's own classify step timed out or was a rules smoke test.
  let cls = (readJson(PROV_PATH, {}).records || []).find((r) => r.step === "classify");
  const fresh = cls && (cls.started_at || "") >= started && cls.engine === "ollama" && cls.item === target;
  let rerun = false;
  if (!fresh) {
    console.log("== Bob did not complete a Granite classify run on its taxonomy; running scripts/classify.py now");
    classify(["--item", target]);
    rerun = true;
    cls = (readJson(PROV_PATH, {}).records || []).find((r) => r.step === "classify");
  }
  const c = readJson(CATS_PATH, {});
  upsertProvenance({
    step: "bob_categorize",
    engine: "bob",
    model: "IBM Bob Shell (agent mode), skill categorize-comments",
    reason: "",
    started_at: started,
    finished_at: bobRun.finished_at,
    task_id: bobRun.task_id,
    duration_ms: bobRun.duration_ms,
    session_costs: bobRun.session_costs,
    stats: bobRun.stats,
    prompt_form: bobRun.prompt_form,
    summary: (bobRun.last_message || "").slice(0, 2000),
    counts: {
      bob_runs_used: bobRunsUsed + 1,
      bob_max_runs: maxRuns,
      target,
      categories: (c.categories || []).map((x) => x.key),
      classify_rerun_by_run_bob: rerun,
      rows_by_engine: cls?.counts ? { ollama: cls.counts.ollama, fallback: cls.counts.fallback } : null,
    },
    categories_source: c.source || null,
  });
  console.log(`Bob run ${bobRun.task_id} recorded (${bobRunsUsed + 1}/${maxRuns} runs), cost $${bobRun.session_costs}.`);
  process.exit(0);
}

// ---------------------------------------------------------------- fallback: Bob not usable or failed
const reason = reasons.join("; ");
loud(`IBM Bob did NOT author this step. Reason: ${reason}.\n!! Running scripts/classify.py on the existing taxonomy; provenance records engine "fallback".`);
if (!existsSync(CATS_PATH)) {
  loud("no data/categories.json to fall back to; stopping");
  process.exit(2);
}
const status = classify(["--item", target], { BOB_FALLBACK_REASON: reason });
const clsRec = (readJson(PROV_PATH, {}).records || []).find((r) => r.step === "classify") || {};
upsertProvenance({
  step: "bob_categorize",
  engine: "fallback",
  model: clsRec.model || null,
  reason,
  started_at: started,
  finished_at: now(),
  task_id: bobRun?.task_id ?? null,
  session_costs: bobRun?.session_costs ?? null,
  counts: {
    bob_runs_used: bobRunsUsed + (bobRun ? 1 : 0),
    bob_max_runs: maxRuns,
    target,
    classify_exit_code: status,
    rows_by_engine: clsRec.counts ? { ollama: clsRec.counts.ollama, fallback: clsRec.counts.fallback } : null,
  },
  categories_source: readJson(CATS_PATH, {}).source || null,
});
process.exit(status ?? 1);
