export function StatCard({
  label,
  value,
  subValue,
  className = "",
}: {
  label: string;
  value: string | number;
  subValue?: string;
  className?: string;
}) {
  return (
    <div className={`bg-surface-2 border border-surface-4 rounded-lg p-4 ${className}`}>
      <p className="text-xs text-neutral-500 uppercase tracking-wider">{label}</p>
      <p className="mt-1 text-2xl font-mono font-semibold text-neutral-100">
        {value}
      </p>
      {subValue && (
        <p className="mt-0.5 text-xs text-neutral-500">{subValue}</p>
      )}
    </div>
  );
}
