# Hamburger Menu Z-Index Layering Chart (Flask + HTMX Projects)

This chart documents the z-index relationships between hamburger menu, dropdown, and modal overlays in bookmark-manager style applications.

## Component Z-Index Map

| Element | Selector | z-index | Notes |
|---------|----------|---------|-------|
| Hamburger button | `.hamburger-btn` | `1001` | Above dropdown, below any toast/notification |
| Hamburger dropdown | `.hamburger-dropdown` | `1000` | Appears on top of page content |
| Page content overlay | `.dialog-overlay` | `2000+` | Modal/popup backgrounds cover everything |
| Modals | `#schedule-modal`, `#notehub-dialog` | `2500` | Content inside overlay, higher than dropdown |
| Toast notifications | `#toast` | `3000+` | Topmost transient feedback |

## Interaction Flow

```
User clicks hamburger button → toggleHamburger() adds 'show' class → dropdown appears (z-index 1000)
│
├── If user clicks modal-open button in dropdown (e.g., "排程音檔") → openScheduleModal() → 
│   - toggleHamburger() closes dropdown first (remove 'show')  
│   - schedule-modal displays (display:flex) with z-index 2500
│
├── If user clicks outside anywhere → document click event listener checks if target is inside 
│   .hamburger-menu; if not, remove 'show' from dropdown
│
└── Z-index problem scenario: dropdown opens while modal is already visible → 
    modal overlay (z-index 2500) covers dropdown (z-index 1000) → 
    user cannot see dropdown items OR clicks pass through to body → unexpected close behavior
```

## Recommended Fix

Always call `toggleHamburger()` inside modal-opening functions to close the dropdown **before** showing the modal:

```javascript
function openScheduleModal() {
    toggleHamburger(); // Ensure dropdown is closed first
    // ... then show modal
}
```

This prevents the dropdown from being visually obscured by the modal overlay.

## Debugging Checklist

When menu disappears or clicks don't work:

1. **Check browser console**: Any `ReferenceError: toggleHamburger is not defined` means the function wasn't loaded due to a script block error earlier
2. **Count script tags**: Verify `<script>` and `</script>` are balanced in HTML source
3. **Inspect element**: Right-click hamburger button → "Inspect" → check if the element exists and has the correct class/ID
4. **Verify CSS**: Open DevTools → Computed tab → confirm `.hamburger-dropdown.show` sets `display: block`
5. **Check z-index**: In DevStyles, look at `.hamburger-dropdown` and ensure it's not covered by another element with higher z-index
6. **Test isolated**: Temporarily simplify to just a working dropdown without modals, then re-add complexity incrementally