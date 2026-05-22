# Vision Document — Agentic Calendar Assistant

---

## Executive Summary

Calendar-Agent is an agentic solution that enables individual users to fully delegate the management of their Google Calendar to an AI assistant. It addresses the cognitive overhead of manual scheduling and planning by autonomously reading, creating, updating, and deleting calendar events on the user's behalf. The expected outcome is a personal time management assistant that proactively organises the user's day, suggests optimal scheduling, and maintains awareness of ongoing projects — reducing time spent on calendar management from ~30 minutes per day to under 5 minutes.

---

## Business Context

### Problem Statement

Employees spend significant time each day managing their calendars manually — scheduling meetings, resolving conflicts, tracking project-related tasks, and planning their week. This is repetitive, error-prone, and diverts focus from actual work. There is no intelligent layer between the user and their calendar that can understand context, anticipate needs, and act autonomously.

### Business Drivers

- Reduce the time and mental load employees spend on scheduling and planning logistics
- Enable proactive time management rather than reactive firefighting
- Improve visibility of workload and project advancement for both employees and managers
- Validate the value of agentic AI applied to everyday productivity tools

### Target Users and Stakeholders

| User Type | Description | Primary Need |
|-----------|-------------|--------------|
| Employee | Individual contributor with a busy calendar | Automated scheduling, daily/weekly briefings, task follow-up |
| Manager | Oversees team workload and project progress | Better visibility of team availability and project timelines |

### Business Constraints

- Must run on a free-tier AWS account — no paid cloud services beyond what the free tier covers
- Google Calendar is the only supported calendar platform for the MVP
- No paid third-party scheduling SaaS — all scheduling logic is custom-built

### Success Metrics

| Metric | Current State | Target State | Measurement Method |
|--------|--------------|--------------|-------------------|
| Time spent on manual scheduling | ~30 min/day | < 5 min/day | User self-report |
| Scheduling conflicts per week | Untracked | 0 unresolved conflicts | Calendar audit |
| Agent task completion rate | N/A | > 90% of requests handled correctly | Interaction logs |
| User satisfaction | N/A | > 4/5 rating | Post-session feedback |

---

## Full Scope Vision

### Product Vision Statement

A fully autonomous calendar agent that acts as a personal chief of staff — proactively managing schedules, coordinating across projects, and ensuring every user's time is allocated to what matters most.

### Feature Areas

#### Feature Area 1: Calendar Intelligence
- **Description**: Reading, analysing, and summarising calendar content to give users instant awareness of their schedule
- **Key Capabilities**:
  - Daily and weekly briefings on upcoming events
  - Detection of scheduling conflicts and overloaded days
  - Pattern recognition (recurring meeting types, peak productivity windows)
- **User Value**: Users always know what's ahead without manually checking their calendar

#### Feature Area 2: Autonomous Scheduling
- **Description**: Creating, updating, and deleting calendar events on behalf of the user through natural language
- **Key Capabilities**:
  - Natural language event creation ("schedule a 1h focus block tomorrow morning")
  - Smart time slot suggestion based on existing workload and user preferences
  - Conflict resolution with alternative proposals
- **User Value**: Users delegate scheduling entirely to the agent

#### Feature Area 3: Project and Task Follow-up
- **Description**: Tracking tasks and meetings that belong to the same project to ensure nothing falls through the cracks
- **Key Capabilities**:
  - Grouping related events under a project label
  - Alerting when follow-up actions are due
  - Suggesting next steps based on past meeting descriptions or notes
- **User Value**: Full project timeline visibility without manual tracking

#### Feature Area 4: Team Coordination (Future)
- **Description**: Coordinating schedules across a team for managers and cross-functional work
- **Key Capabilities**:
  - Finding common availability across multiple calendars
  - Manager dashboard for team workload visibility
  - Automated meeting proposals sent to participants
- **User Value**: Managers can coordinate teams without back-and-forth emails

### Integration Points

- **Google Calendar API** — core calendar read/write operations
- **Google OAuth 2.0** — user authentication and calendar access authorisation
- **Amazon Bedrock** — LLM reasoning and natural language understanding
- **Future: Microsoft Outlook / Office 365** — expanded calendar platform support
- **Future: Jira / Notion / Asana** — project context enrichment

### User Journeys (Full Vision)

#### Journey 1: Morning Briefing
1. User opens the chat interface
2. Agent proactively greets the user with a summary of today's events
3. Agent flags any conflicts or tight transitions
4. Agent suggests one optimisation (e.g., "You have back-to-back meetings at 2pm and 3pm — want me to add a 15-min buffer?")
5. User approves or adjusts
**Outcome**: User starts the day with a clear, optimised schedule in under 2 minutes

#### Journey 2: Scheduling a New Task
1. User types "I need to prep for the Q3 review, about 2 hours, before Friday"
2. Agent analyses the calendar for available slots
3. Agent proposes 2–3 options with rationale
4. User picks one or asks for alternatives
5. Agent creates the event and confirms
**Outcome**: Task is scheduled in the optimal slot without the user opening the calendar

#### Journey 3: Project Follow-up
1. User asks "What's the status of the Alpha project meetings?"
2. Agent retrieves all events tagged or related to the Alpha project
3. Agent summarises what happened, what's upcoming, and what's missing
4. Agent suggests scheduling a follow-up if none exists
**Outcome**: User has full project timeline visibility in one conversation turn

### Scalability and Growth

- Start as a single-user personal tool, then expand to team and enterprise use
- Add support for Microsoft Outlook / Office 365 to cover corporate environments
- Integrate with project management tools (Jira, Notion, Asana) for richer scheduling context
- Support multiple languages for international teams

### Long-Term Roadmap

| Phase | Focus | Timeframe |
|-------|-------|-----------|
| MVP | Single-user Google Calendar agent with chat UI | Q3 2025 |
| Phase 2 | Project follow-up, team coordination, manager dashboard | Q4 2025 |
| Phase 3 | Outlook integration, PM tool integrations, multi-language | 2026 |

---

## MVP Scope

### MVP Objective

Deliver a single-user agentic assistant that can autonomously read, create, update, and delete Google Calendar events through a conversational web chat interface, proving that an AI agent can meaningfully reduce the time and effort a user spends managing their calendar.

### MVP Success Criteria

- [ ] User can ask the agent to summarise their day or week and receive an accurate response
- [ ] User can create a new calendar event via natural language and it appears in Google Calendar
- [ ] User can delete or reschedule an event via the chat interface
- [ ] Agent suggests an optimal time slot when asked to schedule a task
- [ ] All interactions complete without the user needing to open Google Calendar directly

### Features In Scope (MVP)

| Feature | Description | Priority | Rationale for Inclusion |
|---------|-------------|----------|------------------------|
| Calendar read | Fetch and display upcoming events by day/week | Must Have | Core value — user needs to see their schedule |
| Event creation | Create events via natural language | Must Have | Core autonomous action |
| Event deletion / refusal | Delete or decline events via chat | Must Have | Core autonomous action |
| Event rescheduling | Move an event to a new time slot | Must Have | Core autonomous action |
| Smart slot suggestion | Propose optimal times for new tasks | Must Have | Key differentiator from simple calendar apps |
| Daily/weekly briefing | Proactive summary of upcoming events | Must Have | Reduces need for user to ask manually |
| Web chat UI | Conversational interface for all interactions | Must Have | Primary interaction channel |
| Google OAuth | Secure calendar access via Google login | Must Have | Required for Google Calendar API access |

### Features Explicitly Out of Scope (MVP)

| Feature | Reason for Deferral | Target Phase |
|---------|-------------------|--------------|
| Multi-user / team coordination | Adds significant complexity; single-user validates core value first | Phase 2 |
| Manager dashboard | Requires multi-user support | Phase 2 |
| Project follow-up tracking | Needs event tagging system not in MVP | Phase 2 |
| Outlook / Office 365 support | Google Calendar validates the approach first | Phase 3 |
| PM tool integrations (Jira, Notion) | Out of scope for calendar-only MVP | Phase 3 |
| Mobile app | Web UI is sufficient for MVP validation | Phase 2 |
| Proactive push notifications | Requires background process; user-initiated chat is sufficient for MVP | Phase 2 |

### MVP User Journeys

#### Journey 1: Daily Briefing
1. User opens the web chat interface
2. User asks "What do I have today?"
3. Agent fetches today's events from Google Calendar
4. Agent returns a structured summary with times, titles, and any conflicts
**Outcome**: User knows their day at a glance
**Limitation vs Full Vision**: No proactive push — user must ask; no optimisation suggestions yet

#### Journey 2: Schedule a New Event
1. User types "Block 2 hours for deep work tomorrow afternoon"
2. Agent checks tomorrow's calendar for free slots in the afternoon
3. Agent proposes the best available slot with a brief rationale
4. User confirms
5. Agent creates the event in Google Calendar and confirms
**Outcome**: Event created in the right slot without opening Google Calendar
**Limitation vs Full Vision**: No cross-project awareness; single-user only

#### Journey 3: Delete or Reschedule an Event
1. User types "Cancel my 3pm meeting on Thursday"
2. Agent identifies the matching event
3. Agent asks for confirmation before deleting
4. User confirms
5. Agent deletes the event and confirms
**Outcome**: Event removed cleanly with a confirmation step
**Limitation vs Full Vision**: No attendee notification or rescheduling proposal to others

### MVP Constraints and Assumptions

- **Assumption**: A single user authenticates once via Google OAuth and the token is stored securely — **Risk if wrong**: Re-auth friction degrades UX significantly
- **Assumption**: Google Calendar API free quota is sufficient for single-user MVP usage — **Risk if wrong**: Rate limiting; need to add response caching
- **Assumption**: Amazon Bedrock free tier provides sufficient LLM invocations for MVP testing — **Risk if wrong**: Costs incurred; need to optimise prompt frequency
- **Accepted Limitation**: No real-time push notifications — user must initiate every conversation
- **Accepted Limitation**: Natural language understanding is bounded by the Bedrock model's capabilities; complex or ambiguous requests may require clarification from the user

### MVP Definition of Done

- [ ] All "Must Have" features implemented and tested
- [ ] Google OAuth flow working end-to-end in the web UI
- [ ] Agent correctly reads, creates, updates, and deletes events in a live Google Calendar
- [ ] Web chat UI deployed and accessible
- [ ] Basic error handling in place for API failures and ambiguous user input
- [ ] End-to-end user journey tested manually from chat to Google Calendar

---

## Risks and Dependencies

### Key Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM misinterprets user intent and modifies the wrong event | Medium | High | Add explicit confirmation step before any write or delete operation |
| Google Calendar API rate limiting | Low | Medium | Implement request caching and exponential backoff |
| OAuth token expiry causing silent failures | Medium | Medium | Implement token refresh logic and user re-auth prompts |
| Amazon Bedrock model unavailability or quota limits | Medium | High | Use model fallback; cache frequent responses |
| Calendar data privacy — event content sent to Bedrock | Medium | High | Review AWS data handling policies; avoid persisting raw event data |
| Scope creep from team/multi-user requests during MVP | Medium | Medium | Enforce out-of-scope list; defer all team features to Phase 2 |

### External Dependencies

- **Google Calendar API** — Google — Active; requires OAuth app registration in Google Cloud Console
- **Google OAuth 2.0** — Google — Active; requires app approval for calendar scopes
- **Amazon Bedrock** — AWS — Active; requires free-tier account with Bedrock model access enabled

### Open Questions

- [Yes] Should the agent store any calendar data persistently, or always fetch live from Google?
- [ask for clarification] What happens when the user's request is ambiguous — does the agent ask for clarification or make a best guess and confirm?
- [No] Is there a need for conversation history / memory across sessions?
- [It should yes] Should the MVP support recurring event creation, or single events only?
- [Just a respons saying something bad happened and demand the user clarification] What is the fallback behaviour when Bedrock is unavailable or returns an error?
