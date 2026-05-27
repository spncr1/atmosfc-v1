# Atmos FC

Atmos FC analyses fan sentiment and online reaction around football matches by collecting YouTube comments from match highlight videos and turning them into a readable post-match snapshot. 

Users can search for finished fixtures, filter by competition and season, pick a match, and see how the mood shifted in the 24 hours after full time through a reaction intensity chart, top comments, match events, overall vibe labels, and crowd energy indicators. 

The aim is to turn thousands of scattered reactions into one centralised view of what a match felt like after the final whistle.

*Live version: https://atmosfc-v1.vercel.app/*

## The problem

Following football in the modern era can feel more emotionally taxing than ever, especially when more and more high-profile matches are creating multitudes of highlight reels, reaction clips, posts, replies, and comment sections across the many social media platforms people have access to. 

If a fan cannot watch the match live, whether because it is on late at night, they missed the broadcast, or they could not get to the game, it can be hard to get a proper feel for what actually happened without scrolling through thousands of comments online, all saying different things. 

Atmos FC is built to make that post-match catch-up easier for the average fan by bringing that reaction into one place, starting with YouTube comments, so users can quickly understand whether the game was exciting, disappointing, controversial, quiet, or genuinely memorable. By using VADER sentiment analysis and time-based comment bucketing in Python, the app focuses on the first 24 hours after full time, when the raw fan reaction is typically strongest.

## Features

- **Dashboard home page**
    - Search for finished football matches by team or fixture name
    - Browse recent matches from supported competitions
    - Filter by competition and season before choosing a match to analyse
- **Match search and filtering**
    - Search across the Premier League, La Liga, Bundesliga, Serie A, Ligue 1, and the UEFA Champions League
    - Filter results by competition and season from 2015/16 through to 2025/26
    - View match cards with team names, crests, scores, dates, rounds, and competition details
- **Match analysis page**
    - View a selected match with score, half-time score, competition, round, season, venue, and team crests where available
    - See key match events, including goals and cards, alongside the sentiment output
    - Review top liked YouTube comments with source links back to the original videos
- **Sentiment analysis**
    - Pull relevant YouTube highlight videos for a selected match and aggregate top-level comments across available sources
    - Analyse comments with VADER to calculate post-match sentiment and reaction intensity
    - Focus on the first 24 hours after full time to capture the strongest period of online fan reaction
- **Interactive visualisations**
    - Display a Chart.js reaction intensity graph for the 24 hours after full time
    - Show high and low reaction zones, peak reaction window, comment volume, and sentiment score
    - Surface summary labels such as overall vibe and crowd energy based on sentiment, volume, score margin, and late reaction shifts
- **Fallback handling**
    - Try multiple matching YouTube videos when comments are disabled or unavailable
    - Return clear empty and error states when match data, video comments, or analysis results cannot be loaded

## Tech Stack

- Backend: Python, FastAPI, Football-Data.org, YouTube Data API, VADER
- Frontend: vanilla HTML, CSS, JavaScript, Chart.js
- Backend deployment: Railway
- Frontend deployment: Vercel

## Running the Project locally

Clone the repository:

```bash
git clone https://github.com/spncr1/atmosfc-v1.git
cd atmosfc-v1
```

Install the frontend tooling:

```bash
npm install
```

Create a backend virtual environment and install the Python dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

Create `backend/.env` with the API keys required by the FastAPI service:

```bash
FOOTBALL_DATA_API_KEY=your_football_data_api_key_goes_here
YOUTUBE_API_KEY=your_youtube_api_key_goes_here
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Run the development server:

```bash
npm run dev
```

Then open the local frontend URL shown in the terminal.

## Limitations

- YouTube comment volume varies by match prominence, so Champions League and Premier League matches will usually have more usable data than lower-profile fixtures
- Sentiment analysis reflects the online post-match reaction rather than the live mood inside the stadium
- The current social media data source is YouTube, with other platforms to be added in the near future
- Historical matches depend on highlight videos and comments remaining publicly available, making it difficult to add data on those matches to the site
