import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDate } from '../utils.js'

export default function FeaturedCard({ article }) {
  const [expanded, setExpanded] = useState(false)

  const {
    id, headline, tags = [], source, research_theme, why_this_matters,
    published, source_url, image_url, summary = {},
  } = article

  const {
    hook, what_it_does, key_idea,
    core_challenge, key_assumption,
    result, what_it_enables, open_source, tldr,
  } = summary

  const date = formatDate(published)

  const themeLabel = (research_theme || tags[0] || source).split(',')[0].trim()

  return (
    <article>
      <div className="featured__meta">
        <p className="featured__category">{themeLabel}</p>
      </div>

      <h1 className="featured__headline">
        <Link to={`/article/${id}`}>{headline}</Link>
      </h1>

      {why_this_matters && <p className="why-matters">{why_this_matters}</p>}

      {hook && <p className="featured__hook">{hook}</p>}

      {what_it_does && <p className="featured__digest">{what_it_does}</p>}

      {result && (
        <div className="featured__result">
          <span className="featured__result-label">Key result</span>
          {result}
        </div>
      )}

      {what_it_enables && (
        <div className="featured__enables">
          <span className="featured__enables-label">What this opens up</span>
          {what_it_enables}
        </div>
      )}

      <div className="featured__img-wrap">
        <img
          className="featured__img"
          src={image_url}
          alt={headline}
          loading="eager"
          fetchpriority="high"
          width="800"
          height="450"
        />
      </div>

      {(key_idea || core_challenge || key_assumption) && (
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
              {(core_challenge || key_assumption) && (
                <div className="expand-section">
                  <p className="expand-label">Research context</p>
                  {core_challenge && <p>{core_challenge}</p>}
                  {key_assumption && <p>{key_assumption}</p>}
                </div>
              )}
              {open_source && (
                <div className="expand-section">
                  <p className="expand-label">Open source</p>
                  <a href={open_source.startsWith('http') ? open_source : `https://${open_source}`}
                     target="_blank" rel="noopener noreferrer"
                     className="featured__opensource-link">
                    {open_source}
                  </a>
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
