import { useState, useRef, useEffect } from 'react'

const MAX_VISIBLE = 6
const DIFFICULTIES = ['Accessible', 'Intermediate', 'Advanced']

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
  useClickOutside(ref, () => setOpen(false))

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

function DifficultyDropdown({ selected, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useClickOutside(ref, () => setOpen(false))

  return (
    <div className="nav__dropdown nav__dropdown--right" ref={ref}>
      <button
        className={`nav__item nav__item--dropdown ${selected ? 'nav__item--active' : ''}`}
        onClick={() => setOpen(v => !v)}
      >
        {selected || 'All levels'} ▾
      </button>
      {open && (
        <div className="nav__dropdown-menu nav__dropdown-menu--right">
          <button
            className={`nav__dropdown-item ${!selected ? 'nav__dropdown-item--active' : ''}`}
            onClick={() => { onChange(null); setOpen(false) }}
          >
            All levels
          </button>
          {DIFFICULTIES.map(d => (
            <button
              key={d}
              className={`nav__dropdown-item ${selected === d.toLowerCase() ? 'nav__dropdown-item--active' : ''}`}
              onClick={() => { onChange(d.toLowerCase()); setOpen(false) }}
            >
              {d}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Header({ articles = [], selectedTag, onTagChange, selectedDifficulty, onDifficultyChange, generatedAt }) {
  const date = generatedAt
    ? new Date(generatedAt).toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })
    : new Date().toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })

  // Derive tags from actual articles, sorted by frequency (most articles = most trendy)
  const tagCounts = {}
  for (const a of articles) {
    for (const t of (a.tags ?? [])) {
      tagCounts[t] = (tagCounts[t] ?? 0) + 1
    }
  }
  const sortedTags = Object.entries(tagCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([tag]) => tag)

  const visibleTags = sortedTags.slice(0, MAX_VISIBLE)
  const overflowTags = sortedTags.slice(MAX_VISIBLE)

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
          {/* All + visible tags */}
          <div className="nav__tags">
            <button
              className={`nav__item ${!selectedTag ? 'nav__item--active' : ''}`}
              onClick={() => onTagChange(null)}
            >
              All
            </button>
            {visibleTags.map(tag => (
              <button
                key={tag}
                className={`nav__item ${selectedTag === tag ? 'nav__item--active' : ''}`}
                onClick={() => onTagChange(tag)}
              >
                {tag}
              </button>
            ))}
            {overflowTags.length > 0 && (
              <MoreDropdown
                tags={overflowTags}
                selectedTag={selectedTag}
                onTagChange={onTagChange}
              />
            )}
          </div>

          {/* Difficulty filter — pushed to the right */}
          <DifficultyDropdown
            selected={selectedDifficulty}
            onChange={onDifficultyChange}
          />
        </div>
      </nav>
    </header>
  )
}
