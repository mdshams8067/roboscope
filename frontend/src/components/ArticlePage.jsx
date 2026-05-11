import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { formatDate } from '../utils.js'

const BLOCK_COLORS = {
  problem:      { bg: '#FEF2F2', border: '#FCA5A5', icon: '⚠️' },
  limitation:   { bg: '#FFF7ED', border: '#FED7AA', icon: '🚧' },
  idea:         { bg: '#EFF6FF', border: '#93C5FD', icon: '💡' },
  method:       { bg: '#F0FDF4', border: '#86EFAC', icon: '⚙️' },
  data:         { bg: '#F5F3FF', border: '#C4B5FD', icon: '🗄️' },
  experiment:   { bg: '#ECFDF5', border: '#6EE7B7', icon: '🧪' },
  result:       { bg: '#FFFBEB', border: '#FCD34D', icon: '📊' },
  insight:      { bg: '#EFF6FF', border: '#60A5FA', icon: '🔍' },
  deployment:   { bg: '#F0FDF4', border: '#4ADE80', icon: '🚀' },
  impact:       { bg: '#FDF4FF', border: '#E879F9', icon: '🌍' },
  context:      { bg: '#F8FAFC', border: '#CBD5E1', icon: '📖' },
  announcement: { bg: '#EFF6FF', border: '#3B82F6', icon: '📢' },
  next:         { bg: '#F8FAFC', border: '#94A3B8', icon: '→'  },
}

const DEFAULT_COLOR = { bg: '#F8FAFC', border: '#CBD5E1', icon: '•' }

function FlowBlock({ block, isLast }) {
  const [expanded, setExpanded] = useState(false)
  const color = BLOCK_COLORS[block.type] ?? DEFAULT_COLOR

  return (
    <>
      <div
        className="flow-block"
        style={{ background: color.bg, borderColor: color.border }}
      >
        <div className="flow-block__type">
          <span className="flow-block__type-label">{block.type}</span>
        </div>

        <h3 className="flow-block__heading">{block.heading}</h3>
        <p className="flow-block__body">{block.body}</p>

        {block.has_number && block.number_callout && (
          <div className="flow-block__stat">{block.number_callout}</div>
        )}

        {block.detail && (
          <>
            <button
              className="flow-block__detail-btn"
              onClick={() => setExpanded(v => !v)}
            >
              {expanded ? '▾ Less detail' : '▸ More detail'}
            </button>
            {expanded && (
              <p className="flow-block__detail">{block.detail}</p>
            )}
          </>
        )}
      </div>

      {!isLast && <div className="flow-connector" />}
    </>
  )
}

export default function ArticlePage({ articles }) {
  const { id } = useParams()
  const article = articles.find(a => a.id === id)

  if (!article) {
    return (
      <div className="article-page">
        <div className="state">
          <h2>Article not found</h2>
          <Link to="/" className="article-page__back">← Back to feed</Link>
        </div>
      </div>
    )
  }

  const { headline, tags = [], source, published, source_url, image_url, flow } = article

  const date = formatDate(published)

  const readingTime = flow
    ? `~${Math.round(flow.reading_time_seconds / 60) || 1} min read`
    : null

  return (
    <div className="article-page">
      <div className="article-page__inner">

        {/* Back nav */}
        <Link to="/" className="article-page__back">← Back to feed</Link>

        {/* Hero image */}
        {image_url && (
          <div className="article-page__hero">
            <img src={image_url} alt={headline} width="800" height="450" fetchpriority="high" />
          </div>
        )}

        {/* Page header */}
        <div className="article-page__header">
          {tags.length > 0 && (
            <div className="article-page__tags">
              {tags.map(t => <span key={t} className="card__tag">{t}</span>)}
            </div>
          )}
          <h1 className="article-page__title">
            {flow?.flow_title || headline}
          </h1>
          <div className="article-page__meta">
            <span>{source}{date ? ` · ${date}` : ''}</span>
            {readingTime && <span className="article-page__readtime">{readingTime}</span>}
          </div>
        </div>

        {/* Flow diagram or fallback */}
        {!flow ? (
          <div className="flow-unavailable">
            <p>Full breakdown unavailable — read the original article.</p>
            <a href={source_url} target="_blank" rel="noopener noreferrer" className="article-page__source-btn">
              Read Original Article →
            </a>
          </div>
        ) : (
          <>
            {/* Prerequisite concepts */}
            {flow.prerequisite_concepts?.length > 0 && (
              <div className="flow-prereqs">
                <span className="flow-prereqs__label">You'll need to know:</span>
                {flow.prerequisite_concepts.map(c => (
                  <span key={c} className="flow-prereq-pill">{c}</span>
                ))}
              </div>
            )}

            {/* Flow blocks */}
            <div className="flow-diagram">
              {flow.blocks.map((block, i) => (
                <FlowBlock
                  key={block.id}
                  block={block}
                  isLast={i === flow.blocks.length - 1}
                />
              ))}
            </div>

            {/* Key takeaway */}
            {flow.key_takeaway && (
              <div className="flow-takeaway">
                <span className="flow-takeaway__label">Key takeaway</span>
                <p>{flow.key_takeaway}</p>
              </div>
            )}

            {/* Source link */}
            <div className="article-page__footer">
              <a href={source_url} target="_blank" rel="noopener noreferrer" className="article-page__source-btn">
                Read Original Article →
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
