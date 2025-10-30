# Feature: Feedback Image Attachments

> **Status**: Draft
> **Created**: 2025-10-30
> **Last Updated**: 2025-10-30
> **Owner**: Financial Agent Team

## Context

Users need the ability to attach screenshots and images when submitting feedback to better illustrate bugs, UI issues, or feature suggestions. Currently, feedback is limited to text-only descriptions, which makes it harder to understand visual problems.

**User Story**:
As a user reporting a bug or UI issue, I want to attach screenshots directly to my feedback, so that developers can see exactly what I'm describing without additional back-and-forth communication.

**Background**:
- Current feedback form only accepts title and description (text)
- Users mentioned: "Feedback should support image attachments"
- Common use cases:
  - UI layout bugs (collapse arrow obscured, table formatting issues)
  - Chart rendering problems
  - Visual design suggestions
  - Mobile responsiveness issues

**Related Features**:
- Feedback Platform (existing: `/docs/features/feedback-platform.md`)
- Alibaba Cloud OSS storage (already configured for Langfuse)

---

## Problem Statement

**Current Limitations**:
1. ❌ No way to attach screenshots to feedback
2. ❌ Developers must recreate reported issues without visual context
3. ❌ Increases back-and-forth communication for visual bugs
4. ❌ Reduces feedback quality and actionability

**Impact**:
- Slower bug resolution times
- Misinterpretation of user feedback
- Frustration from users trying to describe visual issues in text

---

## Proposed Solution

### High-Level Approach

Add image upload capability to the feedback submission form, with files stored in Alibaba Cloud OSS (same bucket as Langfuse events).

**Key Components**:
1. **Frontend**: File input with drag-and-drop support
2. **Backend**: File upload endpoint with validation
3. **Storage**: Use existing OSS bucket (`langfuse-events-prod`)
4. **Database**: Store OSS URLs in feedback items
5. **Display**: Show thumbnails in feedback list/detail views

### Technical Architecture

```
User Browser
    ↓ (Upload image)
Frontend Form (/src/components/feedback/SubmitFeedbackForm.tsx)
    ↓ (POST /api/feedback/upload-attachment)
Backend API (/api/feedback.py)
    ↓ (Validate + Upload)
OSS Service (/services/oss_service.py)
    ↓ (Store file)
Alibaba Cloud OSS (langfuse-events-prod/feedback-attachments/)
    ↓ (Return URL)
MongoDB (feedback collection)
    ↓ (Store attachment URLs)
Feedback Detail View
    ↓ (Display images)
User/Admin
```

### Data Flow

1. **Upload Phase**:
   - User selects image(s) → Frontend validates type/size
   - Upload to `/api/feedback/upload-attachment` → Returns OSS URL
   - Frontend stores URL in form state

2. **Submission Phase**:
   - User submits feedback → Includes attachment URLs
   - Backend validates URLs are from our OSS bucket
   - Save feedback with `attachments: [url1, url2, ...]`

3. **Display Phase**:
   - Feedback list shows thumbnail previews
   - Click to view full-size image in new tab
   - 7-day signed URLs for secure access

---

## Implementation Plan

### Phase 1: Backend Storage Setup (Day 1-2)

**Files to Modify**:
- `backend/src/core/config.py`
  - Add `feedback_attachments_prefix: str = "feedback-attachments/"`
  - Add `max_attachment_size_mb: int = 10`
  - Add `allowed_attachment_types: list[str] = ["image/png", "image/jpeg", ...]`

**Files to Create**:
- `backend/src/services/oss_service.py`
  - `OSSService` class
  - `upload_feedback_attachment(file, filename, content_type) -> url`
  - Use `oss2` library (already installed for Langfuse)

**Configuration**:
```python
# Use existing OSS credentials:
OSS_ACCESS_KEY_ID = <REDACTED>
OSS_SECRET_ACCESS_KEY = <REDACTED>
OSS_BUCKET = "langfuse-events-prod"
OSS_ENDPOINT = "https://oss-cn-hangzhou.aliyuncs.com"
```

### Phase 2: Backend Model & API (Day 2-3)

**Files to Modify**:
- `backend/src/models/feedback.py`
  - Add `attachments: list[str] = Field(default=[], max_items=5)` to `FeedbackItemCreate`
  - Add `attachments: list[str] = []` to `FeedbackItem`

- `backend/src/api/feedback.py`
  - Add `POST /api/feedback/upload-attachment` endpoint
  - Validate file type (PNG, JPG, GIF, WebP only)
  - Validate file size (max 10MB)
  - Upload to OSS, return URL
  - Modify `POST /api/feedback/submit` to validate attachment URLs

- `backend/src/services/feedback_service.py`
  - Update `create_feedback()` to handle attachments

**Validation Rules**:
```python
- Max 5 attachments per feedback
- Max 10MB per file
- Allowed types: image/png, image/jpeg, image/gif, image/webp
- URLs must match pattern: https://langfuse-events-prod.oss-cn-hangzhou.aliyuncs.com/feedback-attachments/*
```

### Phase 3: Frontend Form Enhancement (Day 4-5)

**Files to Modify**:
- `frontend/src/components/feedback/SubmitFeedbackForm.tsx`
  - Add `attachments: string[]` state
  - Add `uploadingFiles: boolean` state
  - Add file input (accept images, multiple)
  - Add upload handler → POST to `/api/feedback/upload-attachment`
  - Display uploaded images as thumbnails with remove button
  - Include attachments in form submission

- `frontend/src/types/feedback.ts`
  - Add `attachments?: string[]` to `FeedbackItemCreate`
  - Add `attachments: string[]` to `FeedbackItem`

**UI Components**:
```typescript
<input
  type="file"
  accept="image/png,image/jpeg,image/gif,image/webp"
  multiple
  onChange={handleFileUpload}
/>

<div className="grid grid-cols-2 gap-2">
  {attachments.map((url, index) => (
    <div className="relative group">
      <img src={url} className="thumbnail" />
      <button onClick={() => removeAttachment(index)}>
        <X size={16} />
      </button>
    </div>
  ))}
</div>
```

### Phase 4: Feedback Display Enhancement (Day 6)

**Files to Modify**:
- Create `frontend/src/components/feedback/FeedbackItem.tsx` (if not exists)
  - Display feedback title, description, type, date
  - Display attachments as thumbnails (3-column grid)
  - Click thumbnail → Open in new tab

**UI Layout**:
```
┌─────────────────────────────────────────┐
│ [BUG] UI collapse arrow partially hidden│
│ 2025-10-30 04:40 PM                     │
├─────────────────────────────────────────┤
│ Description: The collapse arrow on the  │
│ chart panel is cut off...               │
├─────────────────────────────────────────┤
│ Attachments:                            │
│ [img1] [img2] [img3]                    │
└─────────────────────────────────────────┘
```

---

## Data Models

### Backend (MongoDB)

```python
class FeedbackItem(BaseModel):
    id: str
    title: str
    description: str
    type: FeedbackType  # "bug" | "feature"
    attachments: list[str] = []  # NEW: OSS URLs
    created_at: datetime
    updated_at: datetime
    user_id: str | None = None
    status: str = "pending"  # pending, reviewed, resolved
```

### Frontend (TypeScript)

```typescript
interface FeedbackItemCreate {
  title: string;
  description: string;
  type: FeedbackType;
  attachments?: string[];  // NEW: OSS URLs
}

interface FeedbackItem {
  id: string;
  title: string;
  description: string;
  type: FeedbackType;
  attachments: string[];  // NEW
  created_at: string;
  updated_at: string;
  user_id: string | null;
  status: string;
}
```

---

## API Endpoints

### 1. Upload Attachment

```http
POST /api/feedback/upload-attachment
Content-Type: multipart/form-data

file: <binary data>

Response:
{
  "url": "https://langfuse-events-prod.oss-cn-hangzhou.aliyuncs.com/feedback-attachments/20251030-abc123.png"
}

Status Codes:
- 200: Success
- 400: Invalid file type or size
- 413: File too large
- 500: Upload failed
```

### 2. Submit Feedback (Modified)

```http
POST /api/feedback/submit
Content-Type: application/json

{
  "title": "UI collapse arrow partially hidden",
  "description": "The collapse button is cut off...",
  "type": "bug",
  "attachments": [
    "https://langfuse-events-prod.oss-cn-hangzhou.aliyuncs.com/feedback-attachments/20251030-abc123.png"
  ]
}

Response:
{
  "id": "feedback_123",
  "title": "...",
  "attachments": ["https://..."],
  "created_at": "2025-10-30T16:40:00Z"
}
```

---

## Security Considerations

### File Upload Security

1. **Type Validation**:
   - Only allow image MIME types
   - Verify content matches declared type (magic number check)
   - Block SVG (potential XSS risk)

2. **Size Limits**:
   - Max 10MB per file (prevent DoS)
   - Max 5 files per feedback (prevent storage abuse)
   - Total limit: 50MB per feedback

3. **Filename Sanitization**:
   - Generate unique filenames: `{timestamp}-{uuid}.{ext}`
   - Never use user-provided filenames directly

4. **URL Validation**:
   - Only accept URLs from our OSS bucket domain
   - Prevent injection of external URLs

5. **Access Control**:
   - Use signed URLs with 7-day expiration
   - Files not publicly listable (bucket permissions)

### Storage Security

```python
# OSS bucket configuration:
- Private bucket (not public-read)
- Generate signed URLs with expiration
- Separate prefix: feedback-attachments/
- Lifecycle policy: Delete after 90 days (optional)
```

---

## Performance Considerations

### Optimization Strategies

1. **Client-Side Image Compression**:
   - Resize large images before upload (max 1920px width)
   - Use browser Canvas API for compression
   - Target: <500KB per file after compression

2. **Lazy Loading**:
   - Load thumbnails on scroll (intersection observer)
   - Full-size images only on click

3. **CDN (Future Enhancement)**:
   - Use Alibaba Cloud CDN for faster image delivery
   - Cache-Control headers: `max-age=604800` (7 days)

4. **Thumbnail Generation (Future Enhancement)**:
   - Generate 200x200 thumbnails on upload
   - Store both original + thumbnail in OSS
   - Load thumbnails in lists, original on click

---

## Testing Strategy

### Unit Tests

```python
# backend/tests/test_oss_service.py
- test_upload_valid_image()
- test_upload_invalid_type()
- test_upload_oversized_file()
- test_generate_unique_filename()
- test_signed_url_generation()

# backend/tests/test_feedback_api.py
- test_upload_attachment_success()
- test_upload_attachment_invalid_type()
- test_submit_feedback_with_attachments()
- test_validate_attachment_urls()
```

### Integration Tests

```typescript
// frontend/tests/feedback.test.tsx
- Upload single image → Verify URL returned
- Upload multiple images → Verify all uploaded
- Remove attachment → Verify state updated
- Submit feedback with attachments → Verify saved
- Display feedback with attachments → Verify rendered
```

### Manual Testing Checklist

- [ ] Upload PNG, JPG, GIF, WebP (all should succeed)
- [ ] Upload PDF, TXT (should fail with error)
- [ ] Upload 11MB file (should fail with size error)
- [ ] Upload 6 files (should fail with max limit error)
- [ ] Remove attachment before submit (should exclude from submission)
- [ ] Submit feedback with 0, 1, 3, 5 attachments (all should work)
- [ ] View feedback in list (thumbnails display)
- [ ] Click thumbnail (opens full-size in new tab)
- [ ] Mobile responsive (file input works, thumbnails stack)

---

## Acceptance Criteria

### Must Have (MVP)

- [x] Users can upload 1-5 images per feedback
- [x] Supported formats: PNG, JPG, GIF, WebP
- [x] Max file size: 10MB per image
- [x] Images stored in Alibaba Cloud OSS
- [x] Feedback form shows uploaded thumbnails with remove button
- [x] Submitted feedback includes attachment URLs in database
- [x] Feedback display shows attachments as clickable thumbnails
- [x] Error handling for invalid files (type, size)
- [x] Loading states during upload

### Nice to Have (Future)

- [ ] Drag-and-drop file upload
- [ ] Client-side image compression
- [ ] Thumbnail generation on server
- [ ] Image annotation/markup tool
- [ ] Video attachment support
- [ ] Clipboard paste image support

---

## Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Storage costs escalate | Medium | Low | Implement 90-day lifecycle policy, monitor usage |
| Abuse (spam uploads) | High | Medium | Rate limiting, require authentication, max 5 files |
| Large file uploads slow down UX | Medium | High | Client-side compression, progress bars |
| OSS service downtime | High | Low | Graceful degradation, retry logic, queue uploads |
| XSS via SVG uploads | High | Medium | Block SVG, validate MIME types, sanitize metadata |

---

## Rollout Plan

### Development Phase (1 week)

1. **Day 1-2**: Backend storage + API endpoints
2. **Day 3-4**: Frontend form enhancements
3. **Day 5**: Feedback display updates
4. **Day 6**: Testing + bug fixes
5. **Day 7**: Documentation + deployment

### Deployment Strategy

1. **Test Environment**:
   - Deploy to K8s test namespace
   - Verify OSS connectivity
   - Test with real uploads

2. **Production Rollout** (when ready):
   - Deploy backend first (backward compatible)
   - Deploy frontend after backend validated
   - Monitor error rates and storage usage

### Monitoring

```bash
# Metrics to track:
- Upload success rate
- Average file size
- Total storage used (GB)
- Failed upload reasons (type, size, network)
- Feedback with vs without attachments (%)
```

---

## Dependencies

### External Services

- **Alibaba Cloud OSS**: Already configured for Langfuse
  - Bucket: `langfuse-events-prod`
  - Region: `cn-hangzhou`
  - Access via `oss2` Python library

### Python Libraries

- `oss2`: Already installed (used by Langfuse)
- `python-magic`: For MIME type validation (optional)

### Frontend Libraries

- No new dependencies needed
- Use native `<input type="file">` API
- Consider `react-dropzone` for drag-and-drop (optional)

---

## Success Metrics

### Quantitative

- **Target**: 50% of bug reports include screenshots within 30 days
- **Upload Success Rate**: >95%
- **Average Feedback Resolution Time**: Reduce by 30%
- **User Satisfaction**: Feedback form NPS score improves

### Qualitative

- Developers report better understanding of visual bugs
- Reduced back-and-forth in feedback discussions
- Improved bug reproduction rates

---

## Future Enhancements

1. **Video Attachments**: Support screen recordings (MP4, WebM)
2. **Image Annotation**: Allow users to mark up screenshots with arrows/text
3. **Clipboard Paste**: Paste images directly from clipboard
4. **Automatic Screenshots**: Browser extension to capture screenshots
5. **OCR for Text in Images**: Extract text from screenshots for search
6. **Thumbnail Generation**: Server-side thumbnail creation for faster loading

---

## References

- Existing Feedback Platform: `/docs/features/feedback-platform.md`
- Alibaba Cloud OSS Documentation: https://www.alibabacloud.com/help/en/oss
- OSS Python SDK: https://help.aliyun.com/document_detail/32026.html
- File Upload Best Practices: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
