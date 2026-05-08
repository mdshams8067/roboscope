export default function PickCard({ article }) {
  const { headline, tags = [], source, source_url, image_url } = article
  const primaryTag = tags[0] ?? source

  return (
    <div className="pick">
      <img
        className="pick__img"
        src={image_url}
        alt={headline}
        loading="lazy"
        onError={e => {
          e.target.src = 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800'
        }}
      />
      <div className="pick__body">
        <p className="pick__category">{primaryTag}</p>
        <a
          className="pick__headline"
          href={source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {headline}
        </a>
        <p className="pick__source">{source}</p>
      </div>
    </div>
  )
}
