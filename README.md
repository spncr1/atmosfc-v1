# Atmos FC

Atmos FC analyses fan sentiment and reactions from comments on YouTube match highlight videos and visualises how crowd mood shifts in the hours following a football match. The aim is to turn thousands of raw reactions into a summarised analytcs chart, minute by minute, comment by comment.

## The problem

...

## Features

- 

## Tech Stack

- Backend: Python, FastAPI, Football-Data.org, YouTube Data API, VADER
- Frontend: vanilla HTML, CSS, JavaScript, Chart.js
- Backend deployment: Railway
- Frontend deployment: Vercel

## Limitations

- YouTube comment volume varies by match prominence i.e., Champions League and Premier League matches will have significantly more data than lower-profile fixtures
- Some videos have comments disabled; Atmos FC falls back to other available channels automatically
- Sentiment analysis reflects post-match rather than capturing the live mood in the stadium/venue that the match is pbeing played in
- Historical matches depend on highlight videos remaining publicly available
