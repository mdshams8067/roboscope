export default function TrendingCard({ article }) {
  const { headline, tags = [], source, source_url } = article
  const primaryTag = tags[0] ?? source

  return (
    <div className="trending">
      <p className="trending__category">{primaryTag}</p>
      <a
        className="trending__headline"
        href={source_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {headline}
      </a>
      <p className="trending__source">By {source}</p>
    </div>
  )
}
