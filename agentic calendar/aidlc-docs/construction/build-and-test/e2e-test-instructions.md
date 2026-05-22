# End-to-End Test Instructions — Calendar-Agent

---

## Purpose

End-to-end (E2E) tests validate the complete user workflow from the browser through the frontend, API Gateway, Lambda, Bedrock, and Google Calendar — ensuring the entire system works as a cohesive product.

---

## Prerequisites

- Backend deployed to AWS (stack `calendar-agent` active)
- Frontend deployed to S3 with correct `API_BASE_URL`
- Google OAuth redirect URI registered in Google Cloud Console
- A test Google account with some calendar events

---

## E2E Test Scenarios

### Scenario 1: First-Time User — OAuth Login

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open the frontend URL in a browser | Auth screen displayed with "Sign in with Google" button |
| 2 | Click "Sign in with Google" | Redirected to Google OAuth consent screen |
| 3 | Grant calendar access | Redirected back to frontend with `?auth=success` |
| 4 | Chat screen appears | Welcome message displayed, input field active |

**Pass criteria**: User lands on the chat screen with no errors.

---

### Scenario 2: Daily Briefing

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Type "What do I have today?" and press Enter | Loading indicator appears |
| 2 | Wait for response | Agent replies with a formatted list of today's events |
| 3 | Verify events match Google Calendar | Events, times, and titles are accurate |

**Pass criteria**: Response matches the user's actual Google Calendar for today.

---

### Scenario 3: Create a Single Event

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Type "Block 1 hour for reading tomorrow at 3pm" | Agent asks for confirmation (default mode) |
| 2 | Type "yes" | Agent confirms: "Done! I've created **Reading**..." |
| 3 | Open Google Calendar | Event "Reading" exists tomorrow at 3pm, 1 hour duration |

**Pass criteria**: Event created in Google Calendar with correct title, time, and duration.

---

### Scenario 4: Create a Recurring Event

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Type "Add a weekly standup every Monday at 9am" | Agent asks for confirmation |
| 2 | Type "yes" | Agent confirms creation |
| 3 | Open Google Calendar | Recurring event series visible on Mondays at 9am |

**Pass criteria**: Recurring event series created correctly.

---

### Scenario 5: Smart Slot Suggestion

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Type "I need 2 hours for deep work this week" | Agent proposes 2–3 slot options with rationale |
| 2 | Type "2" (select second option) | Agent asks for confirmation |
| 3 | Type "yes" | Agent confirms creation in the selected slot |
| 4 | Open Google Calendar | Event exists in the selected time slot |

**Pass criteria**: Suggested slots respect working hours and buffer time; selected slot is created correctly.

---

### Scenario 6: Delete an Event

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Type "Cancel my reading block tomorrow" | Agent asks for confirmation |
| 2 | Type "yes" | Agent confirms: "Done! I've cancelled **Reading**." |
| 3 | Open Google Calendar | Event no longer exists |

**Pass criteria**: Event deleted from Google Calendar.

---

### Scenario 7: Ambiguous Request

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Ensure two events exist tomorrow | (Setup) |
| 2 | Type "Cancel my meeting tomorrow" | Agent presents numbered list of matching events |
| 3 | Type "1" | Agent asks for confirmation for the selected event |
| 4 | Type "yes" | Only the selected event is deleted |

**Pass criteria**: Agent does not delete the wrong event; disambiguation works correctly.

---

### Scenario 8: Preference Configuration

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Type "My working hours are 8am to 4pm" | Agent acknowledges the change |
| 2 | Type "I need 1 hour for planning this week" | Suggested slots are within 8am–4pm only |
| 3 | Type "Stop asking me to confirm" | Agent acknowledges confirmation mode is off |
| 4 | Type "Block 30 minutes for email tomorrow at 9am" | Event created immediately without confirmation prompt |

**Pass criteria**: Preferences applied correctly within the session.

---

### Scenario 9: Error Handling — Bedrock Unavailable

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | (Simulate by temporarily changing BEDROCK_MODEL_ID to an invalid value) | |
| 2 | Type "What do I have today?" | Agent returns friendly error: "I'm having trouble connecting..." |
| 3 | Restore correct model ID | |

**Pass criteria**: No crash, no silent failure, user-friendly error message displayed.

---

### Scenario 10: Session Continuity

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Type "What do I have today?" | Agent responds with events |
| 2 | Type "And tomorrow?" | Agent understands "tomorrow" in context (session memory) |
| 3 | Refresh the browser page | New session starts fresh (no memory of previous conversation) |

**Pass criteria**: Context maintained within session; fresh start after page refresh.

---

## Test Execution Checklist

```
[ ] Scenario 1: OAuth Login
[ ] Scenario 2: Daily Briefing
[ ] Scenario 3: Create Single Event
[ ] Scenario 4: Create Recurring Event
[ ] Scenario 5: Smart Slot Suggestion
[ ] Scenario 6: Delete Event
[ ] Scenario 7: Ambiguous Request
[ ] Scenario 8: Preference Configuration
[ ] Scenario 9: Error Handling
[ ] Scenario 10: Session Continuity
```

---

## Cleanup After Testing

1. Delete any test events created in Google Calendar
2. (Optional) Revoke the test account's OAuth access: Google Account → Security → Third-party apps → Calendar-Agent → Remove access
