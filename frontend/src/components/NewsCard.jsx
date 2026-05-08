export default function NewsCard({ article }) {
  const {
    headline, digest, tags = [], source, published,
    source_url, image_url, image_is_fallback,
  } = article

  const date = published
    ? new Date(published).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : ''

  return (
    <article className="card">
      <div className="card__image-wrap">
        <img
          className="card__image"
          src={image_url}
          alt={headline}
          loading="lazy"
          onError={e => { e.target.src = 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800' }}
        />
        {image_is_fallback && (
          <span className="card__fallback-badge">stock photo</span>
        )}
      </div>

      <div className="card__body">
        {tags.length > 0 && (
          <div className="card__tags">
            {tags.map(tag => (
              <span key={tag} className="card__tag">{tag}</span>
            ))}
          </div>
        )}

        <h2 className="card__headline">{headline}</h2>
        <p className="card__digest">{digest}</p>

        <div className="card__footer">
          <div className="card__source-info">
            <strong>{source}</strong>
            {date && <> · {date}</>}
          </div>
          <a
            className="card__read-link"
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Read Article →
          </a>
        </div>
      </div>
    </article>
  )
}
