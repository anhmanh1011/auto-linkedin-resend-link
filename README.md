# Auto LinkedIn Resend Link

Browser automation framework dùng AdsPower + Playwright + OmoCaptcha.

## Architecture

```
automation-base/
├── config.py              # Config (env + .env)
├── adspower_client.py     # AdsPower Local API client
├── base_flow.py           # BaseFlow — abstract class (user kế thừa)
├── engine.py              # FlowRunner — orchestration engine
├── main.py                # CLI entry point
├── flows/
│   └── login_flow.py      # LinkedIn password reset flow
├── test_run.py            # Config & client tests
└── .env                   # Secrets (gitignored)
```

## Quick Start

```bash
# Run flow (no args needed)
python main.py

# Keep profile after run
python main.py --keep

# Batch mode
python main.py --batch accounts.txt
```

## How It Works

1. **User viết Flow** — kế thừa `BaseFlow`, override `run(page)`
2. **Engine xử lý** — tạo profile AdsPower → mở browser → kết nối Playwright → chạy flow → cleanup
3. **CAPTCHA** — OmoCaptcha extension tự giải reCAPTCHA

## Current Flow: LinkedIn Password Reset

| Step | Action |
|------|--------|
| 0 | Set OmoCaptcha API key |
| 1 | Navigate to linkedin.com |
| 2 | Go to password reset page |
| 3 | Type email |
| 4 | Click submit |
| 5 | Wait for CAPTCHA solved (~20s) |
| 6 | Click resend link |

## Config

`.env` file:
```
ADSPOWER_HOST=local.adspower.net
ADSPOWER_PORT=50325
ADSPOWER_API_KEY=your_key
```

## Dependencies

- `httpx` — async HTTP client
- `python-dotenv` — env loading
- `playwright` — browser automation via CDP
