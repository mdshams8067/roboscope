const ALL_TAGS = [
  "All", "Humanoid", "Manipulation", "SLAM", "Legged",
  "Surgical", "Aerial", "Simulation", "Foundation Models", "Safety", "Industry",
]

export default function Header({ selectedTag, onTagChange, generatedAt }) {
  const date = generatedAt
    ? new Date(generatedAt).toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })
    : new Date().toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })

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
          {ALL_TAGS.map(tag => (
            <button
              key={tag}
              className={`nav__item ${(tag === 'All' ? !selectedTag : selectedTag === tag) ? 'nav__item--active' : ''}`}
              onClick={() => onTagChange(tag === 'All' ? null : tag)}
            >
              {tag}
            </button>
          ))}
        </div>
      </nav>
    </header>
  )
}
