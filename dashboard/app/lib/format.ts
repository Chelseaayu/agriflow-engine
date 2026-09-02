// Shared formatters. Indonesian locale everywhere so 406626 reads 406.626.

export function fmtIdr(n: number, opts: { compact?: boolean } = {}): string {
  if (opts.compact) {
    if (Math.abs(n) >= 1_000_000_000_000) return "Rp " + (n / 1_000_000_000_000).toFixed(2) + " T";
    if (Math.abs(n) >= 1_000_000_000) return "Rp " + (n / 1_000_000_000).toFixed(1) + " M";
    if (Math.abs(n) >= 1_000_000) return "Rp " + (n / 1_000_000).toFixed(1) + " jt";
    if (Math.abs(n) >= 1_000) return "Rp " + (n / 1_000).toFixed(0) + " rb";
  }
  return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}

export function fmtTon(n: number, digits = 0): string {
  return n.toLocaleString("id-ID", { maximumFractionDigits: digits }) + " t";
}

export function fmtNum(n: number, digits = 0): string {
  return n.toLocaleString("id-ID", { maximumFractionDigits: digits });
}

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined) return "n/a";
  return n.toFixed(digits).replace(".", ",") + "%";
}

export function fmtDate(iso: string | null | undefined, withYear = true): string {
  if (!iso) return "?";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("id-ID", {
    day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}),
  });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "?";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("id-ID", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }) + " WIB";
}

export function shortKab(name: string): string {
  return name.replace(/^Kab\. /, "").replace(/^Kabupaten /, "");
}

export const COMMODITY_NAMES: Record<string, string> = {
  cabai_rawit: "Cabai Rawit",
  cabai_merah: "Cabai Merah Besar",
  bawang_merah: "Bawang Merah",
  bawang_putih: "Bawang Putih",
  beras_medium: "Beras Medium",
  beras_premium: "Beras Premium",
  daging_ayam: "Daging Ayam",
  telur_ayam: "Telur Ayam",
};

export function commodityName(code: string, list?: { code: string; nama: string }[]): string {
  return list?.find((c) => c.code === code)?.nama ?? COMMODITY_NAMES[code] ?? code;
}
