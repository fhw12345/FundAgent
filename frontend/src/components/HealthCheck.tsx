import { useQuery } from "@tanstack/react-query";
import { RefreshCw, CheckCircle, XCircle, AlertCircle } from "lucide-react";
import { healthService } from "../services/api";
import type { HealthResponse } from "../types/api";

export function HealthCheck() {
  const {
    data: health,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: healthService.getHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const getStatusIcon = (connected: boolean) => {
    if (connected) {
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    }
    return <XCircle className="h-5 w-5 text-red-500" />;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ok":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <CheckCircle className="h-3 w-3 mr-1" />
            Healthy
          </span>
        );
      case "degraded":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            <AlertCircle className="h-3 w-3 mr-1" />
            Degraded
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
            <XCircle className="h-3 w-3 mr-1" />
            Error
          </span>
        );
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center justify-center">
          <RefreshCw className="h-6 w-6 animate-spin text-blue-500" />
          <span className="ml-2 text-gray-600">Checking system health...</span>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">System Status</h3>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </button>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <XCircle className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                Unable to connect to backend
              </h3>
              <p className="mt-2 text-sm text-red-700">
                Error:{" "}
                {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-medium text-gray-900">System Status</h3>
        <div className="flex items-center space-x-3">
          {getStatusBadge(health?.status || "error")}
          <button
            onClick={() => refetch()}
            className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Dependencies Status */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-900">Dependencies</h4>

          {/* MongoDB */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
            <div className="flex items-center">
              {getStatusIcon(health?.dependencies?.mongodb?.connected || false)}
              <span className="ml-3 text-sm font-medium text-gray-900">
                MongoDB
              </span>
            </div>
            <div className="text-xs text-gray-500">
              {health?.dependencies?.mongodb?.connected
                ? `v${health.dependencies.mongodb.version}`
                : "Disconnected"}
            </div>
          </div>

          {/* Redis */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
            <div className="flex items-center">
              {getStatusIcon(health?.dependencies?.redis?.connected || false)}
              <span className="ml-3 text-sm font-medium text-gray-900">
                Redis
              </span>
            </div>
            <div className="text-xs text-gray-500">
              {health?.dependencies?.redis?.connected
                ? `v${health.dependencies.redis.version}`
                : "Disconnected"}
            </div>
          </div>
        </div>

        {/* Configuration */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-900">Configuration</h4>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Environment:</span>
              <span className="font-mono text-gray-900">
                {health?.environment}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Version:</span>
              <span className="font-mono text-gray-900">{health?.version}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Database:</span>
              <span className="font-mono text-gray-900">
                {health?.configuration?.database_name}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">LangSmith:</span>
              <span
                className={`font-mono ${health?.configuration?.langsmith_enabled ? "text-green-600" : "text-gray-400"}`}
              >
                {health?.configuration?.langsmith_enabled
                  ? "Enabled"
                  : "Disabled"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Walking Skeleton Success Message */}
      {health?.status === "ok" && (
        <div className="mt-6 bg-green-50 border border-green-200 rounded-md p-4">
          <div className="flex">
            <CheckCircle className="h-5 w-5 text-green-400" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-green-800">
                Walking Skeleton Verified! 🎉
              </h3>
              <p className="mt-2 text-sm text-green-700">
                End-to-end connectivity confirmed: Frontend ↔ FastAPI ↔
                MongoDB ↔ Redis
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
