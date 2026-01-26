/**
 * Format number in Indian currency system (Lakh/Crore)
 * @param {number} amount - Amount to format
 * @returns {string} - Formatted string like ₹1.5L or ₹2.3Cr
 */
export function formatIndianCurrency(amount) {
  if (!amount || amount === 0) return '₹0';
  
  const absAmount = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';
  
  if (absAmount >= 10000000) {
    // Crores (1 Cr = 1,00,00,000)
    return `${sign}₹${(absAmount / 10000000).toFixed(2)}Cr`;
  } else if (absAmount >= 100000) {
    // Lakhs (1 L = 1,00,000)
    return `${sign}₹${(absAmount / 100000).toFixed(2)}L`;
  } else if (absAmount >= 1000) {
    // Thousands
    return `${sign}₹${(absAmount / 1000).toFixed(2)}K`;
  } else {
    return `${sign}₹${absAmount.toFixed(0)}`;
  }
}
