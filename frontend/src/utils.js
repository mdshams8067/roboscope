/**
 * Formats a published date string for display.
 * Handles year-only strings (e.g. "2025") from OpenReview,
 * and full ISO dates (e.g. "2025-03-14") from arXiv.
 */
export function formatDate(published, opts = { month: 'long', day: 'numeric', year: 'numeric' }) {
  if (!published) return ''
  const s = String(published)
  if (/^\d{4}$/.test(s)) return s          // year-only → show "2025"
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleDateString('en-US', opts)
}
