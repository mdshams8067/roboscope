import { Link } from 'react-router-dom'

export default function TrendingCard({ article }) {
  const { id, headline, tags = [], source, research_theme } = article
  const themeLabel = (research_theme || tags[0] || source).split(',')[0].trim()

  return (
    <div className="trending">
      <p className="trending__category">{themeLabel}</p>
      <Link className="trending__headline" to={`/article/${id}`}>
        {headline}
      </Link>
      <p className="trending__source">By {source}</p>
    </div>
  )
}
