/**
 * Export data to CSV file
 * @param {Array} data - Array of objects to export
 * @param {string} filename - Name of the CSV file
 * @param {Array} columns - Optional array of column configurations {key, header}
 */
export function exportToCSV(data, filename, columns = null) {
  if (!data || data.length === 0) {
    alert('No data to export');
    return;
  }

  // If columns not provided, use all keys from first object
  let headers, keys;
  if (columns) {
    headers = columns.map(col => col.header);
    keys = columns.map(col => col.key);
  } else {
    keys = Object.keys(data[0]);
    headers = keys;
  }

  // Create CSV header
  const csvHeader = headers.join(',');

  // Create CSV rows
  const csvRows = data.map(row => {
    return keys.map(key => {
      let value = row[key];
      
      // Handle null/undefined
      if (value === null || value === undefined) {
        return '';
      }
      
      // Convert to string and escape quotes
      value = String(value).replace(/"/g, '""');
      
      // Wrap in quotes if contains comma or newline
      if (value.includes(',') || value.includes('\n') || value.includes('"')) {
        return `"${value}"`;
      }
      
      return value;
    }).join(',');
  });

  // Combine header and rows
  const csv = [csvHeader, ...csvRows].join('\n');

  // Create blob and download
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', `${filename}.csv`);
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
