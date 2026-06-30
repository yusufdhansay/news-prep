import React, { useState, useEffect, useRef } from 'react';
import { 
  Newspaper, 
  FileText, 
  MessageSquare, 
  Bookmark, 
  Settings, 
  RefreshCw, 
  Search, 
  Award, 
  TrendingUp, 
  CheckCircle, 
  ChevronRight, 
  AlertCircle, 
  Eye, 
  BookOpen, 
  Send, 
  HelpCircle, 
  Lock,
  Calendar
} from 'lucide-react';

// Simple markdown renderer for AI output
const renderMarkdown = (text) => {
  if (!text) return null;
  const parseBold = (str) => {
    const parts = str.split(/\*\*(.*?)\*\*/g);
    return parts.map((part, index) => {
      if (index % 2 === 1) {
        return <strong key={index} style={{ color: 'var(--text-primary)' }}>{part}</strong>;
      }
      return part;
    });
  };

  return text.split('\n').map((line, idx) => {
    const trimmed = line.trim();
    if (!trimmed) return null;
    
    if (trimmed.startsWith('## ')) {
      return <h2 key={idx} style={{ color: 'var(--accent-primary)', fontSize: '1.3rem', marginTop: '1.5rem', marginBottom: '0.75rem', fontFamily: 'var(--font-display)', fontWeight: 700 }}>{parseBold(trimmed.substring(3))}</h2>;
    }
    if (trimmed.startsWith('# ')) {
      return <h1 key={idx} style={{ color: 'var(--text-primary)', fontSize: '1.7rem', marginTop: '1.5rem', marginBottom: '1rem', fontFamily: 'var(--font-display)', fontWeight: 800 }}>{parseBold(trimmed.substring(2))}</h1>;
    }
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      return <li key={idx} style={{ marginLeft: '1.5rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>{parseBold(trimmed.substring(2))}</li>;
    }
    if (trimmed.match(/^\d+\.\s/)) {
      const content = trimmed.replace(/^\d+\.\s/, '');
      return <li key={idx} style={{ marginLeft: '1.5rem', marginBottom: '0.5rem', listStyleType: 'decimal', color: 'var(--text-secondary)' }}>{parseBold(content)}</li>;
    }
    return <p key={idx} style={{ marginBottom: '1rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>{parseBold(trimmed)}</p>;
  });
};

export default function App() {
  // Get today's date formatted as YYYY-MM-DD
  const getTodayDateString = () => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const [activeTab, setActiveTab] = useState('dashboard');
  const [news, setNews] = useState([]);
  const [selectedArticle, setSelectedArticle] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDate, setSelectedDate] = useState(getTodayDateString());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isAutoRefreshing, setIsAutoRefreshing] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  
  // Daily Briefing state
  const [briefing, setBriefing] = useState('');
  const [isLoadingBriefing, setIsLoadingBriefing] = useState(false);
  
  // Mock Interview states
  const [interviewActive, setInterviewActive] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [answerInput, setAnswerInput] = useState('');
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  const [quizHistory, setQuizHistory] = useState([]);
  const [selectedHistorySession, setSelectedHistorySession] = useState(null);

  // Stats and System state
  const [stats, setStats] = useState({
    read_count: 0,
    total_count: 0,
    bookmark_count: 0,
    quiz_count: 0,
    avg_score: 0,
    streak: 0
  });
  const [apiConnected, setApiConnected] = useState(false);
  const [hasGroqKey, setHasGroqKey] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [apiKeySaved, setApiKeySaved] = useState(false);

  // Authentication states
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [authError, setAuthError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const saveSession = (newToken, newUser) => {
    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  };
  
  const clearSession = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken('');
    setUser(null);
  };

  const apiFetch = async (url, options = {}) => {
    const headers = options.headers || {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await window.fetch(url, {
      ...options,
      headers
    });
    if (res.status === 401) {
      clearSession();
    }
    return res;
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    if (!authEmail || !authPassword) {
      setAuthError('Please fill in all fields.');
      return;
    }
    setAuthError('');
    setIsAuthenticating(true);
    
    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const res = await window.fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      });
      
      const data = await res.json();
      if (res.ok) {
        saveSession(data.token, data.user);
        setAuthEmail('');
        setAuthPassword('');
      } else {
        setAuthError(data.detail || 'Authentication failed. Please try again.');
      }
    } catch (err) {
      setAuthError('Could not connect to server. Please try again later.');
    } finally {
      setIsAuthenticating(false);
    }
  };

  // Ask AI Chat states
  const [askAiOpen, setAskAiOpen] = useState(false);
  const [articleChatInput, setArticleChatInput] = useState('');
  const [articleChatHistory, setArticleChatHistory] = useState([]);
  const [isSubmittingArticleChat, setIsSubmittingArticleChat] = useState(false);

  const chatEndRef = useRef(null);

  // Fetch initial setup and health info
  useEffect(() => {
    checkHealth();
    if (token) {
      fetchStats();
      fetchNews();
      fetchQuizHistory();
    }
  }, [token]);

  // Popstate back button listening
  useEffect(() => {
    const handlePopState = (event) => {
      if (event.state && event.state.articleId) {
        fetchArticleAndSet(event.state.articleId);
      } else {
        setSelectedArticle(null);
        setAskAiOpen(false);
        setArticleChatHistory([]);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [news]);

  const fetchArticleAndSet = async (articleId) => {
    let art = news.find(n => n.id === articleId);
    if (art && art.summary && art.full_text) {
      setSelectedArticle(art);
      setAskAiOpen(false);
      return;
    }
    
    try {
      const body = art ? JSON.stringify({
        title: art.title,
        link: art.link,
        source: art.source,
        category: art.category,
        pub_date: art.pub_date
      }) : null;
      const res = await apiFetch(`/api/news/${articleId}/analyze`, { 
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body
      });
      if (res.ok) {
        const analyzed = await res.json();
        setSelectedArticle(analyzed);
        setAskAiOpen(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Sync scroll on chat messages update
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages]);

  const checkHealth = async () => {
    try {
      const res = await apiFetch('/api/health');
      if (res.ok) {
        const data = await res.json();
        setApiConnected(data.status === 'healthy');
        setHasGroqKey(data.has_groq_key);
      } else {
        setApiConnected(false);
      }
    } catch {
      setApiConnected(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await apiFetch('/api/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error("Error fetching stats:", e);
    }
  };

  // Validate date is in range 2026-01-01 to today
  const isValidDate = (dateStr) => {
    if (!dateStr || dateStr.length !== 10) return false;
    const match = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return false;
    const year = parseInt(match[1], 10);
    if (year < 2026 || year > new Date().getFullYear()) return false;
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return false;
    const today = getTodayDateString();
    return dateStr >= '2026-01-01' && dateStr <= today;
  };

  const handleDateChange = (e) => {
    const val = e.target.value;
    if (isValidDate(val)) {
      setSelectedDate(val);
    }
  };

  const fetchNews = async () => {
    // Guard: only fetch if selectedDate is valid
    if (!isValidDate(selectedDate)) return;

    try {
      const url = `/api/news?category=${encodeURIComponent(selectedCategory)}&search=${encodeURIComponent(searchQuery)}&date=${selectedDate}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setNews(data);
        
        // Auto-refresh if no news is cached for the selected date
        if (selectedDate && !isRefreshing && !isAutoRefreshing) {
          // Check if there are any articles at all for this date
          const checkUrl = `/api/news?category=all&date=${encodeURIComponent(selectedDate)}`;
          const checkRes = await apiFetch(checkUrl);
          if (checkRes.ok) {
            const checkData = await checkRes.json();
            if (checkData.length === 0) {
              setIsAutoRefreshing(true);
              try {
                const refreshUrl = `/api/news/refresh?date=${encodeURIComponent(selectedDate)}`;
                const refreshRes = await apiFetch(refreshUrl, { method: 'POST' });
                if (refreshRes.ok) {
                  // Re-fetch news with current filters
                  const reRes = await apiFetch(url);
                  if (reRes.ok) {
                    const reData = await reRes.json();
                    setNews(reData);
                  }
                  fetchStats();
                }
              } catch (e) {
                console.error("Auto-refresh failed:", e);
              } finally {
                setIsAutoRefreshing(false);
              }
            }
          }
        }

        // Retain selection if the active selection exists in the new list
        if (selectedArticle) {
          const updated = data.find(a => a.id === selectedArticle.id);
          if (updated) setSelectedArticle(updated);
        }
      }
    } catch (e) {
      console.error("Error fetching news:", e);
    }
  };

  // Re-run news fetch on filter/search/date change
  useEffect(() => {
    if (token) {
      fetchNews();
    }
  }, [selectedCategory, searchQuery, selectedDate, token]);

  const handleRefreshNews = async () => {
    setIsRefreshing(true);
    try {
      const url = `/api/news/refresh?date=${encodeURIComponent(selectedDate)}`;
      const res = await apiFetch(url, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        fetchNews();
        fetchStats();
        alert(`News updated! Ingested ${data.new_articles_count} new articles.`);
      }
    } catch (e) {
      console.error(e);
      alert("Failed to refresh news. Check your connection.");
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSelectArticle = async (article) => {
    if (!window.history.state || window.history.state.articleId !== article.id) {
      window.history.pushState({ articleId: article.id }, '', `#article-${article.id}`);
    }
    setSelectedArticle(article);
    setAskAiOpen(false);
    setArticleChatInput('');
    setArticleChatHistory([]);
    // Mark as read instantly if it wasn't read
    if (article.read_status === 0) {
      try {
        await apiFetch(`/api/news/${article.id}/read`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ read_status: true })
        });
        // Update local status
        setNews(prev => prev.map(n => n.id === article.id ? { ...n, read_status: 1 } : n));
        fetchStats();
      } catch (e) {
        console.error(e);
      }
    }
    
    // If not analyzed, run analysis automatically
    if (!article.summary || !article.financial_implications || !article.pi_questions) {
      setIsAnalyzing(true);
      try {
        const body = JSON.stringify({
          title: article.title,
          link: article.link,
          source: article.source,
          category: article.category,
          pub_date: article.pub_date
        });
        const res = await apiFetch(`/api/news/${article.id}/analyze`, { 
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: body
        });
        if (res.ok) {
          const analyzed = await res.json();
          setSelectedArticle(analyzed);
          setNews(prev => prev.map(n => n.id === article.id ? analyzed : n));
        } else {
          const err = await res.json();
          alert(`Analysis failed: ${err.detail || "Configure your Groq API key in Settings."}`);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setIsAnalyzing(false);
      }
    }
  };

  const handleToggleBookmark = async (e, article) => {
    e.stopPropagation();
    try {
      const res = await apiFetch(`/api/news/${article.id}/bookmark`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setNews(prev => prev.map(n => n.id === article.id ? { ...n, bookmarked: data.bookmarked ? 1 : 0 } : n));
        if (selectedArticle && selectedArticle.id === article.id) {
          setSelectedArticle(prev => ({ ...prev, bookmarked: data.bookmarked ? 1 : 0 }));
        }
        fetchStats();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleFetchBriefing = async () => {
    setIsLoadingBriefing(true);
    try {
      const res = await apiFetch('/api/daily-briefing');
      if (res.ok) {
        const data = await res.json();
        setBriefing(data.content);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoadingBriefing(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'briefing' && !briefing && token) {
      handleFetchBriefing();
    }
  }, [activeTab, token]);

  // Mock Interview operations
  const fetchQuizHistory = async () => {
    try {
      const res = await apiFetch('/api/quiz/history');
      if (res.ok) {
        const data = await res.json();
        setQuizHistory(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleStartInterview = async () => {
    setChatMessages([]);
    setSelectedHistorySession(null);
    setInterviewActive(true);
    setIsSubmittingAnswer(true);
    
    try {
      const res = await apiFetch('/api/quiz/start', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setCurrentSessionId(data.session_id);
        setChatMessages([{ role: 'panelist', content: data.message }]);
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to start interview. Ensure you have cached articles.");
        setInterviewActive(false);
      }
    } catch (e) {
      console.error(e);
      setInterviewActive(false);
    } finally {
      setIsSubmittingAnswer(false);
    }
  };

  const handleSubmitAnswer = async (e) => {
    e.preventDefault();
    if (!answerInput.trim() || isSubmittingAnswer) return;

    const userMsg = answerInput.trim();
    setAnswerInput('');
    setChatMessages(prev => [...prev, { role: 'candidate', content: userMsg }]);
    setIsSubmittingAnswer(true);

    try {
      const res = await apiFetch(`/api/quiz/${currentSessionId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: userMsg })
      });

      if (res.ok) {
        const data = await res.json();
        setChatMessages(data.qa_details);
        if (data.completed) {
          setInterviewActive(false);
          fetchStats();
          fetchQuizHistory();
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsSubmittingAnswer(false);
    }
  };

  const handleSaveApiKey = async (e) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) return;

    try {
      const res = await apiFetch('/api/settings/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput.trim() })
      });
      if (res.ok) {
        setApiKeySaved(true);
        setHasGroqKey(true);
        setApiKeyInput('');
        checkHealth();
        setTimeout(() => setApiKeySaved(false), 3000);
      }
    } catch (e) {
      console.error(e);
      alert("Failed to save API key.");
    }
  };

  const handleSendArticleChat = async (e) => {
    e.preventDefault();
    if (!articleChatInput.trim() || isSubmittingArticleChat) return;

    const query = articleChatInput.trim();
    setArticleChatInput('');
    setArticleChatHistory(prev => [...prev, { role: 'user', content: query }]);
    setIsSubmittingArticleChat(true);

    try {
      const res = await apiFetch(`/api/news/${selectedArticle.id}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          history: articleChatHistory
        })
      });

      if (res.ok) {
        const data = await res.json();
        setArticleChatHistory(prev => [...prev, { role: 'assistant', content: data.response }]);
      } else {
        alert("Failed to get response from AI. Please check your Groq API Key.");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmittingArticleChat(false);
    }
  };

  if (!token) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-logo">
              <Newspaper size={48} style={{ color: 'var(--accent-primary)' }} />
            </div>
            <h1 className="auth-title">MFin Prep</h1>
            <p className="auth-subtitle">JBIMS PI Current Affairs Portal</p>
          </div>

          <div className="auth-tabs">
            <button 
              className={`auth-tab-btn ${authMode === 'login' ? 'active' : ''}`}
              onClick={() => { setAuthMode('login'); setAuthError(''); }}
            >
              Sign In
            </button>
            <button 
              className={`auth-tab-btn ${authMode === 'register' ? 'active' : ''}`}
              onClick={() => { setAuthMode('register'); setAuthError(''); }}
            >
              Create Account
            </button>
          </div>

          <form className="auth-form" onSubmit={handleAuthSubmit}>
            <div className="auth-field">
              <label className="auth-label">Email Address</label>
              <input 
                type="email" 
                className="auth-input" 
                placeholder="you@domain.com"
                value={authEmail}
                onChange={e => setAuthEmail(e.target.value)}
                required
              />
            </div>

            <div className="auth-field">
              <label className="auth-label">Password</label>
              <input 
                type="password" 
                className="auth-input" 
                placeholder="••••••••"
                value={authPassword}
                onChange={e => setAuthPassword(e.target.value)}
                required
              />
            </div>

            {authError && (
              <div className="auth-error-msg">
                {authError}
              </div>
            )}

            <button type="submit" className="auth-btn-primary" disabled={isAuthenticating}>
              {isAuthenticating ? 'Processing...' : (authMode === 'login' ? 'Sign In' : 'Create Account')}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Mobile Header (visible only on mobile via CSS) */}
      <div className="mobile-header">
        <div className="logo-section" style={{ marginBottom: 0, paddingLeft: 0 }}>
          <div className="logo-icon">
            <Newspaper size={24} />
          </div>
          <div>
            <h1 className="logo-title" style={{ fontSize: '1.15rem' }}>MFin Prep</h1>
          </div>
        </div>
        <div className="connection-pill">
          <span className={`dot ${apiConnected ? 'connected' : 'disconnected'}`}></span>
        </div>
      </div>

      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-section">
          <div className="logo-icon">
            <Newspaper size={36} />
          </div>
          <div>
            <h1 className="logo-title">MFin Prep</h1>
            <p className="logo-subtitle">JBIMS PI Portal</p>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <ul className="sidebar-menu">
            <li 
              className={`menu-item ${activeTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => { setActiveTab('dashboard'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
              id="nav-dashboard"
            >
              <BookOpen size={18} />
              <span>Daily Feed</span>
            </li>
            <li 
              className={`menu-item ${activeTab === 'briefing' ? 'active' : ''}`}
              onClick={() => { setActiveTab('briefing'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
              id="nav-briefing"
            >
              <FileText size={18} />
              <span>Daily Briefing</span>
            </li>
            <li 
              className={`menu-item ${activeTab === 'bookmarks' ? 'active' : ''}`}
              onClick={() => { setActiveTab('bookmarks'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
              id="nav-bookmarks"
            >
              <Bookmark size={18} />
              <span>Revision Bank</span>
            </li>
            <li 
              className={`menu-item ${activeTab === 'settings' ? 'active' : ''}`}
              onClick={() => { setActiveTab('settings'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
              id="nav-settings"
            >
              <Settings size={18} />
              <span>Settings</span>
            </li>
          </ul>

          <div className="sidebar-footer">
            <div className="connection-pill">
              <span className={`dot ${apiConnected ? 'connected' : 'disconnected'}`}></span>
              <span>{apiConnected ? 'API Connected' : 'API Disconnected'}</span>
            </div>
            {!hasGroqKey && (
              <div style={{ color: 'var(--accent-rose)', fontSize: '0.75rem', marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Lock size={12} />
                <span>Configure Groq Key</span>
              </div>
            )}
            <button 
              onClick={clearSession} 
              style={{
                background: 'transparent',
                border: '1px solid var(--glass-border)',
                color: 'var(--text-secondary)',
                width: '100%',
                marginTop: '1.25rem',
                padding: '0.5rem 0.75rem',
                borderRadius: 'var(--border-radius-sm)',
                fontSize: '0.8rem',
                fontWeight: '500',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                transition: 'var(--transition-smooth)'
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(244, 63, 94, 0.4)'; e.currentTarget.style.color = 'var(--text-primary)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--glass-border)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
            >
              Sign Out
            </button>
          </div>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        
        {/* FULL SCREEN ARTICLE DETAIL VIEW */}
        {selectedArticle ? (
          <div className="full-detail-screen">
            {/* Header: Title, Metadata */}
            <div className="detail-header" style={{ marginBottom: '2rem' }}>
              <div className="detail-header-meta" style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.75rem', marginTop: '1rem' }}>
                <span style={{ textTransform: 'uppercase', fontWeight: 600, color: 'var(--accent-secondary)' }}>{selectedArticle.category}</span>
                <span>{selectedArticle.pub_date}</span>
              </div>
              
              <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '2rem', fontWeight: 700, lineHeight: 1.35, marginBottom: '1.25rem', color: 'var(--text-primary)' }}>
                {selectedArticle.title}
              </h1>
              
              <div className="detail-actions" style={{ display: 'flex', gap: '1rem' }}>
                <button 
                  className="btn-secondary"
                  onClick={(e) => handleToggleBookmark(e, selectedArticle)}
                  style={{ color: selectedArticle.bookmarked ? 'var(--accent-amber)' : 'inherit' }}
                >
                  <Bookmark size={16} fill={selectedArticle.bookmarked ? 'var(--accent-amber)' : 'none'} />
                  <span>{selectedArticle.bookmarked ? 'Saved in Revision Bank' : 'Save for Revision'}</span>
                </button>
                <a 
                  href={selectedArticle.link} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="btn-secondary" 
                  style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Eye size={16} />
                  <span>Read Source</span>
                </a>
                <button 
                  className="btn-primary"
                  onClick={() => setAskAiOpen(!askAiOpen)}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <MessageSquare size={16} />
                  <span>{askAiOpen ? 'Close Assistant' : 'Ask AI'}</span>
                </button>
              </div>
            </div>

            {/* Split Grid: Details on Left (60%/100%), Chat on Right (40%) */}
            <div className={`detail-split-grid ${askAiOpen ? 'has-chat' : ''}`}>
              
              {/* Left Column: implications & questions */}
              <div className="detail-panel" style={{ padding: '2.5rem', background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: 'var(--border-radius)', position: 'static' }}>
                {isAnalyzing ? (
                  <div className="loading-skeleton">
                    <div className="skeleton-text skeleton-title"></div>
                    <div className="skeleton-text"></div>
                    <div className="skeleton-text"></div>
                    <div className="skeleton-text" style={{ width: '80%' }}></div>
                  </div>
                ) : (
                  <div className="detail-body">
                    {/* News Summary */}
                    {selectedArticle.summary && (
                      <div className="detail-section" style={{ border: 'none', paddingTop: 0 }}>
                        <div className="section-label">
                          <FileText size={16} />
                          <span>Brief Summary</span>
                        </div>
                        <div className="section-content" style={{ color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                          {selectedArticle.summary}
                        </div>
                      </div>
                    )}

                    {selectedArticle.full_text && (
                      <div className="detail-section">
                        <div className="section-label">
                          <Newspaper size={16} />
                          <span>Full Article Content</span>
                        </div>
                        <div className="section-content" style={{ color: 'var(--text-secondary)', lineHeight: '1.7', whiteSpace: 'pre-wrap', maxHeight: '400px', overflowY: 'auto', background: 'rgba(255,255,255,0.01)', padding: '1.25rem', borderRadius: 'var(--border-radius-sm)', border: '1px solid var(--glass-border)' }}>
                          {selectedArticle.full_text}
                        </div>
                      </div>
                    )}

                    <div className="detail-section">
                      <div className="section-label">
                        <TrendingUp size={16} />
                        <span>MFin Economic Implications</span>
                      </div>
                      <div className="section-content">
                        <ul className="implications-list">
                          {selectedArticle.financial_implications?.map((imp, idx) => (
                            <li key={idx} className="implication-item">{imp}</li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    <div className="detail-section">
                      <div className="section-label">
                        <HelpCircle size={16} />
                        <span>JBIMS PI Questions</span>
                      </div>
                      <div className="section-content">
                        <div className="questions-list">
                          {selectedArticle.pi_questions?.map((item, idx) => (
                            <div key={idx} className="question-block" style={{ marginBottom: '1rem' }}>
                              <div className="pi-question-text" style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Q: {item.question}</div>
                              <div className="pi-answer-text" style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: '1.65', background: 'var(--bg-primary)', padding: '0.85rem 1rem', borderLeft: '3px solid var(--accent-emerald)', borderRadius: '0 6px 6px 0' }}>
                                <strong style={{ color: 'var(--accent-emerald)', display: 'block', marginBottom: '0.4rem', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Sample Answer:</strong>
                                {item.sample_answer || item.answer_pointers}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Right Column: Chat widget */}
              {askAiOpen && (
                <div className="chat-container">
                  <div className="chat-container-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.25rem', borderBottom: '1px solid var(--glass-border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                      <MessageSquare size={16} style={{ color: 'var(--accent-primary)' }} />
                      <span style={{ fontSize: '0.95rem' }}>Ask AI Assistant</span>
                    </div>
                    <button 
                      onClick={() => setAskAiOpen(false)}
                      style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center' }}
                      title="Close Chat"
                    >
                      <span style={{ fontSize: '1.25rem', fontWeight: 'bold', lineHeight: 1 }}>&times;</span>
                    </button>
                  </div>
                  <div className="chat-messages" style={{ padding: '1.25rem' }}>
                    <div className="message-wrapper panelist">
                      <div className="message-header">AI Assistant</div>
                      <div className="message-bubble">
                        Ask any questions or seek conceptual clarifications regarding **{selectedArticle.title}**. How can I help you?
                      </div>
                    </div>
                    {articleChatHistory.map((msg, idx) => (
                      <div key={idx} className={`message-wrapper ${msg.role === 'user' ? 'candidate' : 'panelist'}`}>
                        <div className="message-header">
                          {msg.role === 'user' ? 'You' : 'AI Assistant'}
                        </div>
                        <div className="message-bubble">
                          {msg.role === 'user' ? msg.content : renderMarkdown(msg.content)}
                        </div>
                      </div>
                    ))}
                    {isSubmittingArticleChat && (
                      <div className="message-wrapper panelist">
                        <div className="message-header">AI Assistant</div>
                        <div className="message-bubble loading-skeleton" style={{ width: '100px' }}>
                          Thinking...
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  <div className="chat-input-area">
                    <form onSubmit={handleSendArticleChat} className="chat-form">
                      <input 
                        type="text" 
                        className="chat-input"
                        placeholder="Ask about monetary impact, terms, etc..."
                        value={articleChatInput}
                        onChange={(e) => setArticleChatInput(e.target.value)}
                        disabled={isSubmittingArticleChat}
                      />
                      <button 
                        type="submit" 
                        className="chat-submit-btn"
                        disabled={isSubmittingArticleChat || !articleChatInput.trim()}
                      >
                        <Send size={18} />
                      </button>
                    </form>
                  </div>
                </div>
              )}

            </div>
          </div>
        ) : (
          <>
            {/* DASHBOARD SCREEN */}
            {activeTab === 'dashboard' && (
              <div>
                <header className="screen-header">
                  <div className="header-title-area">
                    <h1>Financial News Feed</h1>
                    <p>Curated news feeds for JBIMS MFin Personal Interview preparation</p>
                  </div>
                  <div className="header-actions" style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <div className="date-picker-container">
                      <Calendar size={16} className="date-picker-icon" />
                      <input 
                        type="date" 
                        className="date-picker-input" 
                        min="2026-01-01"
                        max={getTodayDateString()}
                        value={selectedDate}
                        onChange={handleDateChange}
                      />
                    </div>
                    <button 
                      className="btn-primary" 
                      onClick={handleRefreshNews}
                      disabled={isRefreshing || isAutoRefreshing}
                      id="btn-refresh-feed"
                    >
                      <RefreshCw size={16} className={(isRefreshing || isAutoRefreshing) ? 'loading-skeleton' : ''} />
                      <span>{(isRefreshing || isAutoRefreshing) ? 'Refreshing RSS...' : 'Refresh News'}</span>
                    </button>
                  </div>
                </header>

                {/* Filters and Search */}
                <div className="feed-controls">
                  <div className="category-tabs">
                    {['all', 'Finance & Banking', 'Markets', 'Geopolitics', 'Corporate & Economy'].map(cat => (
                      <button 
                        key={cat} 
                        className={`tab-chip ${selectedCategory === cat ? 'active' : ''}`}
                        onClick={() => setSelectedCategory(cat)}
                      >
                        {cat === 'all' ? 'All Categories' : cat}
                      </button>
                    ))}
                  </div>
                  <div className="search-box">
                    <Search size={16} className="search-icon" />
                    <input 
                      type="text" 
                      className="search-input" 
                      placeholder="Search articles..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>
                </div>

                {/* News Feed List (Full Width) */}
                <div className="news-list">
                  {news.length === 0 ? (
                    <div className="empty-state">
                      <Newspaper size={48} className="placeholder-icon" />
                      <h3>No Articles Found</h3>
                      <p>Try refreshing the feed or clearing your search term.</p>
                    </div>
                  ) : (
                    news.map(item => (
                      <article 
                        key={item.id} 
                        className={`news-card ${item.read_status === 0 ? 'unread' : ''}`}
                        onClick={() => handleSelectArticle(item)}
                      >
                        <div className="card-metadata">
                          <span className="card-category">{item.category}</span>
                          <span>{item.pub_date.split(' ')[0]}</span>
                        </div>
                        <h3 className="card-title">{item.title}</h3>
                        <div className="card-footer">
                          <span className="source-badge">{item.source}</span>
                          <div 
                            className={`bookmark-action ${item.bookmarked ? 'active' : ''}`}
                            onClick={(e) => handleToggleBookmark(e, item)}
                          >
                            <Bookmark size={16} />
                          </div>
                        </div>
                      </article>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* DAILY BRIEFING SCREEN */}
            {activeTab === 'briefing' && (
              <div>
                <header className="screen-header">
                  <div className="header-title-area">
                    <h1>MFin Daily Briefing</h1>
                    <p>Cohesive digest synthesizing today's key macroeconomic and market developments</p>
                  </div>
                  <button 
                    className="btn-primary" 
                    onClick={handleFetchBriefing} 
                    disabled={isLoadingBriefing}
                    id="btn-regenerate-briefing"
                  >
                    <RefreshCw size={16} className={isLoadingBriefing ? 'loading-skeleton' : ''} />
                    <span>{isLoadingBriefing ? 'Synthesizing...' : 'Regenerate Brief'}</span>
                  </button>
                </header>

                {isLoadingBriefing ? (
                  <div className="briefing-card text-center" style={{ padding: '5rem' }}>
                    <RefreshCw size={48} className="placeholder-icon loading-skeleton" />
                    <h2>Compiling daily financial digest...</h2>
                    <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>Connecting headlines and building conceptual MFin interview prep strategies.</p>
                  </div>
                ) : (
                  <article className="briefing-card">
                    <div className="briefing-content">
                      {briefing ? renderMarkdown(briefing) : (
                        <div className="text-center" style={{ color: 'var(--text-secondary)' }}>
                          <AlertCircle size={48} className="placeholder-icon" />
                          <p>No briefing content generated for today. Click the button above to synthesize one.</p>
                        </div>
                      )}
                    </div>
                  </article>
                )}
              </div>
            )}

            {/* REVISION BANK SCREEN */}
            {activeTab === 'bookmarks' && (
              <div>
                <header className="screen-header">
                  <div className="header-title-area">
                    <h1>Revision Bank</h1>
                    <p>Review articles and PI questions you saved for rapid revision before your actual interview</p>
                  </div>
                </header>

                {/* Filtered news items */}
                <div className="news-list">
                  {news.filter(n => n.bookmarked === 1).length === 0 ? (
                    <div className="empty-state">
                      <Bookmark size={48} className="placeholder-icon" />
                      <h3>No Saved Articles</h3>
                      <p>Select articles from the Daily Feed and save them to build your personal revision dashboard.</p>
                    </div>
                  ) : (
                    news.filter(n => n.bookmarked === 1).map(item => (
                      <article 
                        key={item.id} 
                        className="news-card"
                        onClick={() => handleSelectArticle(item)}
                      >
                        <div className="card-metadata">
                          <span className="card-category">{item.category}</span>
                          <span>{item.pub_date.split(' ')[0]}</span>
                        </div>
                        <h3 className="card-title">{item.title}</h3>
                        <div className="card-footer">
                          <span className="source-badge">{item.source}</span>
                          <div 
                            className="bookmark-action active"
                            onClick={(e) => handleToggleBookmark(e, item)}
                          >
                            <Bookmark size={16} />
                          </div>
                        </div>
                      </article>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* SETTINGS SCREEN */}
            {activeTab === 'settings' && (
              <div>
                <header className="screen-header">
                  <div className="header-title-area">
                    <h1>Settings Configuration</h1>
                    <p>Manage your access credentials and AI settings for news summary processing</p>
                  </div>
                </header>

                <div className="settings-container">
                  <form onSubmit={handleSaveApiKey}>
                    <div className="form-group">
                      <label htmlFor="api-key-input">Groq Cloud API Key</label>
                      <input 
                        type="password" 
                        id="api-key-input"
                        placeholder={hasGroqKey ? "••••••••••••••••••••••••••••••••" : "gsk_..."}
                        value={apiKeyInput}
                        onChange={(e) => setApiKeyInput(e.target.value)}
                      />
                      <small>
                        API keys are used locally to communicate with Groq LPU models. Get a free key at{' '}
                        <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>
                          console.groq.com
                        </a>.
                      </small>
                      {apiKeySaved && <div className="success-message">API Key Saved Successfully!</div>}
                    </div>

                    <div className="form-group">
                      <label>LLM Inference Model</label>
                      <input 
                        type="text" 
                        value="llama-3.3-70b-versatile (Active)" 
                        disabled 
                        style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)', cursor: 'not-allowed' }}
                      />
                      <small>Llama 3.3 70B Versatile is locked as the optimal model for financial reasoning and PI simulation.</small>
                    </div>

                    <div style={{ marginTop: '2rem' }}>
                      <button type="submit" className="btn-primary" disabled={!apiKeyInput.trim()} id="btn-save-settings">
                        Save Configuration
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </>
        )}

      </main>

      {/* Mobile Bottom Navigation Bar (visible only on mobile via CSS) */}
      <nav className="mobile-nav">
        <div 
          className={`mobile-nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => { setActiveTab('dashboard'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
          id="mobile-nav-dashboard"
        >
          <BookOpen size={20} />
          <span>Feed</span>
        </div>
        <div 
          className={`mobile-nav-item ${activeTab === 'briefing' ? 'active' : ''}`}
          onClick={() => { setActiveTab('briefing'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
          id="mobile-nav-briefing"
        >
          <FileText size={20} />
          <span>Briefing</span>
        </div>
        <div 
          className={`mobile-nav-item ${activeTab === 'bookmarks' ? 'active' : ''}`}
          onClick={() => { setActiveTab('bookmarks'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
          id="mobile-nav-bookmarks"
        >
          <Bookmark size={20} />
          <span>Revision</span>
        </div>
        <div 
          className={`mobile-nav-item ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => { setActiveTab('settings'); setSelectedArticle(null); window.history.pushState(null, '', '/'); }}
          id="mobile-nav-settings"
        >
          <Settings size={20} />
          <span>Settings</span>
        </div>
      </nav>
    </div>
  );
}
