import { useState, useMemo } from 'react';

export function useSortableData(data, defaultKey = null, defaultDir = 'desc') {
  const [sortConfig, setSortConfig] = useState({ key: defaultKey, direction: defaultDir });

  const sortedData = useMemo(() => {
    if (!sortConfig.key || !data) return data || [];
    return [...data].sort((a, b) => {
      let aVal = a[sortConfig.key];
      let bVal = b[sortConfig.key];
      // Handle strings case-insensitively
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();
      // Handle nulls/undefined
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  const requestSort = (key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc'
    }));
  };

  return { sortedData, sortConfig, requestSort };
}
