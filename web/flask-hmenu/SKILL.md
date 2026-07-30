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
2. **View page source** and count `<script>` and `</script>` tags — they should match exactly
3. **Reset to known good state**:  
   ```bash
   git checkout HEAD -- templates/index.html static/style.css app.py
   ```
4. **Re-add changes one at a time**, testing after each small edit

## Verification After Implementation

After deploying, verify:
- ✓ Clicking hamburger opens dropdown (no console errors)
- ✓ Clicking outside closes dropdown
- ✓ Dropdown items call correct functions
- ✓ No page crash or blank screen
- ✓ Browser Console shows 0 errors

## Support Files

- `references/hmenu_zindex.md` — detailed z-index layering chart for overlapping modals (component mapping, interaction flow, debugging checklist)
- `scripts/hmenu_test.js` — minimal test script to verify DOM element presence (pre-deployment checklist)