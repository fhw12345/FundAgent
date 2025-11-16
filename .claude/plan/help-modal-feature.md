# Help Modal Feature - Implementation Plan

## Context

**User Request:** Add a floating help button on the main page with a modal explaining three usage modes:
1. **Agent Mode** - Outline tools the agent automatically calls and summarize with suggestions
2. **Copilot Mode** - User clicks analysis buttons to see charts, AI helps understand
3. **Portfolio Agent** - Navigate to portfolio page to view simulated transactions and P&L

**Requirements:**
- Floating button (bottom-right corner)
- Modal with step-by-step flows
- Color-coded sections (Blue/Purple/Green)
- Stylish design matching existing aesthetics
- Text-only explanations (no interactive elements)

## Problem Statement

New users need guidance on how to use the Financial Agent platform's three different modes. Currently, there's no in-app help or onboarding flow explaining:
- What each mode does
- How to use each mode
- When to use each mode

## Proposed Solution

**Solution 1: Single Scrollable Modal with Color-Coded Sections** (Approved)

Create a floating help button that opens a stylish modal with three distinct color-coded sections, each containing:
- Concise description
- Visual flow diagram
- Step-by-step guidance

## Implementation Plan

### File Structure
```
frontend/src/
├── components/
│   ├── HelpModal.tsx          # NEW: Main help modal component
│   └── EnhancedChatInterface.tsx  # Existing (no changes)
└── App.tsx                     # MODIFY: Add floating button + modal state
```

### Step 1: Create HelpModal Component
**File:** `frontend/src/components/HelpModal.tsx`

**Component Interface:**
```typescript
interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}
```

**Features:**
- Modal backdrop with blur effect
- Three color-coded sections:
  - Agent Mode (Blue gradient: from-blue-500 to-blue-600)
  - Copilot Mode (Purple gradient: from-purple-500 to-purple-600)
  - Portfolio Agent (Green gradient: from-green-500 to-green-600)
- Flow diagrams with arrows and step indicators
- Close on backdrop click or X button
- Responsive design (mobile + desktop)

### Step 2: Add to App.tsx
**File:** `frontend/src/App.tsx`

**Changes:**
1. Import HelpModal component
2. Add state: `const [isHelpModalOpen, setIsHelpModalOpen] = useState(false)`
3. Add floating help button (bottom-right, fixed position)
4. Render HelpModal component

### Step 3: Testing
- Verify modal opens/closes correctly
- Check responsive design on mobile/desktop
- Validate TypeScript types
- Run linting and type-check
- Test z-index layering with other modals

## Color Scheme

| Mode | Gradient | Badge Color | Icon |
|------|----------|-------------|------|
| Agent Mode | from-blue-500 to-blue-600 | bg-blue-100 text-blue-700 | Bot/Sparkles |
| Copilot Mode | from-purple-500 to-purple-600 | bg-purple-100 text-purple-700 | MessageSquare |
| Portfolio Agent | from-green-500 to-green-600 | bg-green-100 text-green-700 | TrendingUp |

## Acceptance Criteria

- [ ] Floating help button visible on all pages
- [ ] Modal opens on button click
- [ ] Modal closes on backdrop/X click
- [ ] Three color-coded sections render correctly
- [ ] Flow diagrams are clear and concise
- [ ] Responsive on mobile (375px) and desktop (1920px)
- [ ] No TypeScript errors
- [ ] No linting issues
- [ ] Matches existing design system

## Implementation Notes

- Use lucide-react icons (already installed)
- Follow existing modal pattern (see SubmitFeedbackForm.tsx)
- Match glassmorphism design (backdrop-blur, shadows)
- Ensure z-index layering: button (z-40), modal (z-50)
