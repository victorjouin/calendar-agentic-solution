# Unit Test Execution — Calendar-Agent

---

## Overview

The test suite covers all four backend modules with mocked external dependencies (AWS SSM, Google Calendar API, Amazon Bedrock). No real AWS or Google credentials are needed to run unit tests.

**Test files:**

| File | Module Under Test | Test Count |
|------|------------------|------------|
| `tests/test_auth_manager.py` | `backend/auth_manager.py` | ~15 tests |
| `tests/test_calendar_client.py` | `backend/calendar_client.py` | ~15 tests |
| `tests/test_bedrock_client.py` | `backend/bedrock_client.py` | ~10 tests |
| `tests/test_orchestrator.py` | `backend/orchestrator.py` | ~20 tests |

---

## Step 1: Install Test Dependencies

```bash
# From workspace root, with virtual environment activated
pip install pytest pytest-cov
```

---

## Step 2: Run All Unit Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Expected output:
# tests/test_auth_manager.py::TestExchangeCodeForTokens::test_success PASSED
# tests/test_auth_manager.py::TestExchangeCodeForTokens::test_failure_raises_value_error PASSED
# ...
# ===== X passed in Y.XXs =====
```

---

## Step 3: Run Tests with Coverage Report

```bash
# Run with coverage (HTML report)
pytest tests/ -v \
  --cov=backend \
  --cov-report=term-missing \
  --cov-report=html:coverage-report

# View HTML report
# Open coverage-report/index.html in a browser
```

**Expected coverage targets:**

| Module | Target Coverage |
|--------|----------------|
| `auth_manager.py` | ≥ 85% |
| `calendar_client.py` | ≥ 80% |
| `bedrock_client.py` | ≥ 85% |
| `orchestrator.py` | ≥ 80% |
| Overall | ≥ 80% |

---

## Step 4: Run a Specific Test File

```bash
# Run only auth manager tests
pytest tests/test_auth_manager.py -v

# Run only orchestrator tests
pytest tests/test_orchestrator.py -v

# Run a specific test class
pytest tests/test_orchestrator.py::TestProcessMessageDelete -v

# Run a specific test
pytest tests/test_orchestrator.py::TestProcessMessageDelete::test_delete_with_confirmation_on_returns_prompt -v
```

---

## Step 5: Review Test Results

**All tests should pass.** If any fail:

1. Read the failure output — pytest shows the exact assertion that failed
2. Check if the failure is in the test logic or the module under test
3. Common causes:
   - Import errors → check `backend/__init__.py` exists
   - Mock not applied correctly → check `patch` target paths match actual import paths
   - Assertion mismatch → check the expected value matches the actual implementation

---

## Key Test Scenarios Covered

### AuthManager
- ✅ Token exchange success and failure
- ✅ Token storage in SSM (SecureString)
- ✅ Token loading — found and not found (ParameterNotFound)
- ✅ Valid token returned without refresh
- ✅ Expired token triggers automatic refresh
- ✅ No tokens → `ReAuthRequiredException`
- ✅ Invalid refresh token (400/401) → `ReAuthRequiredException`

### CalendarClient
- ✅ Cache hit returns cached events without API call
- ✅ Cache miss fetches from Google API and populates cache
- ✅ Create event invalidates cache
- ✅ Update event invalidates cache
- ✅ Delete event invalidates cache
- ✅ Recurring event creation includes RRULE in API body
- ✅ Free slot finder respects working hours
- ✅ Free slot finder respects buffer time
- ✅ Returns max 3 suggestions
- ✅ All-day event parsing

### BedrockClient
- ✅ System prompt includes working hours, buffer, confirmation mode
- ✅ Valid JSON response parsed correctly
- ✅ JSON in markdown code block extracted and parsed
- ✅ Invalid JSON falls back to `chat` action
- ✅ Unknown action defaults to `chat`
- ✅ `needs_clarification: true` propagated
- ✅ Bedrock `ClientError` raises `RuntimeError` with user-friendly message
- ✅ Conversation history passed correctly to Bedrock API

### Orchestrator
- ✅ `create_new_session()` creates session with config defaults
- ✅ Working hours updated from natural language
- ✅ Confirmation mode disabled/enabled from natural language
- ✅ Buffer time updated from natural language
- ✅ Unrelated message leaves preferences unchanged
- ✅ Read action returns formatted event summary
- ✅ Read action on empty calendar returns appropriate message
- ✅ Delete with confirmation ON returns confirmation prompt
- ✅ Delete with confirmation OFF executes immediately
- ✅ Ambiguous delete presents numbered options
- ✅ Event not found returns helpful message
- ✅ "yes" confirms pending delete
- ✅ "no" cancels pending action
- ✅ Slot selection creates event
- ✅ Chat action returns model reply
- ✅ Bedrock error returns friendly message
- ✅ Conversation history grows with each turn
