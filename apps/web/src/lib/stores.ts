// Store lookup for labels and the city · area manager filter.
// Copied from data/raw/stores.csv and data/raw/area_managers.csv; the run's
// stores[] carries city once item 5 fills it, but not area managers.

export type StoreInfo = { city: string; tier: string; areaManager: string | null };

const AREA_MANAGERS: Record<string, string> = {
  Lucknow: "Rakesh Srivastava",
  Kanpur: "Alok Tiwari",
  Patna: "Nitin Sinha",
  Muzaffarpur: "Pankaj Jha",
  Bengaluru: "Harish Gowda",
  Mysuru: "Mahesh Shetty",
};

const STORE_ROWS: [id: string, city: string, tier: string][] = [
  ["LKO-01", "Lucknow", "S++"],
  ["LKO-02", "Lucknow", "S+"],
  ["LKO-03", "Lucknow", "A"],
  ["LKO-04", "Lucknow", "S+"],
  ["KNP-01", "Kanpur", "S+"],
  ["KNP-02", "Kanpur", "A"],
  ["KNP-03", "Kanpur", "B"],
  ["PAT-01", "Patna", "S++"],
  ["PAT-02", "Patna", "S+"],
  ["PAT-03", "Patna", "A"],
  ["PAT-04", "Patna", "B"],
  ["MZF-01", "Muzaffarpur", "A"],
  ["MZF-02", "Muzaffarpur", "B"],
  ["BLR-01", "Bengaluru", "S++"],
  ["BLR-02", "Bengaluru", "S++"],
  ["BLR-03", "Bengaluru", "S+"],
  ["BLR-04", "Bengaluru", "S+"],
  ["BLR-05", "Bengaluru", "B"],
  ["MYS-01", "Mysuru", "A"],
  ["MYS-02", "Mysuru", "B"],
];

export const WAREHOUSE_ID = "WH-KOL";

export const STORES: Record<string, StoreInfo> = Object.fromEntries(
  STORE_ROWS.map(([id, city, tier]) => [id, { city, tier, areaManager: AREA_MANAGERS[city] ?? null }]),
);

/** City order for the filter, following the area manager list. */
export const CITIES = Object.keys(AREA_MANAGERS);

export function areaManagerFor(city: string): string | null {
  return AREA_MANAGERS[city] ?? null;
}

/** Human place name for a location id; unknown ids fall back to the raw id. */
export function placeName(id: string): string {
  if (id === WAREHOUSE_ID) return "Kolkata warehouse";
  return STORES[id]?.city ?? id;
}

/** The store a move serves, for the city filter: the destination, or the source for a pull back. */
export function storeCity(id: string): string | null {
  return STORES[id]?.city ?? null;
}
