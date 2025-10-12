# Feedback & Community Roadmap Platform

**Feature Specification and Implementation Plan**

---

## 1. Feature Overview

A self-contained system for collecting, prioritizing, and acting on user feedback directly within KlineMatrix. The platform enables authenticated users to submit feature requests and bug reports, vote on existing items, and engage in discussions through a transparent, data-driven roadmap.

**Key Goals:**
- Keep the entire feedback loop within our ecosystem
- Foster strong community engagement
- Provide AI-ready, machine-readable data
- Enable data-driven product decisions

---

## 2. Current Project Structure Analysis

### Backend Architecture
- **Framework**: FastAPI with async/await
- **Layers**: API → Service → Repository → Database
- **Authentication**: JWT-based with dependency injection
  - `get_current_user_id()`: Extract user_id from JWT
  - `get_current_user()`: Get full User object
  - `require_admin()`: Admin-only endpoints
- **Database**: Motor (async MongoDB client)
- **Models**: Pydantic for validation/serialization
- **Patterns**: Repository pattern for data access
- **Logging**: Structured logging with structlog

### Frontend Architecture
- **Framework**: React 18 + TypeScript 5
- **Navigation**: Tab-based state (`activeTab: "health" | "chat"`)
- **Auth**: localStorage token storage via `authService`
- **Styling**: TailwindCSS with glassmorphism design
- **State**: React Query for server state (used in chat feature)
- **Markdown**: react-markdown with remark-gfm

### Database Patterns
- **Collections**: users, chats, messages, refresh_tokens
- **ID Strategy**: Custom IDs (e.g., `chat_abc123`)
- **Repository Layer**: Async methods for CRUD operations
- **Motor**: AsyncIOMotorCollection for MongoDB

---

## 3. Technical Design Decisions

### 3.1 Vote Counting Strategy
**Problem**: Unbounded arrays in MongoDB cause performance degradation and eventually hit document size limits (16MB).

**Solution**: Atomic counters + separate user vote tracking
- `FeedbackItem.voteCount`: Number field, updated atomically (`$inc`)
- `User.feedbackVotes`: Array of voted item IDs (for UI state)
- **Performance**: O(1) vote count updates, no document size issues

### 3.2 Comments Architecture
**Problem**: Embedded comments create unbounded arrays in FeedbackItems.

**Solution**: Separate Comments collection
- Each comment is a document with `itemId` reference
- Indexed on `itemId` for fast retrieval
- Supports pagination and sorting
- No impact on FeedbackItem document size

### 3.3 Content Format
**Standard**: Markdown for all user-generated content
- **Why**: Portable, structured, LLM-friendly
- **Libraries**:
  - Backend: Store as plain text
  - Frontend: `react-markdown` + `remark-gfm`
- **Benefit**: AI agents can parse and analyze easily

### 3.4 AI Integration
**Design Principles**:
1. **API-First**: Primary interface for agents is structured JSON
2. **Type Field**: Enum (`feature` | `bug`) for agent decision-making
3. **Status Tracking**: Clear workflow states
4. **Export Endpoint**: Snapshot capability for batch processing

---

## 4. Database Schema

### 4.1 FeedbackItems Collection

```json
{
  "_id": ObjectId("..."),
  "item_id": "feedback_abc123",
  "title": "Add dark mode toggle",
  "description": "## Problem\nUsers want dark mode...",
  "authorId": "user_xyz789",
  "type": "feature",  // Enum: "feature" | "bug"
  "status": "under_consideration",  // Enum: "under_consideration" | "planned" | "in_progress" | "completed"
  "voteCount": 42,  // Atomic counter
  "commentCount": 8,  // Atomic counter
  "createdAt": ISODate("2025-10-12T10:00:00Z"),
  "updatedAt": ISODate("2025-10-12T15:30:00Z")
}
```

**Indexes**:
- `item_id`: Unique
- `type`: Filter by feature/bug
- `voteCount`: Sort by votes (descending)
- `createdAt`: Sort by date

### 4.2 Comments Collection

```json
{
  "_id": ObjectId("..."),
  "comment_id": "comment_abc123",
  "itemId": "feedback_abc123",  // Reference to FeedbackItems
  "authorId": "user_xyz789",
  "content": "I agree, this would be very useful!",
  "createdAt": ISODate("2025-10-12T11:00:00Z")
}
```

**Indexes**:
- `comment_id`: Unique
- `itemId`: Filter comments for an item (fast lookup)
- `createdAt`: Sort by date

### 4.3 Users Collection (Modification)

**Add new field**:
```json
{
  ...existing fields...,
  "feedbackVotes": ["feedback_abc123", "feedback_xyz789"]  // Array of voted item IDs
}
```

**Purpose**: Track which items a user has voted on for UI state (show/hide vote button).

---

## 5. Backend Implementation Plan

### 5.1 Models (`backend/src/models/feedback.py`)

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Enums
FeedbackType = Literal["feature", "bug"]
FeedbackStatus = Literal["under_consideration", "planned", "in_progress", "completed"]

# Request Models
class FeedbackItemCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=10000)
    type: FeedbackType

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

# Response Models
class FeedbackItem(BaseModel):
    item_id: str
    title: str
    description: str
    authorId: str
    type: FeedbackType
    status: FeedbackStatus
    voteCount: int
    commentCount: int
    createdAt: datetime
    updatedAt: datetime

    # Computed field for user context
    hasVoted: bool = False  # Set by service layer

class Comment(BaseModel):
    comment_id: str
    itemId: str
    authorId: str
    content: str
    createdAt: datetime

    # Author info (joined from users collection)
    authorUsername: str | None = None
```

### 5.2 Repositories

**`backend/src/database/repositories/feedback_repository.py`**
- `create(item: FeedbackItemCreate, authorId: str) -> FeedbackItem`
- `get_by_id(item_id: str) -> FeedbackItem | None`
- `list_by_type(type: FeedbackType, skip: int, limit: int) -> list[FeedbackItem]`
- `increment_vote_count(item_id: str, delta: int) -> bool`
- `increment_comment_count(item_id: str) -> bool`
- `get_all() -> list[FeedbackItem]`  # For export

**`backend/src/database/repositories/comment_repository.py`**
- `create(comment: CommentCreate, itemId: str, authorId: str) -> Comment`
- `list_by_item(itemId: str) -> list[Comment]`

**`backend/src/database/repositories/user_repository.py` (Modification)**
- `add_vote(user_id: str, item_id: str) -> bool`
- `remove_vote(user_id: str, item_id: str) -> bool`
- `get_user_votes(user_id: str) -> list[str]`

### 5.3 Service Layer

**`backend/src/services/feedback_service.py`**
- **Purpose**: Orchestrate repositories, business logic
- **Methods**:
  - `create_item(item: FeedbackItemCreate, authorId: str) -> FeedbackItem`
  - `get_item(item_id: str, user_id: str | None) -> FeedbackItem`
    - Inject `hasVoted` field based on user's votes
  - `list_items(type: FeedbackType, user_id: str | None) -> list[FeedbackItem]`
    - Inject `hasVoted` for each item
  - `vote_item(item_id: str, user_id: str) -> bool`
    - Check if already voted (idempotent)
    - Increment vote count atomically
    - Add to user's feedbackVotes
  - `unvote_item(item_id: str, user_id: str) -> bool`
    - Decrement vote count
    - Remove from user's feedbackVotes
  - `add_comment(itemId: str, comment: CommentCreate, authorId: str) -> Comment`
    - Create comment
    - Increment commentCount on item
  - `get_comments(itemId: str) -> list[Comment]`
    - Join with users collection for author usernames
  - `export_all() -> str`  # Generate Markdown snapshot

### 5.4 API Endpoints (`backend/src/api/feedback.py`)

```python
router = APIRouter(prefix="/api/feedback", tags=["feedback"])

# CREATE
@router.post("/items", status_code=201)
async def create_feedback_item(
    item: FeedbackItemCreate,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackItem:
    """Create new feedback item (feature or bug)."""

# READ
@router.get("/items")
async def list_feedback_items(
    type: FeedbackType | None = None,
    user_id: str | None = Depends(get_current_user_id_optional),
    service: FeedbackService = Depends(get_feedback_service),
) -> list[FeedbackItem]:
    """List feedback items, optionally filtered by type."""

@router.get("/items/{item_id}")
async def get_feedback_item(
    item_id: str,
    user_id: str | None = Depends(get_current_user_id_optional),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackItem:
    """Get detailed view of a feedback item."""

# VOTE
@router.post("/items/{item_id}/vote", status_code=204)
async def vote_feedback_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
):
    """Cast a vote for a feedback item."""

@router.delete("/items/{item_id}/vote", status_code=204)
async def unvote_feedback_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
):
    """Remove vote from a feedback item."""

# COMMENTS
@router.post("/items/{item_id}/comments", status_code=201)
async def add_comment(
    item_id: str,
    comment: CommentCreate,
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
) -> Comment:
    """Add a comment to a feedback item."""

@router.get("/items/{item_id}/comments")
async def get_comments(
    item_id: str,
    service: FeedbackService = Depends(get_feedback_service),
) -> list[Comment]:
    """Get all comments for a feedback item."""

# EXPORT (Admin or AI agent)
@router.get("/export")
async def export_feedback(
    user_id: str = Depends(get_current_user_id),
    service: FeedbackService = Depends(get_feedback_service),
) -> str:
    """Generate Markdown snapshot of all feedback."""
```

**Note**: Need to create `get_current_user_id_optional` dependency for public endpoints.

---

## 6. Frontend Implementation Plan

### 6.1 Navigation Update (`frontend/src/App.tsx`)

**Changes**:
1. Update `activeTab` type: `"health" | "chat" | "feedback"`
2. Add "Feedback" button in navigation
3. Add route for feedback page

```tsx
const [activeTab, setActiveTab] = useState<"health" | "chat" | "feedback">("chat");

// In navigation:
<button onClick={() => setActiveTab("feedback")}>
  Feedback
</button>

// In main:
{activeTab === "feedback" && <FeedbackPage />}
```

### 6.2 Page Component (`frontend/src/pages/FeedbackPage.tsx`)

**Structure**:
```tsx
export function FeedbackPage() {
  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <PageHeader />
      <SubmitButton />
      <DualLeaderboards />
    </div>
  );
}
```

### 6.3 Leaderboard Components

**`frontend/src/components/feedback/FeedbackLeaderboard.tsx`**
- Props: `type: "feature" | "bug"`
- Fetch items from API
- Display list with vote counts, comment counts
- Vote button (toggle vote)
- Click item → navigate to detail view

```tsx
interface FeedbackLeaderboardProps {
  type: "feature" | "bug";
}

export function FeedbackLeaderboard({ type }: FeedbackLeaderboardProps) {
  const { data: items, isLoading } = useQuery({
    queryKey: ["feedback", type],
    queryFn: () => api.listFeedbackItems(type),
  });

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">
        {type === "feature" ? "Feature Requests" : "Bug Reports"}
      </h2>
      {items?.map(item => (
        <FeedbackListItem key={item.item_id} item={item} />
      ))}
    </div>
  );
}
```

**`frontend/src/components/feedback/FeedbackListItem.tsx`**
- Display title, status badge, vote count, comment count
- Vote button with optimistic updates
- Click → navigate to detail page

### 6.4 Detail View (`frontend/src/pages/FeedbackDetailPage.tsx`)

**Structure**:
1. Back button
2. Header (title, status, vote button)
3. Description (Markdown rendering)
4. Comment section
5. Comment form

**Markdown Rendering**:
```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

<ReactMarkdown remarkPlugins={[remarkGfm]}>
  {item.description}
</ReactMarkdown>
```

### 6.5 Forms

**`frontend/src/components/feedback/SubmitFeedbackForm.tsx`**
- Modal/drawer component
- Fields: title, description (textarea), type (radio: feature/bug)
- Markdown preview (optional for MVP)

**`frontend/src/components/feedback/CommentForm.tsx`**
- Simple textarea for comment
- Submit button
- Markdown support (plain textarea, renders on submit)

### 6.6 API Client (`frontend/src/services/feedbackApi.ts`)

```typescript
export const feedbackApi = {
  listItems: (type?: "feature" | "bug") =>
    api.get(`/api/feedback/items${type ? `?type=${type}` : ""}`),

  getItem: (itemId: string) =>
    api.get(`/api/feedback/items/${itemId}`),

  createItem: (data: FeedbackItemCreate) =>
    api.post("/api/feedback/items", data),

  voteItem: (itemId: string) =>
    api.post(`/api/feedback/items/${itemId}/vote`),

  unvoteItem: (itemId: string) =>
    api.delete(`/api/feedback/items/${itemId}/vote`),

  getComments: (itemId: string) =>
    api.get(`/api/feedback/items/${itemId}/comments`),

  addComment: (itemId: string, content: string) =>
    api.post(`/api/feedback/items/${itemId}/comments`, { content }),
};
```

---

## 7. Implementation Phases

### Phase 1: Backend Foundation (Day 1-2)
1. Create Pydantic models (`feedback.py`)
2. Create repositories (feedback, comment, user modifications)
3. Create service layer (`feedback_service.py`)
4. Create API endpoints (`api/feedback.py`)
5. Add dependency injection setup
6. Test all endpoints with curl/Postman

**Deliverable**: Fully functional backend API

### Phase 2: Frontend - Leaderboards (Day 3-4)
1. Update navigation in `App.tsx`
2. Create `FeedbackPage.tsx`
3. Create `FeedbackLeaderboard.tsx`
4. Create `FeedbackListItem.tsx`
5. Implement voting with optimistic updates
6. Create submit form modal

**Deliverable**: Working leaderboards with voting

### Phase 3: Frontend - Detail View (Day 5)
1. Add routing for detail view (or modal)
2. Create `FeedbackDetailPage.tsx`
3. Implement Markdown rendering
4. Create comment section
5. Create comment form

**Deliverable**: Complete feedback loop

### Phase 4: Polish & Testing (Day 6)
1. Add loading states and error handling
2. Improve UI/UX (animations, transitions)
3. Add empty states
4. Test voting race conditions
5. Test comment threading
6. Add export endpoint (admin only)

**Deliverable**: Production-ready feature

### Phase 5: AI Integration (Future)
1. Create AI agent client for feedback API
2. Implement auto-categorization (feature vs bug)
3. Implement sentiment analysis on comments
4. Auto-generate feature spec from high-voted items

---

## 8. File Structure

```
backend/
├── src/
│   ├── models/
│   │   └── feedback.py (NEW)
│   ├── database/
│   │   └── repositories/
│   │       ├── feedback_repository.py (NEW)
│   │       ├── comment_repository.py (NEW)
│   │       └── user_repository.py (MODIFY)
│   ├── services/
│   │   └── feedback_service.py (NEW)
│   └── api/
│       ├── dependencies/
│       │   └── feedback_deps.py (NEW)
│       └── feedback.py (NEW)

frontend/
├── src/
│   ├── pages/
│   │   ├── FeedbackPage.tsx (NEW)
│   │   └── FeedbackDetailPage.tsx (NEW)
│   ├── components/
│   │   └── feedback/
│   │       ├── FeedbackLeaderboard.tsx (NEW)
│   │       ├── FeedbackListItem.tsx (NEW)
│   │       ├── SubmitFeedbackForm.tsx (NEW)
│   │       ├── CommentSection.tsx (NEW)
│   │       └── CommentForm.tsx (NEW)
│   ├── services/
│   │   └── feedbackApi.ts (NEW)
│   └── App.tsx (MODIFY)
```

---

## 9. Testing Strategy

### Backend Tests
```python
# tests/test_feedback.py
- test_create_feedback_item()
- test_vote_idempotency()  # Vote twice → no double count
- test_atomic_vote_counting()  # Concurrent votes
- test_comment_creation()
- test_markdown_export()
```

### Frontend Tests
```typescript
// tests/FeedbackLeaderboard.test.tsx
- renders leaderboard correctly
- handles voting optimistically
- filters by type correctly
```

---

## 10. Success Metrics

1. **Engagement**: % of active users who vote or comment
2. **Feedback Quality**: Average votes per item (indicates resonance)
3. **Response Time**: Time from submission to status update
4. **AI Readiness**: Export endpoint usage by automation tools
5. **Community Growth**: Month-over-month increase in submissions

---

## 11. Future Enhancements

1. **Notifications**: Email users when their item status changes
2. **Tags**: Add tags for categorization (e.g., #ui, #performance)
3. **Attachments**: Allow image uploads for bug reports
4. **Upvote Threshold**: Auto-promote items to "Planned" at 50 votes
5. **AI Auto-Response**: LLM generates initial response to new items
6. **GitHub Integration**: Auto-create GitHub issues from high-voted items

---

## 12. Open Questions

1. **Navigation**: Tab-based or separate route?
   - **Recommendation**: Tab-based (simpler, consistent with current app)

2. **Detail View**: Modal or dedicated page?
   - **Recommendation**: Dedicated page (better for sharing links)

3. **Vote Button**: Heart, thumbs up, or +1?
   - **Recommendation**: Thumbs up (universal, simple)

4. **Comment Threading**: Flat or nested?
   - **Recommendation**: Flat for MVP (simpler), nested later

5. **Export Format**: JSON or Markdown?
   - **Recommendation**: Markdown (more portable, LLM-friendly)

---

## 13. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Vote count race conditions | High | Use atomic `$inc` operations |
| Unbounded comment arrays | High | Separate Comments collection |
| Spam submissions | Medium | Rate limiting per user |
| Inappropriate content | Medium | Admin moderation queue (future) |
| MongoDB document size limit | Low | Separate collections, no embedded arrays |

---

## 14. Dependencies

**Backend**:
- motor (already installed)
- structlog (already installed)
- fastapi (already installed)

**Frontend**:
- react-markdown (already installed)
- remark-gfm (already installed)
- @tanstack/react-query (already installed)

**No new dependencies required!**

---

## 15. Acceptance Criteria

### Must Have (MVP)
- [x] Authenticated users can submit feedback
- [x] Two separate leaderboards (features/bugs)
- [x] Vote/unvote functionality
- [x] Comment on feedback items
- [x] Markdown rendering for descriptions
- [x] API-first design for AI integration

### Nice to Have
- [ ] Real-time vote count updates (WebSocket)
- [ ] Markdown preview in forms
- [ ] Export endpoint for admin
- [ ] Comment edit/delete
- [ ] Status update history

---

## Implementation Ready ✅

This feature is fully specified and ready for implementation. All technical decisions are made, file structure is clear, and patterns match existing codebase conventions.
