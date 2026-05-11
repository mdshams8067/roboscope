import { useState, useRef, useEffect, useMemo, useCallback } from 'react'

const MAX_VISIBLE = 6

function useClickOutside(ref, onClose) {
  useEffect(() => {
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [ref, onClose])
}

function MoreDropdown({ tags, selectedTag, onTagChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const close = useCallback(() => setOpen(false), [])
  useClickOutside(ref, close)

  const hasActive = tags.some(t => t === selectedTag)

  return (
    <div className="nav__dropdown" ref={ref}>
      <button
        className={`nav__item nav__item--dropdown ${hasActive ? 'nav__item--active' : ''}`}
        onClick={() => setOpen(v => !v)}
      >
        {hasActive ? selectedTag : 'More'} ▾
      </button>
      {open && (
        <div className="nav__dropdown-menu">
          {tags.map(tag => (
            <button
              key={tag}
              className={`nav__dropdown-item ${selectedTag === tag ? 'nav__dropdown-item--active' : ''}`}
              onClick={() => { onTagChange(tag); setOpen(false) }}
            >
              {tag}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Header({ articles = [], selectedConference, onConferenceChange, generatedAt }) {
  const date = generatedAt
    ? new Date(generatedAt).toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })
    : new Date().toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })

  const sortedConfs = useMemo(() => {
    const counts = {}
    for (const a of articles) {
      if (a.source) counts[a.source] = (counts[a.source] ?? 0) + 1
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([conf]) => conf)
  }, [articles])

  const visibleConfs = sortedConfs.slice(0, MAX_VISIBLE)
  const overflowConfs = sortedConfs.slice(MAX_VISIBLE)

  return (
    <header>
      <div className="topbar">
        <span className="topbar__logo">
          Robo<span className="topbar__logo-accent">scope</span>
        </span>
        <span className="topbar__date">{date}</span>
      </div>

      <nav className="nav">
        <div className="nav__inner">
          {/* All + visible conferences */}
          <div className="nav__tags">
            <button
              className={`nav__item ${!selectedConference ? 'nav__item--active' : ''}`}
              onClick={() => onConferenceChange(null)}
            >
              All
            </button>
            {visibleConfs.map(conf => (
              <button
                key={conf}
                className={`nav__item ${selectedConference === conf ? 'nav__item--active' : ''}`}
                onClick={() => onConferenceChange(conf)}
              >
                {conf}
              </button>
            ))}
            {overflowConfs.length > 0 && (
              <MoreDropdown
                tags={overflowConfs}
                selectedTag={selectedConference}
                onTagChange={onConferenceChange}
              />
            )}
          </div>

        </div>
      </nav>
    </header>
  )
}
