import { Link } from 'react-router-dom'
import { formatDate } from '../utils.js'

export default function AllNewsCard({ article }) {
  const { id, headline, tags = [], source, research_theme, why_this_matters, published, source_url, image_url, summary = {} } = article
  const { hook, tldr } = summary

  const date = formatDate(published, { month: 'short', day: 'numeric', year: 'numeric' })

  const themeLabel = (research_theme || tags[0] || source).split(',')[0].trim()

  return (
    <div className="allcard">
      <div className="allcard__img-wrap">
        <img
          className="allcard__img"
          src={image_url}
          alt={headline}
          loading="lazy"
          width="400"
          height="225"
        />
      </div>

      <div className="allcard__header">
        <p className="allcard__category">{themeLabel}</p>
      </div>

      <Link className="allcard__headline" to={`/article/${id}`}>
        {headline}
      </Link>

      {why_this_matters && <p className="why-matters">{why_this_matters}</p>}
      {hook && <p className="allcard__digest">{hook}</p>}

      {tldr && <p className="allcard__tldr"><em>TL;DR: {tldr}</em></p>}

      <p className="allcard__footer">{source}{date ? ` · ${date}` : ''}</p>
    </div>
  )
}
