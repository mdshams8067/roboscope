import { useState } from 'react'
import { Link } from 'react-router-dom'

const DIFFICULTY_LABEL = { accessible: 'Accessible', intermediate: 'Intermediate', advanced: 'Advanced' }

export default function FeaturedCard({ article }) {
  const [expanded, setExpanded] = useState(false)

  const {
    id, headline, tags = [], source,
    published, source_url, image_url, summary = {},
  } = article

  const {
    hook, what_it_does, result,
    key_idea, why_it_matters, student_note,
    difficulty = 'intermediate', tldr,
  } = summary

  const date = published
    ? new Date(published).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric',
      })
    : ''

  const primaryTag = tags[0] ?? source

  return (
    <article>
      <div className="featured__meta">
        <p className="featured__category">{primaryTag}</p>
        <span className={`difficulty-badge difficulty-badge--${difficulty}`}>
          {DIFFICULTY_LABEL[difficulty] ?? difficulty}
        </span>
      </div>

      <h1 className="featured__headline">
        <Link to={`/article/${id}`}>{headline}</Link>
      </h1>

      {hook && <p className="featured__hook">{hook}</p>}

      {what_it_does && <p className="featured__digest">{what_it_does}</p>}

      {result && (
        <div className="featured__result">
          <span className="featured__result-label">Key result</span>
          {result}
        </div>
      )}

      <div className="featured__img-wrap">
        <img
          className="featured__img"
          src={image_url}
          alt={headline}
          loading="eager"
        />
      </div>

      {(key_idea || why_it_matters || student_note) && (
        <div className="featured__expandable">
          <button
            className="expand-btn"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            {expanded ? 'Show less ↑' : 'Dig deeper ↓'}
          </button>
          {expanded && (
            <div className="expand-content">
              {key_idea && (
                <div className="expand-section">
                  <p className="expand-label">How it works</p>
                  <p>{key_idea}</p>
                </div>
              )}
              {why_it_matters && (
                <div className="expand-section">
                  <p className="expand-label">Why it matters</p>
                  <p>{why_it_matters}</p>
                </div>
              )}
              {student_note && (
                <div className="expand-section">
                  <p className="expand-label">Student note</p>
                  <p>{student_note}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tldr && <p className="featured__tldr"><em>TL;DR: {tldr}</em></p>}

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
