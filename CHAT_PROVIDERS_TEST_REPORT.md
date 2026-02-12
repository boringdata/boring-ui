# BORING-UI: 4 CHAT PROVIDERS INTERACTIVE TEST REPORT

**Date:** February 11, 2026  
**Tool:** Rodney (Chrome Automation) + Manual Testing  
**Focus:** Testing each chat provider with actual message interaction

---

## TEST PLAN

Testing the 4 main chat providers available in boring-ui:
1. **Claude Code** - Direct Claude integration
2. **Sandbox** - Sandbox-agent provider
3. **Companion** - Companion server provider  
4. **Mock** - Mock/test provider

For each: Send message → Capture screenshot of response

---

## PROVIDER 1: CLAUDE CODE

### Setup
- ✓ Session created: "Session 1 - 20eda7cb"
- ✓ Provider selected: "Claude Code"
- ✓ Chat panel ready

### Test Message
```
Input: "Hello Claude! What is 2+2?"
```

### Evidence
- **Screenshot 2:** Message typed in input field
- **Screenshot 3:** Response from Claude Code

### Status
Testing in progress - awaiting response display

---

## PROVIDER 2: SANDBOX

### Setup
- Sandbox provider available
- Service running on localhost:2468
- Configuration verified

### Test Message
```
Input: "Hello Sandbox! What files are in this directory?"
```

### Screenshot Evidence
- Will capture sandbox response

---

## PROVIDER 3: COMPANION

### Setup
- Companion server running
- Configuration verified

### Test Message
```
Input: "Hello Companion! Can you help?"
```

### Screenshot Evidence  
- Will capture companion response

---

## PROVIDER 4: MOCK

### Setup
- Mock provider available for testing

### Test Message
```
Input: "Hello Mock! This is a test message"
```

### Screenshot Evidence
- Will capture mock response

---

## SCREENSHOTS CAPTURED

### Chat Provider Tests
1. `/tmp/chat-report-0-initial.png` - Initial layout
2. `/tmp/chat-report-1-shell-hidden.png` - Shell panel collapsed
3. `/tmp/chat-report-2-claude-message.png` - Claude message typed
4. `/tmp/chat-report-3-claude-response.png` - Claude response

(Additional screenshots for Sandbox, Companion, Mock providers to follow)

---

## TEST INFRASTRUCTURE

**Frontend:**
- URL: http://localhost:5173
- Status: ✓ Running
- React + Vite + DockView layout

**Backend:**
- URL: http://localhost:8000
- Status: ✓ Running  
- FastAPI with all providers enabled

**Providers Available:**
- ✓ Claude Code (chat-claude-code)
- ✓ Sandbox (port 2468)
- ✓ Companion (port 3456)
- ✓ Mock/Inspector

**Browser:**
- Tool: Rodney (Chrome automation)
- Status: ✓ Active

---

## CHAT PANEL DETAILS

### Location
- Right sidebar of DockView layout
- Shows "Session 1 - [session-id]"
- Selected provider name displayed

### Controls
- "/" - Slash commands
- "@" - Mention files  
- "Ask" button - Submit message
- "↑" button - Send

### Features
- Real-time message display
- Provider-specific formatting
- Session management

---

## NEXT STEPS

1. Complete Claude Code test - capture response
2. Test Sandbox provider - verify working
3. Test Companion provider - verify integration
4. Test Mock provider - verify functionality
5. Create final report with all screenshots

---

**Report Status:** IN PROGRESS  
**Test Focus:** Interactive chat functionality with screenshots  
**Last Updated:** 2026-02-11

