# Requirements Clarification Questions — Agentic Calendar Assistant

Please answer each question by filling in the letter choice after the `[Answer]:` tag.
If none of the options match your needs, choose the last option (Other) and describe your preference.

---

## Question 1: MVP Scope — Recurring Events
The vision document lists this as an open question. Should the MVP support recurring event creation (e.g., "every Monday at 9am"), or only single one-off events?

A) Single events only — keep MVP scope minimal

B) Recurring events included — it's a common enough use case to include from day one

C) Other (please describe after [Answer]: tag below)

[Answer]: Recurring events included — it's a common enough use case to include from day one

---

## Question 2: Conversation Memory
Should the agent remember context across separate sessions (e.g., user says "reschedule that meeting" in a new session and the agent knows which meeting was discussed yesterday)?

A) No memory across sessions — each conversation starts fresh; user must re-specify context

B) Short-term memory only — remember context within a single session, not across sessions

C) Persistent memory — store conversation history so the agent can reference past sessions

D) Other (please describe after [Answer]: tag below)

[Answer]: Short-term memory only — remember context within a single session, not across sessions

---

## Question 3: Ambiguous Request Handling
When the user's request is ambiguous (e.g., "cancel my meeting tomorrow" and there are two meetings), what should the agent do?

A) Always ask for clarification before taking any action

B) Make a best guess and confirm with the user before executing ("I think you mean the 2pm meeting — shall I cancel it?")

C) Present all matching options and let the user choose

D) Other (please describe after [Answer]: tag below)

[Answer]:Present all matching options and let the user choose 

---

## Question 4: Confirmation Before Write/Delete Operations
The vision mentions adding a confirmation step before any write or delete. Should this apply to ALL write operations, or only destructive ones?

A) Confirmation required for ALL write operations (create, update, delete)

B) Confirmation required only for destructive operations (delete, reschedule) — creation can proceed without confirmation

C) Confirmation is optional — user can configure it per preference

D) Other (please describe after [Answer]: tag below)

[Answer]: Confirmation is optional — user can configure it per preference

---

## Question 5: Smart Slot Suggestion Logic
When the agent suggests an optimal time slot, what factors should it consider?

A) Free/busy status only — suggest any available slot in the requested window

B) Free/busy + working hours preference (e.g., avoid early morning or late evening)

C) Free/busy + working hours + buffer time between meetings (avoid back-to-back scheduling)

D) All of the above plus user-defined preferences (e.g., "I prefer mornings for deep work")

E) Other (please describe after [Answer]: tag below)

[Answer]: Free/busy + working hours + buffer time between meetings (avoid back-to-back scheduling)

---

## Question 6: OAuth Token Storage
How should the Google OAuth token be stored between sessions?

A) In-memory only — user must re-authenticate each session (simplest, most secure)

B) Stored in AWS (e.g., SSM Parameter Store or Secrets Manager) — persistent login across sessions

C) Stored in browser (localStorage/cookie) — client-side persistence

D) Other (please describe after [Answer]: tag below)

[Answer]: Stored in AWS (e.g., SSM Parameter Store or Secrets Manager) — persistent login across sessions

---

## Question 7: Calendar Data Persistence
Should the agent store any calendar event data persistently (e.g., for caching or history), or always fetch live from Google Calendar?

A) Always fetch live — no local storage of calendar data

B) Cache events temporarily (e.g., within a session) to reduce API calls, but never persist to disk/DB

C) Persist a local copy for faster access and offline reference

D) Other (please describe after [Answer]: tag below)

[Answer]: Cache events temporarily (e.g., within a session) to reduce API calls, but never persist to disk/DB

---

## Question 8: Web Chat UI — Technology Preference
What technology should be used for the web chat frontend?

A) React (TypeScript) — modern, component-based, good ecosystem

B) Plain HTML/CSS/JavaScript — minimal dependencies, easy to deploy

C) Vue.js — lightweight alternative to React

D) No preference — choose what best fits the AWS free-tier deployment model

E) Other (please describe after [Answer]: tag below)

[Answer]: Plain HTML/CSS/JavaScript — minimal dependencies, easy to deploy

---

## Question 9: Backend Architecture
What backend architecture should be used for the AWS deployment?

A) Serverless — AWS Lambda + API Gateway (best fit for free tier, event-driven)

B) Container-based — AWS ECS Fargate or App Runner

C) Traditional server — EC2 instance (always-on)

D) No preference — choose what best fits free-tier constraints

E) Other (please describe after [Answer]: tag below)

[Answer]:No preference — choose what best fits free-tier constraints but I want to use BedRock to better understanding how it works 

---

## Question 10: Amazon Bedrock Model
Which Amazon Bedrock model should the agent use for natural language understanding?

A) Amazon Nova Pro — AWS's latest high-performance model

B) Amazon Nova Lite — faster and cheaper, good for simpler tasks

C) Anthropic Claude (latest available on Bedrock) — strong reasoning and instruction-following

D) No preference — choose the best free-tier option available

E) Other (please describe after [Answer]: tag below)

[Answer]: No preference — choose the best free-tier option available

---

## Question 11: Error Handling — Bedrock Unavailability
What should happen if Amazon Bedrock is unavailable or returns an error?

A) Return a friendly error message to the user and ask them to retry

B) Retry automatically up to 3 times with exponential backoff, then show error

C) Fall back to a simpler rule-based response for common commands (e.g., "show today's events")

D) Other (please describe after [Answer]: tag below)

[Answer]:Return a friendly error message to the user and ask them to retry 

---

## Question 12: Working Hours Definition
Should the agent be aware of the user's working hours when suggesting time slots?

A) Use a fixed default (e.g., 9am–6pm Monday–Friday)

B) Allow the user to configure their working hours via the chat interface

C) No working hours constraint — suggest any free slot regardless of time of day

D) Other (please describe after [Answer]: tag below)

[Answer]: Allow the user to configure their working hours via the chat interface

---

## Question 13: Security Extension
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]:No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects) 

---

## Question 14: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips

C) No — skip all PBT rules (suitable for simple CRUD applications or thin integration layers)

X) Other (please describe after [Answer]: tag below)

[Answer]: No — skip all PBT rules (suitable for simple CRUD applications or thin integration layers)
