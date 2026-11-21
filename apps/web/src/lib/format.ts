import type { Move, MoveType } from "./run";

const INR = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export const formatNum = (v: number) => INR.format(v);
export const formatINR = (v: number) => `₹${INR.format(v)}`;

export function formatCompactINR(v: number) {
  if (v >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (v >= 1e5) return `₹${(v / 1e5).toFixed(1)} L`;
  return formatINR(v);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-11-04" -> "4 Nov" (or "4 Nov 2026"). Parsed by hand so no time zone can shift the day. */
export function formatDate(iso: string, withYear = false) {
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]}${withYear ? ` ${y}` : ""}`;
}

const IST_TIME = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

/** ISO datetime -> "21 Nov, 12:30 pm IST". */
export function formatIST(iso: string) {
  const parts = Object.fromEntries(IST_TIME.formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  return `${parts.day} ${parts.month}, ${parts.hour}:${parts.minute} ${String(parts.dayPeriod).toLowerCase()} IST`;
}

export function triggerPhrase(trigger: string) {
  if (trigger === "schedule") return "by the daily run";
  if (trigger === "manual") return "by a manual run";
  if (trigger === "seed") return "from the seed run";
  return `by a ${trigger} run`;
}

export const TYPE_LABEL: Record<MoveType, string> = {
  warehouse_to_store: "Warehouse → Store",
  store_to_store: "Store → Store",
  pull_back: "Pull back",
};

export const TYPE_EMPTY: Record<MoveType, string> = {
  warehouse_to_store: "No warehouse-to-store moves in this run.",
  store_to_store: "No store-to-store moves in this run.",
  pull_back: "No pull-back moves in this run.",
};

export const MOVE_TYPES: MoveType[] = ["warehouse_to_store", "store_to_store", "pull_back"];

export type PriorityTone = "urgent" | "high" | "normal" | "ageing";

export function priorityOf(m: Move): { label: string; tone: PriorityTone } {
  if (m.id.startsWith("age-")) return { label: "Ageing", tone: "ageing" };
  if (m.id.startsWith("capacity-")) return { label: "Capacity", tone: "high" };
  if (m.type === "pull_back") return { label: "Pull back", tone: "normal" };
  if (m.type === "store_to_store") return { label: "Rebalance", tone: "normal" };
  const cover = m.numbers.cover_before;
  if (cover === 0) return { label: "Stock-out", tone: "urgent" };
  if (cover !== null && cover < 7) return { label: "Low cover", tone: "high" };
  return { label: "Top-up", tone: "normal" };
}

export const TONE_TEXT: Record<PriorityTone, string> = {
  urgent: "text-oxblood",
  high: "text-saffron-ink",
  normal: "text-stone",
  ageing: "text-ageing",
};
