export default function AllNewsCard({ article }) {
  const { headline, digest, tags = [], source, published, source_url, image_url } = article

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
          onError={e => {
            e.target.src = 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800'
          }}
        />
      </div>
      <p className="allcard__category">{primaryTag}</p>
      <a
        className="allcard__headline"
        href={source_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {headline}
      </a>
      <p className="allcard__digest">{digest}</p>
      <p className="allcard__footer">{source}{date ? ` · ${date}` : ''}</p>
    </div>
  )
}
