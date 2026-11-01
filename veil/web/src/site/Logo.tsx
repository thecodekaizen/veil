/** Veil mark: an amber evidence frame (what a model found) with an ink cover drawn across it (what code did). */
export function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="3" y="3" width="26" height="26" rx="7" fill="none" stroke="#E8B04A" strokeWidth="2.5" />
      <path d="M3 18 L18 3 H22 A7 7 0 0 1 29 10 V22 A7 7 0 0 1 22 29 H10 A7 7 0 0 1 3 22 Z" fill="#F2EFE8" />
      <path d="M10 29 L29 10" stroke="#0B0D10" strokeWidth="2" />
    </svg>
  );
}

export function Brand() {
  return (
    <a className="brand" href="#/" aria-label="Veil home">
      <Mark /> Veil
    </a>
  );
}
