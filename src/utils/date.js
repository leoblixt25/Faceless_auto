export function formatDate(ts) {
  if (!ts) return ''
  const date = ts instanceof Date ? ts : ts.toDate ? ts.toDate() : new Date(ts)
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}
