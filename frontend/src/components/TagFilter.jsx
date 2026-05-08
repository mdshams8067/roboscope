const ALL_TAGS = [
  "Humanoid", "Manipulation", "SLAM", "Legged", "Surgical",
  "Aerial", "Simulation", "Foundation Models", "Safety", "Industry",
]

export default function TagFilter({ selected, onChange }) {
  function toggle(tag) {
    if (selected.includes(tag)) {
      onChange(selected.filter(t => t !== tag))
    } else {
      onChange([...selected, tag])
    }
  }

  return (
    <div className="tag-filter">
      <button
        className={`tag-filter__pill ${selected.length === 0 ? 'tag-filter__pill--active' : ''}`}
        onClick={() => onChange([])}
      >
        All
      </button>
      {ALL_TAGS.map(tag => (
        <button
          key={tag}
          className={`tag-filter__pill ${selected.includes(tag) ? 'tag-filter__pill--active' : ''}`}
          onClick={() => toggle(tag)}
        >
          {tag}
        </button>
      ))}
    </div>
  )
}
