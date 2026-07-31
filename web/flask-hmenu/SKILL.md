---
name: flask-hmenu
description: "Flask header navigation components — hamburger menus, dropdowns, and modals with HTMX compatibility"
tags: [flask, html, css, javascript, htmx, ui]
---

# Flask Header Navigation Components

This skill documents patterns for implementing header navigation elements (hamburger menus, dropdowns, modals) in Flask applications while maintaining compatibility with HTMX and avoiding JavaScript errors that cause page crashes.

## Architecture Overview

```
Flask App (app.py)
├── Routes: /, /bookmarks, /stats, /api/*
├── Templates: index.html (HTMX-enabled)
│   ├── Header with .hamburger-menu
│   ├── Dropdown (#hamburger-dropdown)
│   └── Modal dialogs (schedule, confirm, etc.)
└── Static: style.css (Hamburger CSS, z-index handling)
```

## Common Pitfall: Page Crash on Click

**Symptom:** Clicking hamburger button causes entire page to disappear or freeze.

**Root Causes:**
1. Missing `DOMContentLoaded` event listeners — buttons with `onclick=` call undefined functions
2. Duplicate or mismatched closing `</script>` tags breaking script block structure
3. Z-index overlay blocking clicks even though element is visible
4. Earlier JS error preventing subsequent function definitions from executing
5. **Unrelated script block crashing the whole page** — e.g. a PWA Service Worker registration block elsewhere in the page with an unmatched brace/paren kills the ENTIRE JS engine, so every `onclick=` handler silently stops working. Symptom: 按下去沒反應 (click does nothing) even though the hamburger code itself looks correct. **Diagnose by checking ALL `<script>` blocks in the page, not just the one you edited** — `grep -n '</script>'` the template and inspect each block for balance. A `grep -c '<script'` vs `grep -c '</script>'` mismatch is a smoking gun.

## Implementation Pattern

### 1. HTML Structure (templates/index.html)

Place the hamburger menu inside your header's action area:

```html
<header class="header">
    <h1>📚 Bookmark Manager</h1>
    <div class="header-actions">
        <!-- Hamburger Menu -->
        <div class="hamburger-menu">
            <button class="hamburger-btn" id="hamburger-toggle" onclick="toggleHamburger()">☰ 更多</button>
            <div class="hamburger-dropdown" id="hamburger-dropdown">
                <button class="hamburger-item" onclick="openScheduleModal()">⏱️ 排程音檔</button>
                <button class="hamburger-item" onclick="document.getElementById('notehub-dialog').style.display='flex'">🎙️ 送 Notehub</button>
            </div>
        </div>
        
        <button class="btn btn-sm" onclick="document.getElementById('add-form').style.display='flex'>➕ 新增書籤</button>
        <a href="/tags" class="btn btn-sm">🏷️ 管理標籤</a>
    </div>
</header>
```

### 2. JavaScript Functions (inside main `<script>` block)

Define all functions before the closing `</script>` tag, within the same script block that contains other HTMX-related JS (like `toast()`):

```javascript
function toggleHamburger() {
    const dropdown = document.getElementById('hamburger-dropdown');
    if (!dropdown) return;  // Guard against missing element
    dropdown.classList.toggle('show');
    
    // Close when clicking outside after a short delay
    setTimeout(() => {
        if (dropdown && !dropdown.contains(document.activeElement)) {
            dropdown.classList.remove('show');
        }
    }, 100);
}

// Also close when clicking on the button itself (toggle)
document.addEventListener('click', (e) => {
    const hamburger = document.querySelector('.hamburger-menu');
    if (hamburger && !hamburger.contains(e.target)) {
        const dropdown = document.getElementById('hamburger-dropdown');
        if (dropdown) dropdown.classList.remove('show');
    }
});
```

**Critical:** Ensure the closing `</script>` appears only once after all function definitions. A duplicated or misplaced `</script>` will prematurely terminate the script block, leaving later functions undefined.

### 3. CSS Styling (static/style.css)

Add the following at the end of your stylesheet (after media queries):

```css
/* Hamburger Menu - Taiwanese style */
.hamburger-menu {
    position: relative;
    display: inline-block;
    margin-left: 8px;
}

.hamburger-btn {
    background: #2d3748;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    z-index: 1001;  /* Above dropdown but below overlays */
}

.hamburger-btn:hover {
    background: #4a5568;
}

.hamburger-dropdown {
    display: none;
    position: absolute;
    right: 0;
    top: 100%;
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    min-width: 200px;
    z-index: 1000;  /* Below button but above content */
    margin-top: 4px;
}

.hamburger-dropdown.show {
    display: block;
}

.hamburger-item {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 10px 14px;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    font-size: 14px;
    color: #2d3748;
    transition: background 0.2s;
}

.hamburger-item:hover {
    background: #edf2f7;
}
```

**Z-index note:** The dropdown (`z-index: 1000`) must be below any overlay/modals (typically `z-index: 2000+`). If a modal is open and its overlay covers the dropdown, clicks pass through to the body — which may close the dropdown unexpectedly.

## Recovery Strategy: When the Edit Breaks Everything

If you make multiple patch attempts and the HTML becomes malformed (extra `</script>` tags, missing closing braces, duplicate IDs), use this recovery workflow:

1. **Check browser console** for red JavaScript errors — these indicate undefined functions or syntax crashes
2. **View page source** and count `<script>` and `</script>` tags — they should match exactly (`grep -c '<script'` vs `grep -c '</script>'`)
3. **Reset to known good state**:  
   ```bash
   git checkout HEAD -- templates/index.html static/style.css app.py
   ```
4. **Re-add changes one at a time**, testing after each small edit

> ⚠️ **Patch-tool corruption:** when patching HTML/JS, passing `\n` escape sequences inside `new_string`/`old_string` (instead of real newlines) writes literal backslash-n characters into the file, silently corrupting JS. If `sed`/`read_file` output shows literal `\n` text inside the file, the file is corrupted — reset from git immediately, don't keep patching on top of a corrupted file. Verify each patch with a follow-up read of the edited region.

> ⚠️ **User preference (17uu.tw style):** this user's requested hamburger pattern is a **slide-out sidebar from the screen corner/edge** (like 17uu.tw blogger layouts) that slides in on click — NOT a traditional dropdown menu. If a future session implements the hamburger for this user, use the slide-out sidebar pattern from the start. Traditional dropdowns are acceptable as a fallback only after the user confirms.

## Slide-out Sidebar (17uu.tw / Blogger style) — the pattern that works

Proven implementation (2026-07, bookmark-manager notehub queue sidebar). No dropdown, no `DOMContentLoaded` needed — pure inline `onclick` + CSS transform. Structure:

```html
<!-- overlay + sidebar at end of <body> -->
<div id="nh-overlay" class="nh-overlay" onclick="closeSidebar()"></div>
<aside id="nh-sidebar" class="nh-sidebar">
    <div class="nh-header"><h3>🎙️ 標題</h3><button class="nh-close" onclick="closeSidebar()">✕</button></div>
    <div class="nh-body">...內容...</div>
</aside>
```

```css
.nh-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45);
    opacity: 0; pointer-events: none; transition: opacity 0.3s ease; z-index: 999; }
.nh-overlay.open { opacity: 1; pointer-events: auto; }
.nh-sidebar { position: fixed; top: 0; right: 0; width: min(440px, 94vw); height: 100dvh;
    background: #fff; box-shadow: -4px 0 24px rgba(0,0,0,0.15);
    transform: translateX(100%); transition: transform 0.3s ease; z-index: 1000;
    display: flex; flex-direction: column; overflow: hidden; }
.nh-sidebar.open { transform: translateX(0); }
```

```js
function openSidebar() {
    document.getElementById('nh-overlay').classList.add('open');
    document.getElementById('nh-sidebar').classList.add('open');
}
function closeSidebar() {
    document.getElementById('nh-overlay').classList.remove('open');
    document.getElementById('nh-sidebar').classList.remove('open');
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}
```

**Key facts from the working implementation:**
- The header button is a plain `<button class="hamburger-btn" onclick="openSidebar()">☰</button>` — inline `onclick` beats addEventListener/DOMContentLoaded here because it can't be lost to load-order issues, and it made the sidebar work on the first try after two failed dropdown attempts.
- `height: 100dvh` (dynamic viewport height) — correct on mobile; `100vh` overflows on iOS Safari.
- Overlay (`pointer-events:none` → `auto`) means the closed sidebar never eats clicks even though it's fixed-position.
- Sidebar content is dynamic: build table rows with `tr.innerHTML = \`...\`` and `escapeHtml()` any user text (titles), then poll an API every 5s to update a progress list.
- Poll timer must be cleared in `closeSidebar()` — otherwise hidden sidebar keeps fetching.

## Verification After Implementation

After deploying, verify:
- ✓ Clicking hamburger opens dropdown/sidebar (no console errors)
- ✓ Clicking outside closes dropdown
- ✓ Dropdown items call correct functions
- ✓ No page crash or blank screen
- ✓ Browser Console shows 0 errors
- ✓ **JS syntax gate (run BEFORE browser testing):** extract the main `<script>` block to a temp file and run `node --check` on it — catches syntax errors that would kill every handler:
  ```bash
  python3 -c "
  import re
  html = open('templates/index.html').read()
  m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
  open('/tmp/check_main.js','w').write(m.group(1))"
  node --check /tmp/check_main.js && echo OK
  ```
  Plus a quick brace-balance sanity check (`{` vs `}` counts) on the extracted block. This is the fastest way to prove a page won't 白屏 before you hand it to the user.

## Support Files

- `references/hmenu_zindex.md` — detailed z-index layering chart for overlapping modals (component mapping, interaction flow, debugging checklist)
- `scripts/hmenu_test.js` — minimal test script to verify DOM element presence (pre-deployment checklist)