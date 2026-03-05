---
description: How to add a new automation flow
---

## Add New Flow

1. Create new file in `flows/` directory, e.g. `flows/my_flow.py`:

```python
from base_flow import BaseFlow
from playwright.async_api import Page

class MyFlow(BaseFlow):
    flow_name = "my_flow"

    async def run(self, page: Page):
        # Step 0: Set CAPTCHA key (if needed)
        await page.goto("https://omocaptcha.com/set-key/?api_key=YOUR_KEY")
        await self.wait(2, 3)

        # Step 1: Your automation logic
        await page.goto("https://example.com")
        await self.human_type("#input", self.account["email"])
        await self.safe_click("#submit")
        await self.screenshot("done")
        return {"status": "ok"}
```

2. Import the new flow in `main.py`:

```python
from flows.my_flow import MyFlow
```

3. Update `main.py` to use the new flow class in the `run()` function.

## Available Helpers in BaseFlow

| Method | Description |
|--------|-------------|
| `self.screenshot("name")` | Save screenshot |
| `self.wait(min, max)` | Random delay |
| `self.human_type("#sel", "text")` | Type like human |
| `self.safe_click("#sel")` | Click, wait for element first |
| `self.log("msg")` | Log message |
| `self.account` | Account data dict |
| `self.profile_id` | AdsPower profile ID |

## Optional Hooks
- `setup(page)` — runs before `run()`
- `teardown(page)` — runs after `run()`
- `on_error(error, page)` — runs on failure
