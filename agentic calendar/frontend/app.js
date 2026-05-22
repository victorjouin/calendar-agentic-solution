/**
 * app.js — Calendar-Agent web chat UI
 *
 * Responsibilities:
 * - Google OAuth 2.0 login flow initiation and redirect handling
 * - Session state management in browser memory (no localStorage)
 * - HTTP communication with the backend API Gateway endpoint
 * - Chat message rendering with basic markdown-like formatting
 * - Loading indicator, error handling, auto-resize textarea
 */

'use strict';

// ── Configuration ─────────────────────────────────────────────────────────────
// Replace with your API Gateway base URL after deploying the backend.
// Example: 'https://abc123.execute-api.us-east-1.amazonaws.com/Prod'
const API_BASE_URL = 'REPLACE_WITH_API_GATEWAY_URL';

// Google OAuth 2.0 configuration.
// Replace with your Google Cloud project's OAuth client ID.
const GOOGLE_CLIENT_ID = 'REPLACE_WITH_GOOGLE_CLIENT_ID';

// OAuth scopes required for Google Calendar access
const GOOGLE_SCOPES = 'https://www.googleapis.com/auth/calendar';

// ── DOM References ────────────────────────────────────────────────────────────

const authScreen      = document.getElementById('auth-screen');
const chatScreen      = document.getElementById('chat-screen');
const signInBtn       = document.getElementById('sign-in-btn');
const signOutBtn      = document.getElementById('sign-out-btn');
const authError       = document.getElementById('auth-error');
const messageList     = document.getElementById('message-list');
const chatForm        = document.getElementById('chat-form');
const messageInput    = document.getElementById('message-input');
const sendBtn         = document.getElementById('send-btn');
const typingIndicator = document.getElementById('typing-indicator');
const statusIndicator = document.getElementById('status-indicator');

// ── Application State ─────────────────────────────────────────────────────────

/** @type {Object|null} Session state object — round-tripped with the backend */
let sessionState = null;

/** @type {boolean} Whether a request is currently in flight */
let isLoading = false;

// ── Initialisation ────────────────────────────────────────────────────────────

/**
 * Entry point — called on page load.
 * Checks for OAuth callback parameters or existing authentication.
 */
async function init() {
  const params = new URLSearchParams(window.location.search);

  // OAuth success redirect from backend
  if (params.get('auth') === 'success') {
    // Clean the URL without reloading
    window.history.replaceState({}, document.title, window.location.pathname);
    showChatScreen();
    return;
  }

  // Check if the backend already has valid tokens (user was previously authenticated)
  const authenticated = await checkAuthStatus();
  if (authenticated) {
    showChatScreen();
  } else {
    showAuthScreen();
  }
}

/**
 * Check whether the backend has valid OAuth tokens stored.
 * Sends a lightweight chat message and inspects the requires_auth flag.
 *
 * @returns {Promise<boolean>}
 */
async function checkAuthStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) return false;
    // If health check passes, attempt a silent auth probe
    const chatResponse = await callChatApi('__auth_check__', null);
    return chatResponse && !chatResponse.requires_auth;
  } catch {
    return false;
  }
}

// ── OAuth Flow ────────────────────────────────────────────────────────────────

/**
 * Build the Google OAuth 2.0 authorisation URL and redirect the browser.
 */
function initiateOAuthFlow() {
  const redirectUri = `${API_BASE_URL}/oauth/callback`;
  const state = generateState();

  const params = new URLSearchParams({
    client_id:     GOOGLE_CLIENT_ID,
    redirect_uri:  redirectUri,
    response_type: 'code',
    scope:         GOOGLE_SCOPES,
    access_type:   'offline',   // Request refresh token
    prompt:        'consent',   // Always show consent to ensure refresh token is issued
    state:         state,
  });

  window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

/**
 * Generate a random state string for CSRF protection.
 * @returns {string}
 */
function generateState() {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
}

// ── Screen Management ─────────────────────────────────────────────────────────

function showAuthScreen() {
  authScreen.classList.remove('hidden');
  chatScreen.classList.add('hidden');
  signInBtn.disabled = false;
  hideAuthError();
}

function showChatScreen() {
  authScreen.classList.add('hidden');
  chatScreen.classList.remove('hidden');
  sessionState = null; // Fresh session on every login
  appendWelcomeMessage();
  messageInput.focus();
}

// ── Chat API ──────────────────────────────────────────────────────────────────

/**
 * Send a message to the backend chat endpoint.
 *
 * @param {string} message - The user's message text.
 * @param {Object|null} state - Current session state (null for new sessions).
 * @returns {Promise<{reply: string, session_state: Object, requires_auth?: boolean}|null>}
 */
async function callChatApi(message, state) {
  const body = { message };
  if (state) body.session_state = state;

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Server error (${response.status})`);
  }

  return response.json();
}

// ── Message Handling ──────────────────────────────────────────────────────────

/**
 * Handle chat form submission.
 * @param {Event} event
 */
async function handleSubmit(event) {
  event.preventDefault();

  const text = messageInput.value.trim();
  if (!text || isLoading) return;

  // Render user message immediately
  appendMessage('user', text);
  messageInput.value = '';
  resizeTextarea();
  sendBtn.disabled = true;

  setLoading(true);

  try {
    const data = await callChatApi(text, sessionState);

    if (data.requires_auth) {
      // Session expired — show re-auth prompt
      appendMessage('agent', '🔐 Your session has expired. Please sign in again.');
      setTimeout(showAuthScreen, 2000);
      return;
    }

    // Update session state with the backend's response
    sessionState = data.session_state;

    appendMessage('agent', data.reply);
    setOnline(true);

  } catch (err) {
    console.error('Chat API error:', err);
    appendMessage(
      'agent',
      `⚠️ I'm having trouble connecting right now. Please try again in a moment.\n\n_${err.message}_`
    );
    setOnline(false);
  } finally {
    setLoading(false);
    messageInput.focus();
  }
}

// ── Message Rendering ─────────────────────────────────────────────────────────

/**
 * Append a message bubble to the conversation.
 *
 * @param {'user'|'agent'|'system'} role
 * @param {string} text - Raw text (supports basic markdown-like formatting)
 */
function appendMessage(role, text) {
  const wrapper = document.createElement('div');
  wrapper.classList.add('message', role);

  const bubble = document.createElement('div');
  bubble.classList.add('bubble');
  bubble.innerHTML = formatText(text);

  const timestamp = document.createElement('span');
  timestamp.classList.add('message-time');
  timestamp.textContent = formatTime(new Date());
  timestamp.setAttribute('aria-label', `Sent at ${formatTime(new Date())}`);

  wrapper.appendChild(bubble);
  if (role !== 'system') wrapper.appendChild(timestamp);

  messageList.appendChild(wrapper);
  scrollToBottom();
}

/**
 * Append the welcome message shown at the start of each session.
 */
function appendWelcomeMessage() {
  appendMessage(
    'system',
    '👋 Hi! I\'m your Calendar-Agent. Ask me anything about your schedule, or tell me what to create, move, or cancel.'
  );
}

/**
 * Convert basic markdown-like syntax to safe HTML.
 * Supports: **bold**, *italic*, `code`, line breaks.
 * All other HTML is escaped to prevent XSS.
 *
 * @param {string} text
 * @returns {string} Safe HTML string
 */
function formatText(text) {
  // Escape HTML entities first
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  // Apply markdown-like formatting
  html = html
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')   // **bold**
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')            // *italic*
    .replace(/_(.+?)_/g,       '<em>$1</em>')            // _italic_
    .replace(/`(.+?)`/g,       '<code>$1</code>')        // `code`
    .replace(/\n/g,            '<br>');                  // line breaks

  return html;
}

/**
 * Format a Date object as HH:MM.
 * @param {Date} date
 * @returns {string}
 */
function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ── UI State Helpers ──────────────────────────────────────────────────────────

/**
 * Show or hide the typing indicator and disable/enable the send button.
 * @param {boolean} loading
 */
function setLoading(loading) {
  isLoading = loading;
  typingIndicator.classList.toggle('hidden', !loading);
  sendBtn.disabled = loading || !messageInput.value.trim();
  if (loading) scrollToBottom();
}

/**
 * Update the online/offline status indicator in the header.
 * @param {boolean} online
 */
function setOnline(online) {
  statusIndicator.classList.toggle('offline', !online);
  statusIndicator.title = online ? 'Connected' : 'Connection issue';
  statusIndicator.setAttribute('aria-label', `Status: ${online ? 'connected' : 'connection issue'}`);
}

function showAuthError(message) {
  authError.textContent = message;
  authError.classList.remove('hidden');
}

function hideAuthError() {
  authError.textContent = '';
  authError.classList.add('hidden');
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    messageList.scrollTop = messageList.scrollHeight;
  });
}

// ── Textarea Auto-resize ──────────────────────────────────────────────────────

/**
 * Resize the textarea to fit its content (up to the CSS max-height).
 */
function resizeTextarea() {
  messageInput.style.height = 'auto';
  messageInput.style.height = `${messageInput.scrollHeight}px`;
}

// ── Event Listeners ───────────────────────────────────────────────────────────

// Sign in button
signInBtn.addEventListener('click', () => {
  signInBtn.disabled = true;
  hideAuthError();
  try {
    initiateOAuthFlow();
  } catch (err) {
    showAuthError('Failed to initiate sign-in. Please try again.');
    signInBtn.disabled = false;
  }
});

// Sign out button — clear session and return to auth screen
signOutBtn.addEventListener('click', () => {
  sessionState = null;
  // Clear message history
  messageList.innerHTML = '';
  showAuthScreen();
});

// Chat form submission
chatForm.addEventListener('submit', handleSubmit);

// Keyboard shortcuts: Enter to send, Shift+Enter for new line
messageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    if (!sendBtn.disabled) chatForm.dispatchEvent(new Event('submit'));
  }
});

// Enable/disable send button based on input content
messageInput.addEventListener('input', () => {
  sendBtn.disabled = !messageInput.value.trim() || isLoading;
  resizeTextarea();
});

// ── Boot ──────────────────────────────────────────────────────────────────────

init();
