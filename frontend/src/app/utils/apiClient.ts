// API client with authentication and error handling

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  reason?: string;
  status: number;
}

export interface PolicySummary {
  version: number;
  files: string[];
  agents: string[];
  total_rules: number;
}

export interface Decision {
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

export interface PendingApproval {
  id: string;
  timestamp: string;
  agent_id: string;
  parent_agent?: string;
  call_chain: string[];
  tool: string;
  action: string;
  params: Record<string, unknown>;
  reason: string;
  expires_at: string;
  approved_by?: string;
  approved_at?: string;
}

class ApiClient {
  private readonly baseUrl: string;
  private readonly getToken: () => string | null;
  private readonly onUnauthorized: () => void;

  constructor(
    baseUrl: string,
    getToken: () => string | null,
    onUnauthorized: () => void
  ) {
    this.baseUrl = baseUrl;
    this.getToken = getToken;
    this.onUnauthorized = onUnauthorized;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const token = this.getToken();
    const url = `${this.baseUrl}${endpoint}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    // Add authentication header
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle authentication errors
      if (response.status === 401) {
        this.onUnauthorized();
        return {
          error: 'Authentication required. Please log in again.',
          status: 401,
          reason: 'Authentication required. Please log in again.',
        };
      }

      // Handle rate limiting
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After');
        const retryMessage = retryAfter ? `Try again in ${retryAfter} seconds.` : 'Please try again later.';
        return {
          error: `Rate limit exceeded. ${retryMessage}`,
          status: 429,
          reason: `Rate limit exceeded. ${retryMessage}`,
        };
      }

      // Handle other client errors
      if (response.status >= 400 && response.status < 500) {
        const errorData = await response.json().catch(() => ({}));
        return {
          error: errorData.detail || errorData.error || `Client error: ${response.status}`,
          status: response.status,
          reason: errorData.detail || errorData.reason || errorData.error || `Client error: ${response.status}`,
        };
      }

      // Handle server errors
      if (response.status >= 500) {
        return {
          error: 'Server error. Please try again later.',
          status: response.status,
          reason: 'Server error. Please try again later.',
        };
      }

      // Success response
      const data = await response.json();
      return {
        data,
        status: response.status,
      };
    } catch (error) {
      console.error('API request failed:', error);
      return {
        error: 'Network error. Please check your connection.',
        status: 0,
        reason: 'Network error. Please check your connection.',
      };
    }
  }

  async getAgents(): Promise<ApiResponse<{ agents: string[] }>> {
    return this.request<{ agents: string[] }>('/admin/agents');
  }

  async getPolicies(): Promise<ApiResponse<PolicySummary>> {
    return this.request<PolicySummary>('/admin/policies');
  }

  async getDecisions(limit: number = 50): Promise<ApiResponse<{ decisions: Decision[] }>> {
    return this.request<{ decisions: Decision[] }>(`/admin/decisions?limit=${limit}`);
  }

  async approveAction(
    approvalId: string,
    approvedBy: string = 'admin'
  ): Promise<ApiResponse<{ status: string; approval_id: string; result: Record<string, unknown> }>> {
    return this.request<{ status: string; approval_id: string; result: Record<string, unknown> }>(
      `/approve/${approvalId}`,
      {
        method: 'POST',
        body: JSON.stringify({ approved_by: approvedBy }),
      }
    );
  }

  async testToolCall(
    tool: string,
    action: string,
    agentId: string,
    params: Record<string, unknown>,
    parentAgent?: string
  ): Promise<ApiResponse<Record<string, unknown>>> {
    const headers: HeadersInit = {
      'X-Agent-ID': agentId,
    };

    if (parentAgent) {
      headers['X-Parent-Agent'] = parentAgent;
    }

    return this.request<Record<string, unknown>>(`/tools/${tool}/${action}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(params),
    });
  }

  async login(username: string, password: string): Promise<ApiResponse<{
    access_token: string;
    token_type: string;
    expires_in: number;
  }>> {
    return this.request<{
      access_token: string;
      token_type: string;
      expires_in: number;
    }>('/admin/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  }
}

export default ApiClient;
