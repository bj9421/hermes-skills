# Mobile Map UI Lessons — 17uu.tw Accommodation Query

## Session: 2026-07-18

### Problem 1: Unicode Normalization Breaks Lookup Keys
**Symptom:** Sorting/filtering by city name fails silently.
**Root Cause:** Database stores cities with traditional character `臺` (e.g., `臺北市`) but JS lookup keys use simplified `台` (e.g., `台北市`).
**Fix:** Add a normalization function:
```javascript
function normalizeCity(city) {
    return city.replace(/臺/g, '台');
}
// Then use normalizeCity(key) for ALL lookups
```
**Lesson:** Always normalize unicode variants at the boundary between backend data and frontend logic.

### Problem 2: Marker Click Handler Doesn't Navigate
**Symptom:** Clicking a list item does nothing on the map.
**Root Cause:** `focusHotel(id)` used `findIndex(() => true)` — a hardcoded match that finds the first marker regardless of id.
**Fix:** Store `marker.hotelId = hotel.id` when creating markers, then use `find(m => m.hotelId === id)`.

### Problem 3: Circle Markers Too Small on Mobile
**Symptom:** Markers barely visible on phone screen.
**Fix:** Increase `radius` from 6 to 10, `weight` from 1 to 2, `fillOpacity` from 0.8 to 0.9.

### Problem 4: Search Bar Layout Overflows on Mobile
**Symptom:** City dropdown + checkboxes + search box all on one line, overflows screen.
**Fix:** Split into two rows:
- Row 1: City dropdown + level checkboxes
- Row 2: Search input + buttons
Use CSS flexbox with `flex-wrap: wrap`.

### Problem 5: Sidebar Blocks Map on Mobile
**Symptom:** List takes half the screen, map is tiny.
**Fix:** 
- Desktop: sidebar visible by default
- Mobile: sidebar hidden by default, toggleable via button
- Use CSS media queries with `.sidebar.collapsed` class
- On mobile, sidebar slides up from bottom (position: absolute, bottom: 0)

---

## Session: 2026-07-18 (Mobile Layout Deadlock)

### Problem 6: CSS Media Query Duplicate — Sidebar Invisible on Mobile
**Symptom:** On mobile, the sidebar is completely invisible and cannot be toggled open.
**Root Cause:** Two `@media (max-width: 768px)` blocks in the same CSS file. The second block (later in file) overwrites the first. The second block set `.sidebar` to `position: absolute; bottom: 0; height: 0` and `.sidebar.collapsed` to `display: none` — creating a deadlock where the sidebar can never be shown.
**Fix:** Remove duplicate media queries. Consolidate into one `@media (max-width: 768px)` block. Use flexbox `flex-direction: column` for mobile (search bar → list → map stacked vertically).
**Lesson:** Always search for ALL occurrences of a media query before modifying. Use `search_files` to find duplicates. CSS applies last-defined rule wins — duplicate blocks silently overwrite each other.

### Problem 7: Level Filter Only Supports Single Value
**Symptom:** Checking multiple level checkboxes (五星/高級/飯店/民宿) does not accumulate results. Map markers show only one level.
**Root Cause:** Backend used `request.args.get('level')` which only returns the first value. Frontend default was `selectedLevels = ['[4]']` (only 民宿).
**Fix:** 
- Backend: Change to `request.args.getlist('level')` and use `IN (?)` SQL clause with placeholders.
- Frontend: Change default to `['[1]', '[2]', '[3]', '[4]']` (all levels). Remove "must select at least one" fallback.
- Reset button should check ALL checkboxes, not just one.
**Lesson:** Filters should default to "all" unless user explicitly deselects. Use `getlist()` not `get()` for multi-select parameters.

### Problem 8: Map Only Shows Paginated Results (20 per page)
**Symptom:** Map markers only show 20 items (current page), not all matching accommodations.
**Root Cause:** Frontend called `/api/hotels` (paginated) and used those 20 items for map markers.
**Fix:** Create a separate `/api/hotels/map` endpoint that returns ALL matching records (no pagination). Frontend calls both APIs in parallel via `Promise.all()`.
**Lesson:** Separate paginated list API from full-data map API. Use `Promise.all()` for parallel requests.

### Problem 9: SQL Syntax Error — WHERE Clause with AND
**Symptom:** `/api/hotels/map` returns 500 error, HTML debug page.
**Root Cause:** SQL query built `WHERE {conditions} AND lat IS NOT NULL` but when `where_clause` is empty, it becomes `WHERE AND lat IS NOT NULL` — invalid SQL.
**Fix:** Check if `where_clause` is non-empty before appending `AND`. If empty, use `WHERE lat IS NOT NULL` directly.
**Lesson:** Always handle the "no filter" case separately in dynamic SQL. Never blindly concatenate `AND` to empty WHERE clauses.

---

## Data Reference: Hotel Classification (Taiwan)

| hotel_classes | Label | Count | Meaning |
|---------------|-------|-------|---------|
| [1] | 五星國際 | 71 | 5-star international hotels |
| [2] | 高級飯店 | 45 | High-end hotels |
| [3] | 飯店/旅館 | 3,170 | Hotels / Inns |
| [4] | 民宿 | 12,370 | Licensed B&Bs (觀光局立案) |

**Key insight:** `[4]` = 合格民宿 (licensed B&Bs). This is the largest category and represents government-approved accommodations. Total with all levels: ~15,656 records.
