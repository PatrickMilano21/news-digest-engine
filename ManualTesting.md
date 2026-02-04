# Manual Testing Guide — Suggestions UI

**Last updated:** 2026-02-04
**Tested by:** Patrick
**User ID:** `c17d5f85-31cc-4553-99e1-d9ab69462f3a`
**Email:** `patrick@example.com`
**Password:** `password123`

---

## Quick Start for Tomorrow (2026-02-05)

Run these commands in order, then follow the test checklist below:

```powershell
# 1. Delete old fixture items (same URLs would duplicate)
python -c "from src.db import get_conn, init_db; conn = get_conn(); init_db(conn); r = conn.execute(\"DELETE FROM news_items WHERE url LIKE 'https://fixture.example.com/%%'\"); conn.commit(); print(f'Deleted {r.rowcount} fixture items'); conn.close()"

# 2. Seed today's fixture data (items will have 2026-02-05 dates)
python -m jobs.daily_run --date 2026-02-05 --mode fixtures --force --user-id c17d5f85-31cc-4553-99e1-d9ab69462f3a

# 3. Start dev server
make dev

# 4. Log in via browser console (F12 → Console) on http://localhost:8001/
fetch('/auth/login?email=patrick@example.com&password=password123', {method:'POST'}).then(r=>r.json()).then(d=>{console.log(d); location.reload()})

# 5. Rate a few articles on the home page (Useful / Not useful)

# 6. Navigate to http://localhost:8001/ui/suggestions and run through the test checklist
```

---

## Prerequisites

### 1. Start the Dev Server

```powershell
make dev
```

Server runs at `http://localhost:8001/`. If you get a port conflict, kill existing processes first:

```powershell
taskkill /f /im python.exe
make dev
```

> **Windows note:** Uvicorn's `--reload` sometimes misses file changes on Windows. If routes return 404 unexpectedly, restart the server.

### 2. Seed Fixture Data for Today's Date

The fixture XML has hardcoded dates that won't match today. The fixture loader now overrides `published_at` to match `--date`, so just run:

```powershell
python -m jobs.daily_run --date 2026-02-05 --mode fixtures --force --user-id c17d5f85-31cc-4553-99e1-d9ab69462f3a
```

> **Important:** Always pass `--user-id` so the run record is scoped to your user. Without it, the home page will show articles but feedback buttons won't appear.

> **If you see `inserted: 0, duplicates: 5`:** The fixture URLs already exist in the DB. Delete old fixture items first:
> ```powershell
> python -c "from src.db import get_conn, init_db; conn = get_conn(); init_db(conn); r = conn.execute(\"DELETE FROM news_items WHERE url LIKE 'https://fixture.example.com/%%'\"); conn.commit(); print(f'Deleted {r.rowcount} fixture items'); conn.close()"
> ```
> Then re-run the daily_run command above.

### 3. Verify Home Page

Navigate to `http://localhost:8001/`. It should redirect to `/ui/date/2026-02-05` (or whatever date you used) with 5 articles and feedback buttons.

### 4. Log In (if not already)

The user account was created on 2026-02-04. If the session cookie has expired (24h), log in again:

1. Open browser to `http://localhost:8001/`
2. Press **F12** → **Console** tab
3. Paste and run:

```javascript
fetch('/auth/login?email=patrick@example.com&password=password123', {method:'POST'}).then(r=>r.json()).then(d=>{console.log(d); location.reload()})
```

> **If the user doesn't exist** (fresh DB), create it first:
> ```powershell
> python -c "from src.db import get_conn, init_db; from src.auth import hash_password; from src.repo import create_user; conn = get_conn(); init_db(conn); uid = create_user(conn, email='patrick@example.com', password_hash=hash_password('password123')); conn.close(); print(f'Created user {uid}')"
> ```
> Note: The user ID will be different from the one in this doc. Update the `--user-id` in all commands accordingly.

### 5. Rate Some Articles

Go to the home page and click **Useful** or **Not useful** on at least a couple of articles. This is needed for the "Generate" test (data sufficiency check).

---

## Test Checklist

### Test 1: Auth Required (Redirect)

1. Open an **incognito/private** browser window
2. Navigate to `http://localhost:8001/ui/suggestions`
3. **Expected:** Redirects to `/` (home page)

---

### Test 2: Empty State

1. Log in (regular browser)
2. Navigate to `http://localhost:8001/ui/suggestions`
3. **Expected:**
   - "No suggestions yet" message
   - Explanation text about analyzing feedback
   - "Generate Suggestions" button visible

---

### Test 3: Generate — "Not Enough Feedback"

1. On the suggestions page, click **Generate Suggestions**
2. **Expected:** "Not enough feedback yet. Keep rating articles and check back later."

> This is correct — thresholds are 10 feedback items and 7 days of history. With a single day of fixture data, you'll always hit this.

---

### Test 4: Generate — "Coming Soon" (Optional)

To test the `ready` → "Coming soon" path, temporarily lower thresholds:

1. Edit `src/advisor_tools.py` lines 33-34:
   ```python
   MIN_FEEDBACK_ITEMS = 1   # was 10
   MIN_DAYS_HISTORY = 1     # was 7
   ```
2. Restart dev server
3. Click **Generate Suggestions**
4. **Expected:** "Coming soon — agent not yet enabled"
5. **Revert** the thresholds back to 10/7 after testing

---

### Test 5: Nav Link

1. On any page, click the **hamburger menu** (☰)
2. **Expected:** "💡 Suggestions" link appears after "⚙️ Config"
3. Click it → navigates to `/ui/suggestions`

---

### Test 6: Seed Suggestions

Run this to insert test suggestions:

```powershell
python -c "
from src.db import get_conn, init_db
from src.repo import insert_suggestion
conn = get_conn()
init_db(conn)
uid = 'c17d5f85-31cc-4553-99e1-d9ab69462f3a'
insert_suggestion(conn, user_id=uid, suggestion_type='boost_source', field='source_weights', target_key='Reuters', current_value='1.0', suggested_value='1.3', evidence_items=[{'url':'https://example.com/a','title':'A'},{'url':'https://example.com/b','title':'B'},{'url':'https://example.com/c','title':'C'},{'url':'https://example.com/d','title':'D'},{'url':'https://example.com/e','title':'E'}], reason='You liked 8 out of 10 Reuters articles last week.')
insert_suggestion(conn, user_id=uid, suggestion_type='add_topic', field='topics', target_key=None, current_value=None, suggested_value='artificial intelligence', evidence_items=[{'url':'https://example.com/ai1','title':'AI 1'},{'url':'https://example.com/ai2','title':'AI 2'},{'url':'https://example.com/ai3','title':'AI 3'}], reason='AI topics appeared frequently in your liked articles.')
conn.close()
print('Done - 2 suggestions seeded')
"
```

> **Note:** If your user ID is different, replace `uid = '...'` with your actual user ID.

---

### Test 7: Cards Render

1. Refresh `http://localhost:8001/ui/suggestions`
2. **Expected:**
   - **Sources section:**
     - Card: "📈 Show me more from Reuters" + "Moderate boost"
     - Reason: "You liked 8 out of 10 Reuters articles last week."
     - Badge: "Based on 5 articles"
   - **Topics section:**
     - Card: "➕ Add 'artificial intelligence' to your interests"
     - Reason: "AI topics appeared frequently in your liked articles."
     - Badge: "Based on 3 articles"
   - Accept and Reject buttons on each card
   - "Accept All" button at top
3. Click **Details** toggle on the source card
   - **Expected:** "Current: 1.0 → Proposed: 1.3"
4. Click **Details** toggle on the topic card
   - **Expected:** "This will add the topic to your interests"

---

### Test 8: Accept a Card

1. Click **Accept** on one card
2. **Expected:** Card shows "✓ Applied" and fades out after ~2s

---

### Test 9: Reject a Card

1. Click **Reject** on the other card
2. **Expected:** Card shows "✗ Dismissed" and fades out after ~2s

---

### Test 10: "All Done" State

1. After both cards are resolved (accepted/rejected and faded)
2. **Expected:** "All done! Your preferences have been updated."

---

### Test 11: Accept All

1. Seed 2 more suggestions:

```powershell
python -c "
from src.db import get_conn, init_db
from src.repo import insert_suggestion
conn = get_conn()
init_db(conn)
uid = 'c17d5f85-31cc-4553-99e1-d9ab69462f3a'
insert_suggestion(conn, user_id=uid, suggestion_type='reduce_source', field='source_weights', target_key='BuzzFeed', current_value='1.0', suggested_value='0.7', evidence_items=[{'url':'https://example.com/x','title':'X'},{'url':'https://example.com/y','title':'Y'},{'url':'https://example.com/z','title':'Z'},{'url':'https://example.com/w','title':'W'}], reason='You dismissed 7 out of 8 BuzzFeed articles.')
insert_suggestion(conn, user_id=uid, suggestion_type='remove_topic', field='topics', target_key=None, current_value='crypto', suggested_value='crypto', evidence_items=[{'url':'https://example.com/c1','title':'Crypto 1'},{'url':'https://example.com/c2','title':'Crypto 2'}], reason='You consistently skip crypto-related articles.')
conn.close()
print('Done - 2 more suggestions seeded')
"
```

2. Refresh `/ui/suggestions`
3. Click **Accept All**
4. **Expected:** Each card individually shows "✓ Applied", fades out, then "All done" message

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `/ui/suggestions` returns 404 JSON | Restart dev server (`taskkill /f /im python.exe && make dev`) |
| Home page shows "No items found" | Run `make run DATE=YYYY-MM-DD --mode fixtures --force --user-id ...` |
| `inserted: 0, duplicates: 5` | Delete old fixture items (see Prerequisites step 2) then re-run |
| No feedback buttons on articles | Run was created without `--user-id`. Re-run with `--user-id` flag |
| "Not enough feedback" on Generate | Expected with < 10 items or < 7 days. Lower thresholds temporarily (Test 4) |
| Session expired | Re-login via browser console (see Prerequisites step 4) |
| Register returns "Method Not Allowed" | Registration is admin-only. Create user via Python script (see Prerequisites step 4) |

---

## Results Log

### 2026-02-04 — All Pass ✅

| Test | Result |
|------|--------|
| 1. Auth redirect | ✅ |
| 2. Empty state | ✅ |
| 3. Generate "not enough feedback" | ✅ |
| 4. Generate "coming soon" | ✅ (with lowered thresholds) |
| 5. Nav link | ✅ |
| 6. Seed suggestions | ✅ |
| 7. Cards render | ✅ |
| 8. Accept | ✅ |
| 9. Reject | ✅ |
| 10. All done state | ✅ |
| 11. Accept All | ✅ |
