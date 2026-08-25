const krwFormatter = new Intl.NumberFormat("ko-KR", {
  style: "currency",
  currency: "KRW",
  maximumFractionDigits: 0,
});

export function formatKRW(value: number): string {
  return krwFormatter.format(value);
}

export function formatKRWLimit(value: number): string {
  return value > 0 ? formatKRW(value) : "제한 없음";
}
