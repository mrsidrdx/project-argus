"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Shield,
  Users,
  FileText,
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  LogOut,
  RefreshCw,
  ExternalLink,
  Play,
  Zap,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useAuth } from "./auth/AuthContext";
import LoginPage from "./auth/LoginPage";
import ApiClient, { PolicySummary, Decision } from "./utils/apiClient";

// Utility function to properly handle UTC timestamps and convert to local time
const formatTimestamp = (utcTimestamp: string) => {
  try {
    // The backend now sends timezone-aware timestamps in ISO format
    // Handle different formats:
    // - "2025-10-08T14:24:40.345632+00:00" (new timezone-aware format)
    // - "2025-10-08T14:24:40.345632Z" (old Z suffix format)
    // - "2025-10-08T14:24:40.345632" (old naive format)

    let date: Date;

    if (utcTimestamp.includes("+") || utcTimestamp.includes("Z")) {
      // Already has timezone info, parse directly
      date = new Date(utcTimestamp);
    } else {
      // Treat as UTC by adding 'Z' suffix for backward compatibility
      date = new Date(utcTimestamp + "Z");
    }

    // Check if the date is valid
    if (isNaN(date.getTime())) {
      return "Invalid date";
    }

    return formatDistanceToNow(date, { addSuffix: true });
  } catch (error) {
    console.error("Error parsing timestamp:", utcTimestamp, error);
    return "Invalid date";
  }
};

// Helper function for expected result colors
const getExpectedColor = (expected: string) => {
  switch (expected) {
    case "allow":
      return "text-green-600";
    case "deny":
      return "text-red-600";
    default:
      return "text-yellow-600";
  }
};

// Helper function for status colors
const getStatusColor = (status: number) => {
  switch (status) {
    case 200:
      return "bg-green-100 text-green-800";
    case 202:
      return "bg-yellow-100 text-yellow-800";
    case 403:
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

export default function AdminDashboard() {
  const { isAuthenticated, token, logout, loading: authLoading } = useAuth();
  const [agents, setAgents] = useState<string[]>([]);
  const [policies, setPolicies] = useState<PolicySummary | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "overview" | "agents" | "policies" | "decisions" | "testing"
  >("overview");

  // API client instance
  const apiClient = useMemo(
    () =>
      new ApiClient(
        process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080",
        () => token,
        () => logout()
      ),
    [token, logout]
  );

  const fetchData = useCallback(
    async (showRefreshing = false) => {
      if (showRefreshing) setRefreshing(true);
      setError(null);

      try {
        const [agentsRes, policiesRes, decisionsRes] = await Promise.all([
          apiClient.getAgents(),
          apiClient.getPolicies(),
          apiClient.getDecisions(50),
        ]);

        // Handle errors from any of the API calls
        if (agentsRes.error) {
          setError(agentsRes.error);
          return;
        }
        if (policiesRes.error) {
          setError(policiesRes.error);
          return;
        }
        if (decisionsRes.error) {
          setError(decisionsRes.error);
          return;
        }

        setAgents(agentsRes.data?.agents || []);
        setPolicies(policiesRes.data || null);
        setDecisions(decisionsRes.data?.decisions || []);
      } catch (error) {
        console.error("Failed to fetch data:", error);
        setError("Failed to fetch data. Please try again.");
      } finally {
        setLoading(false);
        if (showRefreshing) setRefreshing(false);
      }
    },
    [apiClient]
  );

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      fetchData();
      const interval = setInterval(() => fetchData(), 5000); // Refresh every 5 seconds
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, authLoading, fetchData]);

  // Show login page if not authenticated
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const getDecisionIcon = (decision: string) => {
    switch (decision) {
      case "allow":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "deny":
        return <XCircle className="w-4 h-4 text-red-500" />;
      case "pending_approval":
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getDecisionColor = (decision: string) => {
    switch (decision) {
      case "allow":
        return "bg-green-100 text-green-800 border-green-200";
      case "deny":
        return "bg-red-100 text-red-800 border-red-200";
      case "pending_approval":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading Aegis Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-3">
              <Shield className="w-8 h-8 text-blue-600" />
              <h1 className="text-2xl font-bold text-gray-900">
                Aegis Gateway Admin
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => fetchData(true)}
                disabled={refreshing}
                className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50"
                title="Refresh data"
              >
                <RefreshCw
                  className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`}
                />
                <span>Refresh</span>
              </button>
              <div className="text-sm text-gray-500">
                Policy Version: {policies?.version || "N/A"}
              </div>
              <button
                onClick={logout}
                className="flex items-center space-x-2 px-3 py-2 text-sm text-red-600 hover:text-red-800"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
                <span>Sign out</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertCircle className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
            <div className="ml-auto pl-3">
              <div className="-mx-1.5 -my-1.5">
                <button
                  onClick={() => setError(null)}
                  className="inline-flex bg-red-50 rounded-md p-1.5 text-red-500 hover:bg-red-100"
                >
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {[
              { id: "overview", label: "Overview", icon: Activity },
              { id: "agents", label: "Agents", icon: Users },
              { id: "policies", label: "Policies", icon: FileText },
              { id: "decisions", label: "Recent Decisions", icon: Clock },
              { id: "testing", label: "Testing", icon: Play },
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() =>
                  setActiveTab(
                    id as
                      | "overview"
                      | "agents"
                      | "policies"
                      | "decisions"
                      | "testing"
                  )
                }
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === id
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === "overview" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Users className="w-8 h-8 text-blue-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">
                    Total Agents
                  </p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {agents.length}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <FileText className="w-8 h-8 text-green-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">
                    Policy Rules
                  </p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {policies?.total_rules || 0}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <CheckCircle className="w-8 h-8 text-green-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">
                    Allowed Today
                  </p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {decisions.filter((d) => d.decision === "allow").length}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <XCircle className="w-8 h-8 text-red-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">
                    Denied Today
                  </p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {decisions.filter((d) => d.decision === "deny").length}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "agents" && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Registered Agents
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agents.map((agent) => (
                  <div
                    key={agent}
                    className="border rounded-lg p-4 hover:bg-gray-50"
                  >
                    <div className="flex items-center space-x-3">
                      <Users className="w-5 h-5 text-blue-600" />
                      <span className="font-medium text-gray-900">{agent}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "policies" && policies && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Policy Configuration
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">
                    Policy Files
                  </h4>
                  <ul className="space-y-2">
                    {policies.files.map((file) => (
                      <li key={file} className="flex items-center space-x-2">
                        <FileText className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-600">{file}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Statistics</h4>
                  <dl className="space-y-2">
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-600">Version:</dt>
                      <dd className="text-sm font-medium text-gray-900">
                        {policies.version}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-600">Total Rules:</dt>
                      <dd className="text-sm font-medium text-gray-900">
                        {policies.total_rules}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-600">Agents:</dt>
                      <dd className="text-sm font-medium text-gray-900">
                        {policies.agents.length}
                      </dd>
                    </div>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "decisions" && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Recent Policy Decisions
              </h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Decision
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Agent
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Action
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Time
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Reason
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {decisions.slice(0, 50).map((decision) => (
                      <tr
                        key={`${decision.timestamp}-${decision.agent_id}-${decision.params_hash}`}
                        className="hover:bg-gray-50"
                      >
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-2">
                            {getDecisionIcon(decision.decision)}
                            <span
                              className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full border ${getDecisionColor(
                                decision.decision
                              )}`}
                            >
                              {decision.decision}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">
                            {decision.agent_id}
                          </div>
                          {decision.parent_agent && (
                            <div className="text-xs text-gray-500">
                              via {decision.parent_agent}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {decision.tool}/{decision.action}
                          </div>
                          <div className="text-xs text-gray-500">
                            {decision.latency_ms.toFixed(1)}ms
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatTimestamp(decision.timestamp)}
                        </td>
                        <td className="px-6 py-4">
                          <div
                            className="text-sm text-gray-900 max-w-xs truncate"
                            title={decision.reason}
                          >
                            {decision.reason || "N/A"}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          {decision.decision === "pending_approval" &&
                            decision.approval_id && (
                              <button
                                onClick={async () => {
                                  try {
                                    const result =
                                      await apiClient.approveAction(
                                        decision.approval_id!,
                                        "admin-ui"
                                      );
                                    if (result.error) {
                                      setError(result.error);
                                    } else {
                                      // Refresh data to show updated status
                                      fetchData();
                                    }
                                  } catch (err) {
                                    console.error("Approval error:", err);
                                    setError("Failed to approve action");
                                  }
                                }}
                                className="text-green-600 hover:text-green-900"
                              >
                                Approve
                              </button>
                            )}
                          {decision.trace_id && (
                            <a
                              href={`${
                                process.env.NEXT_PUBLIC_JAEGER_URL ||
                                "http://localhost:16686"
                              }/trace/${decision.trace_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:text-blue-900 ml-2"
                              title="View trace in Jaeger"
                            >
                              <ExternalLink className="w-4 h-4 inline" />
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === "testing" && (
          <div className="space-y-6">
            <div className="bg-white shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                  Tool Call Testing
                </h3>
                <TestingPanel
                  apiClient={apiClient}
                  agents={agents}
                  onError={setError}
                />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// Testing Panel Component
interface TestingPanelProps {
  readonly apiClient: ApiClient;
  readonly agents: string[];
  readonly onError: (error: string) => void;
}

function TestingPanel({ apiClient, agents, onError }: TestingPanelProps) {
  const [selectedAgent, setSelectedAgent] = useState("");
  const [parentAgent, setParentAgent] = useState("");
  const [tool, setTool] = useState("payments");
  const [action, setAction] = useState("create");
  const [params, setParams] = useState(
    '{"amount": 100, "currency": "USD", "vendor_id": "V1"}'
  );
  const [result, setResult] = useState<{
    status: number;
    data?: Record<string, unknown>;
    error?: string;
    reason?: string;
    timestamp: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  const predefinedTests = [
    {
      name: "Valid Payment (Small)",
      agent: "finance-agent",
      tool: "payments",
      action: "create",
      params: '{"amount": 100, "currency": "USD", "vendor_id": "V1"}',
      expected: "allow",
    },
    {
      name: "High-Value Payment (Approval Required)",
      agent: "finance-agent-high-value",
      tool: "payments",
      action: "create",
      params: '{"amount": 25000, "currency": "USD", "vendor_id": "V2"}',
      expected: "pending_approval",
    },
    {
      name: "Excessive Payment (Denied)",
      agent: "finance-agent",
      tool: "payments",
      action: "create",
      params: '{"amount": 6000, "currency": "USD", "vendor_id": "V1"}',
      expected: "deny",
    },
    {
      name: "HR File Read (Allowed)",
      agent: "hr-agent",
      tool: "files",
      action: "read",
      params: '{"path": "/hr-docs/employee.txt"}',
      expected: "allow",
    },
    {
      name: "Unauthorized File Read (Denied)",
      agent: "hr-agent",
      tool: "files",
      action: "read",
      params: '{"path": "/finance/budget.xlsx"}',
      expected: "deny",
    },
  ];

  const handleTest = async (customParams?: Record<string, unknown>) => {
    if (!selectedAgent) {
      onError("Please select an agent");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const testParams = customParams || JSON.parse(params);
      const response = await apiClient.testToolCall(
        tool,
        action,
        selectedAgent,
        testParams,
        parentAgent || undefined
      );

      console.log("response", response);

      setResult({
        status: response.status,
        data: response.data,
        error: response.error,
        reason: response.reason,
        timestamp: new Date().toISOString(),
      });

      if (response.error && response.reason) {
        onError(response.reason);
      }
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Invalid JSON parameters";
      onError(errorMsg);
      setResult({
        status: 0,
        error: errorMsg,
        reason: errorMsg,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  const runPredefinedTest = async (test: (typeof predefinedTests)[0]) => {
    setSelectedAgent(test.agent);
    setTool(test.tool);
    setAction(test.action);
    setParams(test.params);

    // Wait for state to update, then run test
    setTimeout(() => {
      handleTest(JSON.parse(test.params));
    }, 100);
  };

  return (
    <div className="space-y-6">
      {/* Predefined Tests */}
      <div>
        <h4 className="text-md font-medium text-gray-900 mb-3">Quick Tests</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {predefinedTests.map((test) => (
            <button
              key={test.name}
              onClick={() => runPredefinedTest(test)}
              disabled={loading}
              className="text-left p-3 border rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <div className="font-medium text-sm text-gray-900">
                {test.name}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {test.agent} → {test.tool}/{test.action}
              </div>
              <div
                className={`text-xs mt-1 ${getExpectedColor(test.expected)}`}
              >
                Expected: {test.expected}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Custom Test Form */}
      <div>
        <h4 className="text-md font-medium text-gray-900 mb-3">Custom Test</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="agent-select"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Agent ID
            </label>
            <select
              id="agent-select"
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select an agent...</option>
              {agents.map((agent) => (
                <option key={agent} value={agent}>
                  {agent}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="parent-agent-select"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Parent Agent (Optional)
            </label>
            <select
              id="parent-agent-select"
              value={parentAgent}
              onChange={(e) => setParentAgent(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">None</option>
              {agents.map((agent) => (
                <option key={agent} value={agent}>
                  {agent}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="tool-select"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Tool
            </label>
            <select
              id="tool-select"
              value={tool}
              onChange={(e) => setTool(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="payments">payments</option>
              <option value="files">files</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="action-select"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Action
            </label>
            <select
              id="action-select"
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              {tool === "payments" ? (
                <>
                  <option value="create">create</option>
                  <option value="refund">refund</option>
                </>
              ) : (
                <>
                  <option value="read">read</option>
                  <option value="write">write</option>
                </>
              )}
            </select>
          </div>
        </div>

        <div className="mt-4">
          <label
            htmlFor="params-textarea"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Parameters (JSON)
          </label>
          <textarea
            id="params-textarea"
            value={params}
            onChange={(e) => setParams(e.target.value)}
            rows={4}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            placeholder='{"amount": 100, "currency": "USD"}'
          />
        </div>

        <div className="mt-4">
          <button
            onClick={() => handleTest()}
            disabled={loading || !selectedAgent}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Testing...</span>
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                <span>Run Test</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div>
          <h4 className="text-md font-medium text-gray-900 mb-3">
            Test Result
          </h4>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <span
                className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(
                  result.status
                )}`}
              >
                Status: {result.status}
              </span>
              <span className="text-xs text-gray-500">
                {formatTimestamp(result.timestamp)}
              </span>
            </div>
            <pre className="text-sm bg-white text-gray-900 p-3 rounded border overflow-x-auto font-mono">
              {JSON.stringify(
                result.data || { error: result.error, reason: result.reason },
                null,
                2
              )}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
