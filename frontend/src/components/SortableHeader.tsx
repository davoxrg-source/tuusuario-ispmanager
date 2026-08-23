export default function SortableHeader<F extends string>({
  field,
  label,
  sort,
  onClick,
}: {
  field: F;
  label: string;
  sort: { field: F; dir: "asc" | "desc" };
  onClick: (field: F) => void;
}) {
  const active = sort.field === field;
  return (
    <th className="px-4 py-2">
      <button
        onClick={() => onClick(field)}
        className={`flex items-center gap-1 hover:text-slate-800 ${active ? "text-slate-800 font-medium" : ""}`}
      >
        {label}
        <span className="text-slate-400">{active ? (sort.dir === "asc" ? "▲" : "▼") : "⇅"}</span>
      </button>
    </th>
  );
}
