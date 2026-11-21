import type { Move } from "./run";

export type Decision = "approved" | "rejected";
export type Decisions = Record<string, Decision>;

export const approvalsKey = (runId: string) => `stock-mover:approvals:${runId}`;

/**
 * Reads saved decisions for a run. Missing storage, corrupt JSON, unknown move ids
 * and unexpected values all degrade to "no decision" instead of throwing.
 */
export function loadDecisions(runId: string, moveIds: ReadonlySet<string>): Decisions {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(approvalsKey(runId));
  } catch {
    return {};
  }
  if (!raw) return {};

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {};
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};

  const out: Decisions = {};
  for (const [id, value] of Object.entries(parsed)) {
    if (moveIds.has(id) && (value === "approved" || value === "rejected")) out[id] = value;
  }
  return out;
}

/** Saves decisions; returns false when storage is unavailable (decisions then last for the session only). */
export function saveDecisions(runId: string, decisions: Decisions): boolean {
  try {
    window.localStorage.setItem(approvalsKey(runId), JSON.stringify(decisions));
    return true;
  } catch {
    return false;
  }
}

const CSV_COLUMNS = [
  "move_id",
  "type",
  "sku_id",
  "style_name",
  "category",
  "size",
  "from",
  "to",
  "units",
  "value_mrp",
  "arrives_on",
  "needs_senior_approval",
  "reason",
] as const;

/** RFC 4180 field: quote when it holds a comma, quote or line break; double embedded quotes. */
function csvField(value: string | number | boolean): string {
  const s = String(value);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Every approved move in the run (filters ignored), highest priority first, as CSV text. */
export function toApprovedCsv(moves: readonly Move[], decisions: Decisions): string {
  const rows = moves
    .filter((m) => decisions[m.id] === "approved")
    .sort((a, b) => b.priority - a.priority)
    .map((m) =>
      [
        m.id,
        m.type,
        m.sku_id,
        m.style_name,
        m.category,
        m.size,
        m.from,
        m.to,
        m.units,
        m.value_mrp,
        m.arrives_on,
        m.needs_senior_approval,
        m.reason,
      ]
        .map(csvField)
        .join(","),
    );
  return [CSV_COLUMNS.join(","), ...rows].join("\r\n") + "\r\n";
}
