import type { ExportFile } from './data';

/** Segmented control: opaque covers (default) or the natural export (fictional text re-rendered, OCR-audited). */
export function ExportToggle({ value, onChange }: { value: ExportFile; onChange: (v: ExportFile) => void }) {
  const opts: [ExportFile, string][] = [['output.mp4', 'Covers'], ['output_natural.mp4', 'Natural']];
  return (
    <div className="seg" role="radiogroup" aria-label="Export style">
      {opts.map(([v, label]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} className={value === v ? 'on' : ''} onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  );
}
