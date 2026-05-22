# Code Generation Plan — Unit 2: Frontend

**Unit**: unit-2-frontend
**Technology**: Plain HTML / CSS / JavaScript (no framework)
**Hosting**: AWS S3 static website
**Code Location**: `frontend/`

---

## Generation Steps

### Step 1: HTML — Chat UI structure
- [x] Create `frontend/index.html` — auth screen, chat screen, message list, input form, ARIA labels, data-testid attributes

### Step 2: CSS — Styles
- [x] Create `frontend/style.css` — responsive layout, message bubbles (user/agent/system), typing indicator, auth card, buttons, dark-mode-ready CSS variables

### Step 3: JavaScript — Application logic
- [x] Create `frontend/app.js` — OAuth flow, session state management, API calls, message rendering, markdown formatting, auto-resize textarea, keyboard shortcuts

---

## Requirements Traceability

| Requirement | Implemented In |
|-------------|---------------|
| FR-08 OAuth login initiation | `app.js initiateOAuthFlow()`, `index.html #sign-in-btn` |
| FR-12 Web chat interface | `index.html`, `style.css`, `app.js` |
| NFR-04 Loading indicator | `index.html #typing-indicator`, `app.js setLoading()` |
