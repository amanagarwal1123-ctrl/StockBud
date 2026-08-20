import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

export function buildPdf({ title, subtitle, rows }) {
  const doc = new jsPDF();
  doc.setFontSize(15);
  doc.setTextColor(30);
  doc.text(title, 14, 16);
  doc.setFontSize(9);
  doc.setTextColor(110);
  doc.text(subtitle, 14, 22);
  autoTable(doc, {
    startY: 27,
    head: [['S.No', 'Item Name', 'Order Qty (kg)', 'Current Stock (kg)']],
    body: rows,
    styles: { fontSize: 9, cellPadding: 2 },
    headStyles: { fillColor: [63, 81, 181], halign: 'left' },
    columnStyles: {
      0: { cellWidth: 16 },
      2: { halign: 'right', cellWidth: 34 },
      3: { halign: 'right', cellWidth: 40 },
    },
    alternateRowStyles: { fillColor: [245, 246, 250] },
  });
  return doc;
}

export async function sharePdf(doc, filename, title) {
  const blob = doc.output('blob');
  const file = new File([blob], filename, { type: 'application/pdf' });
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title });
      return 'shared';
    } catch (e) {
      if (e.name === 'AbortError') return 'aborted';
    }
  }
  doc.save(filename);
  return 'downloaded';
}
