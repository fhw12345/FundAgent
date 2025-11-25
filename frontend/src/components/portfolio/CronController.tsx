import React, { useState, useEffect } from 'react';
import { Clock, Play, Pause, RefreshCw } from 'lucide-react';

interface CronControllerProps {
  intervalMinutes: number;
  enabled: boolean;
  onToggle?: (enabled: boolean) => void;
  onIntervalChange?: (minutes: number) => void;
}

/**
 * CronController - Visual countdown and controls for portfolio analysis cron job.
 *
 * Features:
 * - Real-time countdown to next execution
 * - Enable/disable toggle
 * - Interval selector for testing (5 min - 24 hours)
 * - Visual status indicators
 */
export function CronController({
  intervalMinutes,
  enabled,
  onToggle,
  onIntervalChange,
}: CronControllerProps) {
  const [countdown, setCountdown] = useState<string>('');
  const [nextRun, setNextRun] = useState<Date | null>(null);

  // Calculate next run time based on interval
  useEffect(() => {
    if (enabled) {
      const now = new Date();
      const next = new Date(now.getTime() + intervalMinutes * 60 * 1000);
      setNextRun(next);
    } else {
      setNextRun(null);
    }
  }, [intervalMinutes, enabled]);

  // Update countdown every second
  useEffect(() => {
    if (!nextRun || !enabled) {
      setCountdown('--:--:--');
      return;
    }

    const interval = setInterval(() => {
      const now = new Date();
      const diff = nextRun.getTime() - now.getTime();

      if (diff <= 0) {
        setCountdown('Running now...');
        // Recalculate next run
        const next = new Date(now.getTime() + intervalMinutes * 60 * 1000);
        setNextRun(next);
      } else {
        const hours = Math.floor(diff / 3600000);
        const minutes = Math.floor((diff % 3600000) / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);
        setCountdown(
          `${hours.toString().padStart(2, '0')}:${minutes
            .toString()
            .padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
        );
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [nextRun, enabled, intervalMinutes]);

  // Format interval for display
  const formatInterval = (minutes: number): string => {
    if (minutes < 60) return `${minutes} min`;
    if (minutes === 60) return '1 hour';
    if (minutes < 1440) return `${Math.floor(minutes / 60)} hours`;
    return '24 hours (Daily)';
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <RefreshCw className={`w-5 h-5 ${enabled ? 'text-blue-600' : 'text-gray-400'}`} />
          <h3 className="text-lg font-semibold text-gray-900">Portfolio Analysis Cron</h3>
        </div>

        {/* Enable/Disable Toggle */}
        <button
          onClick={() => onToggle?.(!enabled)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            enabled ? 'bg-blue-600' : 'bg-gray-300'
          }`}
          aria-label={enabled ? 'Disable cron' : 'Enable cron'}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              enabled ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {enabled ? (
        <div className="space-y-4">
          {/* Countdown Display */}
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <Clock className="w-5 h-5 text-blue-600" />
              <span className="text-sm font-medium text-gray-700">Next Run</span>
            </div>
            <div className="text-3xl font-mono font-bold text-blue-600 tracking-wider">
              {countdown}
            </div>
            {nextRun && (
              <div className="text-xs text-gray-600 mt-2">
                {nextRun.toLocaleString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </div>
            )}
          </div>

          {/* Status Info */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Play className="w-4 h-4 text-green-600" />
            <span>
              Running every <strong>{formatInterval(intervalMinutes)}</strong>
            </span>
          </div>
        </div>
      ) : (
        <div className="text-center py-6">
          <Pause className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500">Cron is disabled</p>
          <p className="text-xs text-gray-400 mt-1">
            Enable to start automated portfolio analysis
          </p>
        </div>
      )}

      {/* Interval Selector */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Execution Interval (Local Testing)
        </label>
        <select
          value={intervalMinutes}
          onChange={(e) => onIntervalChange?.(Number(e.target.value))}
          className="w-full px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value={5}>Every 5 minutes (Fast test)</option>
          <option value={15}>Every 15 minutes</option>
          <option value={30}>Every 30 minutes</option>
          <option value={60}>Every 1 hour</option>
          <option value={360}>Every 6 hours</option>
          <option value={1440}>Every 24 hours (Production)</option>
        </select>
        <p className="text-xs text-gray-500 mt-2">
          ⚠️ Short intervals recommended for testing only. Production uses 24-hour (8 PM EST daily).
        </p>
      </div>

      {/* Info Panel */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg">
        <p className="text-xs text-gray-600">
          <strong>Note:</strong> This controls the{' '}
          <span className="font-mono bg-gray-200 px-1 rounded">portfolio-cron</span> Docker
          service. Changes require container restart to take effect.
        </p>
      </div>
    </div>
  );
}
