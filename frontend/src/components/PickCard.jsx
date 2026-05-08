import { Link } from 'react-router-dom'

export default function PickCard({ article }) {
  const { id, headline, tags = [], source, source_url, image_url } = article
  const primaryTag = tags[0] ?? source

  return (
    <div className="pick">
      <img
        className="pick__img"
        src={image_url}
        alt={headline}
        loading="lazy"
      />
      <div className="pick__body">
        <p className="pick__category">{primaryTag}</p>
        <Link className="pick__headline" to={`/article/${id}`}>
          {headline}
        </Link>
        <p className="pick__source">{source}</p>
      </div>
    </div>
  )
}
