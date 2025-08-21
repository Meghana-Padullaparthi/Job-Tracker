# DevOps Job Tracker

Flask app + MongoDB + SerpAPI to collect DevOps/SRE jobs (LinkedIn/Indeed/Glassdoor), store them, and view in a Bootstrap UI.

## Run locally
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scraper.py      # populate jobs
python app.py          # start the web app
