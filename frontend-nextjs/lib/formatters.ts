export function formatCurrency(amount?: number | null): string {
  if (amount === undefined || amount === null) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatTimeRemaining(endTime?: string | null): string {
  if (!endTime) return 'Unknown';
  const utcEndTime = endTime.includes('Z') || endTime.includes('+') ? endTime : endTime + 'Z';
  const end = new Date(utcEndTime);
  const now = new Date();
  const diff = end.getTime() - now.getTime();

  if (diff < 0) return 'Ended';

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function isEndingSoon(endTime?: string | null): boolean {
  if (!endTime) return false;
  const utcEndTime = endTime.includes('Z') || endTime.includes('+') ? endTime : endTime + 'Z';
  const end = new Date(utcEndTime);
  const now = new Date();
  const diff = end.getTime() - now.getTime();
  return diff > 0 && diff < 1000 * 60 * 60 * 24;
}

export function statusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-500/20 text-yellow-400',
    submitted: 'bg-blue-500/20 text-blue-400',
    active: 'bg-cyan-500/20 text-cyan-400',
    won: 'bg-green-500/20 text-green-400',
    lost: 'bg-red-500/20 text-red-400',
    error: 'bg-red-500/20 text-red-400',
    cancelled: 'bg-gray-500/20 text-gray-400',
    expired: 'bg-gray-500/20 text-gray-400',
  };
  return colors[status] || 'bg-gray-500/20 text-gray-400';
}
