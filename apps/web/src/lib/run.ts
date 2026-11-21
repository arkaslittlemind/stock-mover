import { readFileSync } from "node:fs";
import path from "node:path";
import { head } from "@vercel/blob";
import { cacheLife } from "next/cache";
import { z } from "zod";

// Mirrors apps/web/data/run.schema.json (the engine's Pydantic contract, locked in item 1).
// Strict objects: an unknown field is a contract break, not something to ignore.

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");

const RunInfoSchema = z.strictObject({
  id: z.string(),
  data_as_of: isoDate,
  generated_at: z.iso.datetime({ offset: true }),
  trigger: z.string(),
});

const BriefingSchema = z.strictObject({
  text: z.string(),
  source: z.enum(["llm", "template"]),
  checked: z.boolean(),
});

const MoveNumbersSchema = z.strictObject({
  velocity: z.number(),
  days_in_stock_84: z.number().int().min(0).max(84),
  cover_before: z.number().nullable(),
  cover_after: z.number().nullable(),
  lift: z.number(),
});

const MoveSchema = z.strictObject({
  id: z.string(),
  type: z.enum(["warehouse_to_store", "store_to_store", "pull_back"]),
  sku_id: z.string(),
  style_id: z.string(),
  style_name: z.string(),
  category: z.string(),
  size: z.string(),
  from: z.string(),
  to: z.string(),
  units: z.number().int().min(1),
  value_mrp: z.number().min(0),
  lead_days: z.number().int().min(0),
  arrives_on: isoDate,
  priority: z.number(),
  reason: z.string(),
  needs_senior_approval: z.boolean(),
  numbers: MoveNumbersSchema,
});

const RuleResultSchema = z.strictObject({
  rule: z.string(),
  label: z.string(),
  checked: z.number().int().min(0),
  passed: z.boolean(),
  failures: z.array(z.unknown()),
});

const DataIssueSchema = z.strictObject({
  location_id: z.string(),
  sku_id: z.string(),
  checks: z.array(z.enum(["negative_stock", "snapshot_vs_weekly", "unknown_sku", "unknown_location"])).min(1),
  note: z.string(),
  excluded: z.boolean(),
});

const MinDisplayGapSchema = z.strictObject({
  category: z.string(),
  min_display_units: z.number().int(),
  units: z.number().int(),
  gap: z.number().int(),
});

const StoreHealthSchema = z.strictObject({
  store_id: z.string(),
  city: z.string(),
  zone: z.string(),
  tier: z.string(),
  capacity_units: z.number().int(),
  units_on_hand: z.number().int(),
  units_in_transit: z.number().int(),
  fill_pct: z.number(),
  days_of_cover: z.number().nullable(),
  min_display_gaps: z.array(MinDisplayGapSchema),
  flags: z.array(z.string()),
});

export const RunSchema = z.strictObject({
  run: RunInfoSchema,
  briefing: BriefingSchema,
  moves: z.array(MoveSchema),
  rule_check: z.array(RuleResultSchema),
  data_issues: z.array(DataIssueSchema),
  stores: z.array(StoreHealthSchema),
});

export type Run = z.infer<typeof RunSchema>;
export type Move = Run["moves"][number];
export type MoveType = Move["type"];
export type DataIssue = Run["data_issues"][number];

export type RunSource = "blob" | "seed";
export type RunLoadResult = { ok: true; run: Run; source: RunSource } | { ok: false; problem: string; paths: string[] };
type ParseResult = { ok: true; run: Run } | { ok: false; problem: string; paths: string[] };

const SEED_RUN_PATH = path.join(process.cwd(), "data", "seed-run.json");
const BLOB_RUN_PATHNAME = "runs/latest.json";

/** Parses raw run text against the contract. Expected failures become an error result, never a throw. */
export function parseRun(raw: string): ParseResult {
  let json: unknown;
  try {
    json = JSON.parse(raw);
  } catch {
    return { ok: false, problem: "The run file is not valid JSON.", paths: [] };
  }

  const parsed = RunSchema.safeParse(json);
  if (!parsed.success) {
    const paths = parsed.error.issues.slice(0, 3).map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`);
    return { ok: false, problem: "The run file does not match the expected format.", paths };
  }

  return { ok: true, run: parsed.data };
}

/** Latest run uploaded by the daily job, or null with one warning line on any failure. */
async function loadBlobRun(): Promise<Run | null> {
  if (!process.env.BLOB_READ_WRITE_TOKEN) return null;
  try {
    const meta = await head(BLOB_RUN_PATHNAME);
    // The version query skips a CDN copy older than the latest upload.
    const res = await fetch(`${meta.url}?v=${meta.uploadedAt.getTime()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const result = parseRun(await res.text());
    if (!result.ok) throw new Error(`${result.problem} ${result.paths.join("; ")}`);
    return result.run;
  } catch (error) {
    const reason = error instanceof Error ? error.message : "unknown error";
    console.warn(`Blob run unavailable, using the seed run: ${reason}`);
    return null;
  }
}

/** Latest Blob run when available, else the committed seed run. Cached and refreshed every 60 seconds. */
export async function loadRun(): Promise<RunLoadResult> {
  "use cache";
  cacheLife({ stale: 60, revalidate: 60, expire: 3600 });

  const blobRun = await loadBlobRun();
  if (blobRun) return { ok: true, run: blobRun, source: "blob" };

  let raw: string;
  try {
    raw = readFileSync(SEED_RUN_PATH, "utf8");
  } catch {
    return { ok: false, problem: "The run file is missing.", paths: [] };
  }
  const result = parseRun(raw);
  return result.ok ? { ...result, source: "seed" } : result;
}
