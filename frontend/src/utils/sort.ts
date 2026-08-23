export function compareText(a: string, b: string): number {
  return a.localeCompare(b, "es", { sensitivity: "base" });
}

export function compareNumber(a: number, b: number): number {
  return a - b;
}

// Compara IPs octeto por octeto como números, no como texto -- si no,
// "10.100.10.5" queda antes que "10.100.9.5" porque '1' < '9' como caracter.
export function compareIp(a: string, b: string): number {
  if (!a && !b) return 0;
  if (!a) return 1; // sin IP al final
  if (!b) return -1;
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
}
