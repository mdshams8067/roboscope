import { useEffect, useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import Header from './components/Header.jsx'
import FeaturedCard from './components/FeaturedCard.jsx'
import PickCard from './components/PickCard.jsx'
import TrendingCard from './components/TrendingCard.jsx'
import AllNewsCard from './components/AllNewsCard.jsx'
import ArticlePage from './components/ArticlePage.jsx'

const ALLNEWS_INITIAL = 3

function Feed({ feed, selectedTag, onTagChange, selectedDifficulty, onDifficultyChange }) {
  const [showAllNews, setShowAllNews] = useState(false)
  useEffect(() => { setShowAllNews(false) }, [selectedTag, selectedDifficulty])

  const all = feed.articles ?? []
  const articles = all.filter(a => {
    const tagMatch = !selectedTag || a.tags?.includes(selectedTag)
    const diffMatch = !selectedDifficulty || a.summary?.difficulty === selectedDifficulty
    return tagMatch && diffMatch
  })

  const featured = articles[0] ?? null
  const picks    = articles.slice(1, 5)
  const trending = articles.slice(5)
  const visibleAllNews = showAllNews ? articles : articles.slice(0, ALLNEWS_INITIAL)
  const hasMore = articles.length > ALLNEWS_INITIAL && !showAllNews

  return (
    <>
      <Header
        articles={all}
        selectedTag={selectedTag}
        onTagChange={onTagChange}
        selectedDifficulty={selectedDifficulty}
        onDifficultyChange={onDifficultyChange}
        generatedAt={feed.generated_at}
      />
      <div className="page">
        {!featured ? (
          <div className="state">
            <h2>No articles</h2>
            <p>Try a different tag, or check back after the next pipeline run.</p>
          </div>
        ) : (
          <>
            <div className="columns">
              <aside className="col-picks">
                <div className="section-label">Latest News</div>
                {picks.length === 0
                  ? <p style={{ fontSize: '0.78rem', color: '#aaa' }}>No other articles.</p>
                  : picks.map(a => <PickCard key={a.id} article={a} />)
                }
              </aside>

              <section className="col-featured">
                <FeaturedCard article={featured} />
              </section>

              <aside className="col-trending">
                <div className="section-label">Trending News</div>
                {trending.length === 0
                  ? <p style={{ fontSize: '0.78rem', color: '#aaa' }}>More news soon.</p>
                  : trending.map(a => <TrendingCard key={a.id} article={a} />)
                }
              </aside>
            </div>

            <div className="all-news">
              <div className="section-label">All News</div>
              <div className="all-news__grid">
                {visibleAllNews.map(a => (
                  <AllNewsCard key={a.id} article={a} />
                ))}
              </div>
              {hasMore && (
                <div className="all-news__more">
                  <button className="read-more-btn" onClick={() => setShowAllNews(true)}>
                    Read More ({articles.length - ALLNEWS_INITIAL} more)
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}

export default function App() {
  const [feed, setFeed] = useState(null)
  const [selectedTag, setSelectedTag] = useState(null)
  const [selectedDifficulty, setSelectedDifficulty] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/feed.json')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(setFeed)
      .catch(err => setError(err.message))
  }, [])

  if (error) return <div className="state"><h2>Could not load feed</h2><p>{error}</p></div>
  if (!feed)  return <div className="state"><div className="spinner" /><p>Loading…</p></div>

  return (
    <Routes>
      <Route
        path="/"
        element={
          <Feed
            feed={feed}
            selectedTag={selectedTag}
            onTagChange={setSelectedTag}
            selectedDifficulty={selectedDifficulty}
            onDifficultyChange={setSelectedDifficulty}
          />
        }
      />
      <Route
        path="/article/:id"
        element={<ArticlePage articles={feed.articles ?? []} />}
      />
    </Routes>
  )
}
