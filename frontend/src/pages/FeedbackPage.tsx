/**
 * Feedback & Community Roadmap Page
 * Displays dual leaderboards for feature requests and bug reports.
 */

import { useState } from "react";
import { FeedbackLeaderboard } from "../components/feedback/FeedbackLeaderboard";
import { SubmitFeedbackForm } from "../components/feedback/SubmitFeedbackForm";
import { FeedbackDetailView } from "../components/feedback/FeedbackDetailView";

export default function FeedbackPage() {
  const [isSubmitFormOpen, setIsSubmitFormOpen] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 py-8">
      <div className="max-w-7xl mx-auto px-6">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent mb-2">
            Feedback & Community Roadmap
          </h1>
          <p className="text-gray-600">
            Shape the future of KlineMatrix by voting on features and reporting
            bugs
          </p>
        </div>

        {/* Submit Button */}
        <div className="mb-8">
          <button
            onClick={() => setIsSubmitFormOpen(true)}
            className="px-6 py-3 bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/30 hover:shadow-xl hover:scale-105 transition-all duration-200"
          >
            Submit Feedback
          </button>
        </div>

        {/* Dual Leaderboards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Feature Requests */}
          <div>
            <FeedbackLeaderboard
              type="feature"
              onItemClick={setSelectedItemId}
            />
          </div>

          {/* Bug Reports */}
          <div>
            <FeedbackLeaderboard type="bug" onItemClick={setSelectedItemId} />
          </div>
        </div>
      </div>

      {/* Submit Feedback Modal */}
      {isSubmitFormOpen && (
        <SubmitFeedbackForm onClose={() => setIsSubmitFormOpen(false)} />
      )}

      {/* Detail View Modal */}
      {selectedItemId && (
        <FeedbackDetailView
          itemId={selectedItemId}
          onClose={() => setSelectedItemId(null)}
        />
      )}
    </div>
  );
}
