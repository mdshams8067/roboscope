export default function FeaturedCard({ article }) {
  const {
    headline, digest, tags = [], source,
    published, source_url, image_url,
  } = article

  const date = published
    ? new Date(published).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric',
      })
    : ''

  const primaryTag = tags[0] ?? source

  return (
    <article>
      <p className="featured__category">{primaryTag}</p>

      <h1 className="featured__headline">
        <a href={source_url} target="_blank" rel="noopener noreferrer">
          {headline}
        </a>
      </h1>

      <p className="featured__digest">{digest}</p>

      <div className="featured__img-wrap">
        <img
          className="featured__img"
          src={image_url}
          alt={headline}
          loading="eager"
          onError={e => {
            e.target.src = 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800'
          }}
        />
      </div>

      <div className="featured__footer">
        <span className="featured__source">
          {source}{date ? ` · ${date}` : ''}
        </span>
        <a
          className="featured__link"
          href={source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Read Full Article
        </a>
      </div>
    </article>
  )
}
