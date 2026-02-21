import { TableHead } from '@/components/ui/table';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

export function SortableHeader({ label, sortKey, sortConfig, onSort, className = '' }) {
  const isActive = sortConfig.key === sortKey;
  return (
    <TableHead
      className={`cursor-pointer select-none hover:bg-muted/50 transition-colors ${className}`}
      onClick={() => onSort(sortKey)}
      data-testid={`sort-${sortKey}`}
    >
      <div className="flex items-center gap-0.5">
        <span className="truncate">{label}</span>
        {isActive ? (
          sortConfig.direction === 'asc' ? <ArrowUp className="h-3 w-3 shrink-0 text-primary" /> : <ArrowDown className="h-3 w-3 shrink-0 text-primary" />
        ) : (
          <ArrowUpDown className="h-3 w-3 shrink-0 opacity-30" />
        )}
      </div>
    </TableHead>
  );
}
