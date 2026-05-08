import { Link } from 'react-router-dom'

export default function TrendingCard({ article }) {
  const { id, headline, tags = [], source, source_url } = article
  const primaryTag = tags[0] ?? source

  return (
    <div className="trending">
      <p className="trending__category">{primaryTag}</p>
      <Link className="trending__headline" to={`/article/${id}`}>
        {headline}
      </Link>
      <p className="trending__source">By {source}</p>
    </div>
  )
}
