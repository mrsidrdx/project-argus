'use client';

import { useState, useEffect } from 'react';
import { Shield, Users, FileText, Activity, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';


interface PolicySummary {
  version: number;
  files: string[];
  agents: string[];
  total_rules: number;
}

interface Decision {
  timestamp: string;
  agent_id: string;
  parent_agent?: string;
  call_chain: string[];
  tool: string;
  action: string;
  params_hash: string;
  decision: string;
  reason?: string;
  policy_version: number;
  latency_ms: number;
  trace_id?: string;
  approval_id?: string;
}

const API_BASE = "http://localhost:8080";

// Utility function to properly handle UTC timestamps and convert to local time
const formatTimestamp = (utcTimestamp: string) => {
  try {
    // The backend now sends timezone-aware timestamps in ISO format
    // Handle different formats: 
    // - "2025-10-08T14:24:40.345632+00:00" (new timezone-aware format)
    // - "2025-10-08T14:24:40.345632Z" (old Z suffix format)
    // - "2025-10-08T14:24:40.345632" (old naive format)
    
    let date: Date;
    
    if (utcTimestamp.includes('+') || utcTimestamp.includes('Z')) {
      // Already has timezone info, parse directly
      date = new Date(utcTimestamp);
    } else {
      // Treat as UTC by adding 'Z' suffix for backward compatibility
      date = new Date(utcTimestamp + 'Z');
    }
    
    // Check if the date is valid
    if (isNaN(date.getTime())) {
      return 'Invalid date';
    }
    
    return formatDistanceToNow(date, { addSuffix: true });
  } catch (error) {
    console.error('Error parsing timestamp:', utcTimestamp, error);
    return 'Invalid date';
  }
};

export default function AdminDashboard() {
  const [agents, setAgents] = useState<string[]>([]);
  const [policies, setPolicies] = useState<PolicySummary | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'agents' | 'policies' | 'decisions'>('overview');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [agentsRes, policiesRes, decisionsRes] = await Promise.all([
          fetch(`${API_BASE}/admin/agents`),
          fetch(`${API_BASE}/admin/policies`),
          fetch(`${API_BASE}/admin/decisions`)
        ]);

        const agentsData = await agentsRes.json();
        const policiesData = await policiesRes.json();
        const decisionsData = await decisionsRes.json();

        setAgents(agentsData.agents || []);
        setPolicies(policiesData);
        setDecisions(decisionsData.decisions || []);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const getDecisionIcon = (decision: string) => {
    switch (decision) {
      case 'allow': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'deny': return <XCircle className="w-4 h-4 text-red-500" />;
      case 'pending_approval': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      default: return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getDecisionColor = (decision: string) => {
    switch (decision) {
      case 'allow': return 'bg-green-100 text-green-800 border-green-200';
      case 'deny': return 'bg-red-100 text-red-800 border-red-200';
      case 'pending_approval': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
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
              <h1 className="text-2xl font-bold text-gray-900">Aegis Gateway Admin</h1>
            </div>
            <div className="text-sm text-gray-500">
              Policy Version: {policies?.version || 'N/A'}
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {[
              { id: 'overview', label: 'Overview', icon: Activity },
              { id: 'agents', label: 'Agents', icon: Users },
              { id: 'policies', label: 'Policies', icon: FileText },
              { id: 'decisions', label: 'Recent Decisions', icon: Clock }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id as 'overview' | 'agents' | 'policies' | 'decisions')}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
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
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <Users className="w-8 h-8 text-blue-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Total Agents</p>
                  <p className="text-2xl font-semibold text-gray-900">{agents.length}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <FileText className="w-8 h-8 text-green-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Policy Rules</p>
                  <p className="text-2xl font-semibold text-gray-900">{policies?.total_rules || 0}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <CheckCircle className="w-8 h-8 text-green-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Allowed Today</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {decisions.filter(d => d.decision === 'allow').length}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <XCircle className="w-8 h-8 text-red-600" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Denied Today</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {decisions.filter(d => d.decision === 'deny').length}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'agents' && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Registered Agents</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agents.map((agent) => (
                  <div key={agent} className="border rounded-lg p-4 hover:bg-gray-50">
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

        {activeTab === 'policies' && policies && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Policy Configuration</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Policy Files</h4>
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
                      <dd className="text-sm font-medium text-gray-900">{policies.version}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-600">Total Rules:</dt>
                      <dd className="text-sm font-medium text-gray-900">{policies.total_rules}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-600">Agents:</dt>
                      <dd className="text-sm font-medium text-gray-900">{policies.agents.length}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'decisions' && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Recent Policy Decisions</h3>
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
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {decisions.slice(0, 50).map((decision, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center space-x-2">
                            {getDecisionIcon(decision.decision)}
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full border ${getDecisionColor(decision.decision)}`}>
                              {decision.decision}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">{decision.agent_id}</div>
                          {decision.parent_agent && (
                            <div className="text-xs text-gray-500">via {decision.parent_agent}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">{decision.tool}/{decision.action}</div>
                          <div className="text-xs text-gray-500">{decision.latency_ms.toFixed(1)}ms</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatTimestamp(decision.timestamp)}
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-gray-900 max-w-xs truncate" title={decision.reason}>
                            {decision.reason || 'N/A'}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}