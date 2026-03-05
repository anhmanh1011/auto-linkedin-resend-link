---
description: How to set up the project from scratch
---
// turbo-all

## Prerequisites
- Python 3.12+
- AdsPower browser running locally
- AdsPower API key

## Setup

1. Create virtual environment:
```bash
python3 -m venv /Users/talk_to_hand/.gemini/antigravity/scratch/automation-base/.venv
```

2. Install dependencies:
```bash
/Users/talk_to_hand/.gemini/antigravity/scratch/automation-base/.venv/bin/pip install httpx python-dotenv playwright
```

3. Create `.env` file with AdsPower config:
```
ADSPOWER_HOST=local.adspower.net
ADSPOWER_PORT=50325
ADSPOWER_API_KEY=your_api_key_here
```

4. Verify setup:
```bash
/Users/talk_to_hand/.gemini/antigravity/scratch/automation-base/.venv/bin/python test_run.py
```
