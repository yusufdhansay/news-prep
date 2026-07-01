# MFin & MHRD MBA Preparation Platform

A premium, high-performance news aggregation and preparation platform designed specifically for students preparing for the prestigious **JBIMS MFin (Master of Finance)** and **JBIMS MHRD (Master of Human Resource Development)** programs. 

The platform delivers high-quality, targeted news briefs, financial deal flows, labor reform updates, and daily briefings to help students ace their entrances, group discussions, and personal interviews.

---

## 🚀 Key Features

* **Categorized News Aggregator**: Automatically aggregates news across six highly relevant categories:
  * **Finance & Banking**: RBI policies, monetary policy updates, NBFC regulations, and banking indicators.
  * **Markets**: Sensex/Nifty trends, corporate earnings, IPO listings, and market analysis.
  * **Geopolitics**: Global trade, tariff updates, US Federal Reserve policy, and bilateral trade relations.
  * **Corporate & Economy**: Startup funding, PE/VC investments, Mergers & Acquisitions (M&A), and GDP metrics.
  * **Current Affairs**: Major national policy changes, Supreme Court rulings, and government schemes.
  * **MHRD**: Labor laws, trade unions, hiring trends, salary structures, gig economy updates, and EPFO directives.
* **Smart Content Filtering**: A customized post-fetch filter automatically cleanses the RSS feed by removing Moneycontrol forum boards, image assets, photo galleries, listicles, empty summaries, and generic main landing pages.
* **Daily Briefings**: Curated and summarized daily briefs helping students capture all key headlines in a single 2-minute read.
* **Persistent Sessions**: "Keep me signed in" authentication option utilizing local storage token management.
* **FastAPI Backend**: Clean asynchronous endpoints, SQL query emulation for cross-database compatibility (Postgres/SQLite), JWT token authentication, and secure password hashing.
* **Vibrant UI/UX**: Premium dark mode design built with Vanilla CSS and responsive grid layouts.

---

## 🛠️ Technology Stack

* **Frontend**: React (v19), Vite, Lucide React (Icons)
* **Backend**: FastAPI (Python), Uvicorn, BeautifulSoup4 (Scraping), PyJWT, Bcrypt
* **Database**: PostgreSQL (Production) / SQLite (Local Development)
* **Hosting**: Vercel (Serverless Backend Functions + Static Frontend)

---

## 📁 Repository Structure

```text
├── backend/
│   ├── database.py       # DB connection pool and SQLite/Postgres emulation layer
│   ├── main.py           # FastAPI application endpoints and routing
│   ├── news_fetcher.py   # Google News RSS fetcher and post-fetch filters
│   └── mfin_news.db      # Local development SQLite database
├── src/                  # React Frontend source
│   ├── components/       # Shared UI components (News Cards, Navigation, etc.)
│   ├── App.jsx           # Main application shell and routing
│   └── index.css         # Styling system (glassmorphism & dark palette)
├── public/               # Static assets
├── requirements.txt      # Python dependencies
├── package.json          # Node dependencies and build scripts
├── vercel.json           # Vercel serverless functions configuration
└── vite.config.js        # Vite bundler configurations
```

---

## ⚙️ Local Development Setup

### 1. Backend Setup
1. Navigate to the project root and create a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your local environment variables. Create a `.env` file in the root directory:
   ```env
   # Leave empty to fall back to local SQLite database (backend/mfin_news.db)
   DATABASE_URL=
   JWT_SECRET=your_jwt_secret_key_here
   ```
4. Start the FastAPI development server:
   ```bash
   python3 -m backend.main
   # Or using uvicorn directly:
   # uvicorn backend.main:app --reload --port 8000
   ```
   The backend API will be available at `http://127.0.0.1:8000`.

### 2. Frontend Setup
1. In a separate terminal tab, install Node dependencies:
   ```bash
   npm install
   ```
2. Start the Vite frontend server:
   ```bash
   npm run dev
   ```
   The application dashboard will be accessible at `http://localhost:5173`.

---

## ☁️ Production Deployment

The project is structured to deploy out-of-the-box on **Vercel** with integrated FastAPI serverless routes:

1. Install the Vercel CLI:
   ```bash
   npm install -g vercel
   ```
2. Log in and link your project:
   ```bash
   vercel login
   vercel link
   ```
3. Deploy to production:
   ```bash
   vercel --prod
   ```
4. Configure production environment variables (`DATABASE_URL`, `JWT_SECRET`) in your Vercel Dashboard.
