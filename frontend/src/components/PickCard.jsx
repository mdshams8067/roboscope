import { Link } from 'react-router-dom'

export default function PickCard({ article }) {
  const { id, headline, tags = [], source, research_theme, image_url } = article
  const themeLabel = (research_theme || tags[0] || source).split(',')[0].trim()

  return (
    <div className="pick">
      <img
        className="pick__img"
        src={image_url}
        alt={headline}
        loading="lazy"
        width="160"
        height="90"
      />
      <div className="pick__body">
        <p className="pick__category">{themeLabel}</p>
        <Link className="pick__headline" to={`/article/${id}`}>
          {headline}
        </Link>
        <p className="pick__source">{source}</p>
      </div>
    </div>
  )
}
