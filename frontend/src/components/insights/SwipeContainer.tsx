/**
 * SwipeContainer component for handling swipe gestures.
 * Enables swipe-left gesture to load more historical data.
 */

import { useState, useCallback, type ReactNode, type TouchEvent } from "react";
import { ChevronLeft } from "lucide-react";

interface SwipeContainerProps {
  /** Child elements to render */
  children: ReactNode;
  /** Callback fired when user swipes left */
  onSwipeLeft?: () => void;
  /** Minimum swipe distance in pixels to trigger callback */
  threshold?: number;
  /** Whether to show the swipe hint indicator */
  showHint?: boolean;
  /** Custom CSS class name */
  className?: string;
}

/**
 * Container that detects left swipe gestures.
 * Useful for "swipe left for more history" interactions.
 */
export function SwipeContainer({
  children,
  onSwipeLeft,
  threshold = 50,
  showHint = false,
  className = "",
}: SwipeContainerProps) {
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [touchDelta, setTouchDelta] = useState<number>(0);
  const [isSwiping, setIsSwiping] = useState(false);

  const handleTouchStart = useCallback((e: TouchEvent) => {
    setTouchStart(e.touches[0].clientX);
    setIsSwiping(true);
  }, []);

  const handleTouchMove = useCallback(
    (e: TouchEvent) => {
      if (touchStart === null) return;
      const currentX = e.touches[0].clientX;
      const delta = touchStart - currentX;
      setTouchDelta(Math.max(0, delta)); // Only track left swipes
    },
    [touchStart]
  );

  const handleTouchEnd = useCallback(() => {
    if (touchStart === null) return;

    // Trigger callback if swipe exceeds threshold
    if (touchDelta > threshold && onSwipeLeft) {
      onSwipeLeft();
    }

    // Reset state
    setTouchStart(null);
    setTouchDelta(0);
    setIsSwiping(false);
  }, [touchStart, touchDelta, threshold, onSwipeLeft]);

  const handleTouchCancel = useCallback(() => {
    setTouchStart(null);
    setTouchDelta(0);
    setIsSwiping(false);
  }, []);

  // Calculate visual feedback (subtle transform)
  const translateX = isSwiping ? Math.min(touchDelta * 0.2, 20) : 0;

  return (
    <div
      className={`relative ${className}`}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchCancel}
    >
      {/* Main content with subtle transform feedback */}
      <div
        style={{
          transform: `translateX(-${translateX}px)`,
          transition: isSwiping ? "none" : "transform 0.2s ease-out",
        }}
      >
        {children}
      </div>

      {/* Swipe hint indicator - only visible on touch devices during interaction */}
      {showHint && isSwiping && touchDelta > 10 && (
        <div className="absolute right-0 top-1/2 -translate-y-1/2 flex items-center gap-0.5 text-blue-500 text-xs animate-pulse">
          <ChevronLeft className="w-3 h-3" />
        </div>
      )}

      {/* Progress indicator during swipe */}
      {isSwiping && touchDelta > 0 && (
        <div
          className="absolute right-0 top-0 bottom-0 flex items-center justify-center bg-gradient-to-l from-blue-50 to-transparent"
          style={{
            width: Math.min(touchDelta, 60),
            opacity: Math.min(touchDelta / threshold, 1),
          }}
        >
          {touchDelta > threshold && (
            <ChevronLeft className="w-4 h-4 text-blue-500" />
          )}
        </div>
      )}
    </div>
  );
}

export default SwipeContainer;
