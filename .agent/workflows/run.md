---
description: How to run the automation flow
---
// turbo-all

## Run Flow

1. Activate venv and run:
```bash
/Users/talk_to_hand/.gemini/antigravity/scratch/automation-base/.venv/bin/python main.py
```

2. Run with keep profile (don't delete after run):
```bash
/Users/talk_to_hand/.gemini/antigravity/scratch/automation-base/.venv/bin/python main.py --keep
```

3. Run batch with accounts file:
```bash
/Users/talk_to_hand/.gemini/antigravity/scratch/automation-base/.venv/bin/python main.py --batch accounts.txt
```

## Account File Format
```
email1@mail.com|password1
email2@mail.com|password2
```
