import { Link } from 'react-router-dom'

const DIFFICULTY_LABEL = { accessible: 'Accessible', intermediate: 'Intermediate', advanced: 'Advanced' }

export default function AllNewsCard({ article }) {
  const { id, headline, tags = [], source, published, source_url, image_url, summary = {} } = article
  const { hook, tldr, difficulty = 'intermediate' } = summary

  const date = published
    ? new Date(published).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
      })
    : ''

  const primaryTag = tags[0] ?? source

  return (
    <div className="allcard">
      <div className="allcard__img-wrap">
        <img
          className="allcard__img"
          src={image_url}
          alt={headline}
          loading="lazy"
        />
      </div>

      <div className="allcard__header">
        <p className="allcard__category">{primaryTag}</p>
        <span className={`difficulty-badge difficulty-badge--${difficulty}`}>
          {DIFFICULTY_LABEL[difficulty] ?? difficulty}
        </span>
      </div>

      <Link className="allcard__headline" to={`/article/${id}`}>
        {headline}
      </Link>

      {hook && <p className="allcard__digest">{hook}</p>}

      {tldr && <p className="allcard__tldr"><em>TL;DR: {tldr}</em></p>}

      <p className="allcard__footer">{source}{date ? ` · ${date}` : ''}</p>
    </div>
  )
}
