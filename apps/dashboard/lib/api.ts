import {
  AdminActionRun,
  AdminOverview,
  AdminUser,
  AdminWorkspace,
  ActionRunDetail,
  ActionRunListResponse,
  CreatedDashboardApiKey,
  CreateRegisteredActionInput,
  CreatedWorkspace,
  DashboardUsage,
  DashboardApiKey,
  DashboardActionDecision,
  DeletedWorkspace,
  ExecutionStatus,
  GovernanceStatus,
  PendingApprovalItem,
  PolicySuggestion,
  RegeneratedWorkspaceKey,
  RegisteredAction,
  SuggestRegisteredActionPolicyInput,
  Workspace,
  WorkspaceApprovalSettings,
  WorkspaceRunMetrics,
  WorkspaceKeyInfo,
} from '@/lib/types';
import { createSupabaseServerClient } from '@/lib/supabase/server';

type ApiResult<T> = {
  data: T | null;
  error: string | null;
};

const DEFAULT_API_BASE_URL =
  process.env.NODE_ENV === 'production'
    ? 'http://127.0.0.1:8000'
    : 'http://127.0.0.1:8000';
const API_BASE_URL = process.env.DAAI_API_BASE_URL ?? DEFAULT_API_BASE_URL;

function readApiErrorBody(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') {
    return fallback;
  }
  const payload = body as {
    detail?: unknown;
    message?: unknown;
    error?: unknown;
  };
  if (typeof payload.message === 'string' && payload.message.trim()) {
    return payload.message;
  }
  if (typeof payload.detail === 'string' && payload.detail.trim()) {
    return payload.detail;
  }
  if (payload.detail && typeof payload.detail === 'object') {
    const detail = payload.detail as { message?: unknown; code?: unknown; error?: unknown };
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }
    if (typeof detail.code === 'string' && detail.code.trim()) {
      return detail.code;
    }
    if (typeof detail.error === 'string' && detail.error.trim()) {
      return detail.error;
    }
  }
  if (typeof payload.error === 'string' && payload.error.trim()) {
    return payload.error;
  }
  return fallback;
}

async function getDashboardAccessToken(): Promise<ApiResult<string>> {
  try {
    const supabase = createSupabaseServerClient();
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
      return {
        data: null,
        error: 'Dashboard auth session is missing. Log in again.',
      };
    }

    const {
      data: { session },
      error: sessionError,
    } = await supabase.auth.getSession();

    if (sessionError || !session?.access_token) {
      return {
        data: null,
        error: 'Dashboard auth token is unavailable. Log in again.',
      };
    }

    const token = session.access_token;
    const tokenParts = token.split('.');
    if (tokenParts.length !== 3) {
      return {
        data: null,
        error:
          'Dashboard auth token is malformed (expected Supabase JWT). Log in again.',
      };
    }

    return { data: token, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return { data: null, error: `Dashboard auth failed: ${message}` };
  }
}

async function dashboardGet<T>(path: string): Promise<ApiResult<T>> {
  const tokenResult = await getDashboardAccessToken();
  if (tokenResult.error || !tokenResult.data) {
    return { data: null, error: tokenResult.error ?? 'Missing dashboard auth token.' };
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${tokenResult.data}`,
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      let detail = 'Request failed';
      try {
        const body = await response.json();
        detail = readApiErrorBody(body, detail);
      } catch {
        detail = response.statusText || detail;
      }
      return {
        data: null,
        error: `Dashboard API error (${response.status}): ${detail}`,
      };
    }

    const payload = (await response.json()) as T;
    return { data: payload, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return { data: null, error: `Cannot reach dashboard API: ${message}` };
  }
}

async function dashboardPost<T>(
  path: string,
  payload: Record<string, unknown>,
): Promise<ApiResult<T>> {
  const tokenResult = await getDashboardAccessToken();
  if (tokenResult.error || !tokenResult.data) {
    return { data: null, error: tokenResult.error ?? 'Missing dashboard auth token.' };
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${tokenResult.data}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      cache: 'no-store',
    });

    if (!response.ok) {
      let detail = 'Request failed';
      try {
        const body = await response.json();
        detail = readApiErrorBody(body, detail);
      } catch {
        detail = response.statusText || detail;
      }
      return {
        data: null,
        error: `Dashboard API error (${response.status}): ${detail}`,
      };
    }

    const parsed = (await response.json()) as T;
    return { data: parsed, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return { data: null, error: `Cannot reach dashboard API: ${message}` };
  }
}

async function dashboardDelete<T>(
  path: string,
  payload: Record<string, unknown>,
): Promise<ApiResult<T>> {
  const tokenResult = await getDashboardAccessToken();
  if (tokenResult.error || !tokenResult.data) {
    return { data: null, error: tokenResult.error ?? 'Missing dashboard auth token.' };
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${tokenResult.data}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      cache: 'no-store',
    });

    if (!response.ok) {
      let detail = 'Request failed';
      try {
        const body = await response.json();
        detail = readApiErrorBody(body, detail);
      } catch {
        detail = response.statusText || detail;
      }
      return {
        data: null,
        error: `Dashboard API error (${response.status}): ${detail}`,
      };
    }

    const parsed = (await response.json()) as T;
    return { data: parsed, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return { data: null, error: `Cannot reach dashboard API: ${message}` };
  }
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export async function fetchWorkspaces(): Promise<ApiResult<Workspace[]>> {
  return dashboardGet<Workspace[]>('/v1/dashboard/workspaces');
}

export async function fetchWorkspace(
  workspaceId: string,
): Promise<ApiResult<Workspace>> {
  return dashboardGet<Workspace>(`/v1/dashboard/workspaces/${workspaceId}`);
}

export async function fetchWorkspaceActions(
  workspaceId: string,
): Promise<ApiResult<RegisteredAction[]>> {
  return dashboardGet<RegisteredAction[]>(
    `/v1/dashboard/workspaces/${workspaceId}/actions`,
  );
}

export async function createWorkspaceRegisteredAction(
  workspaceId: string,
  input: CreateRegisteredActionInput,
): Promise<ApiResult<RegisteredAction>> {
  return dashboardPost<RegisteredAction>(
    `/v1/dashboard/workspaces/${workspaceId}/actions`,
    {
      action_name: input.actionName,
      title: input.title,
      description: input.description,
      risk_level: input.riskLevel,
      policy_type: input.policyType,
      threshold_amount: input.thresholdAmount ?? null,
      approver_email: input.approverEmail ?? null,
      explanation: input.explanation ?? '',
      approval_triggers: input.approvalTriggers ?? [],
      risk_factors: input.riskFactors ?? [],
      client_facing_summary: input.clientFacingSummary ?? '',
      receipt_summary_template: input.receiptSummaryTemplate ?? '',
      policy_source: input.policySource ?? 'manual',
      setup_answers: input.setupAnswers ?? null,
      policy_suggestion_snapshot: input.policySuggestionSnapshot ?? null,
    },
  );
}

export async function suggestWorkspaceRegisteredActionPolicy(
  workspaceId: string,
  input: SuggestRegisteredActionPolicyInput,
): Promise<ApiResult<PolicySuggestion>> {
  return dashboardPost<PolicySuggestion>(
    `/v1/workspaces/${workspaceId}/actions/suggest-policy`,
    {
      action_name: input.actionName,
      title: input.title,
      description: input.description,
      risk_level: input.riskLevel,
      approver_email: input.approverEmail ?? null,
      setup_answers: input.setupAnswers,
    },
  );
}

export async function fetchWorkspaceMetrics(
  workspaceId: string,
): Promise<ApiResult<WorkspaceRunMetrics>> {
  return dashboardGet<WorkspaceRunMetrics>(
    `/v1/dashboard/workspaces/${workspaceId}/metrics`,
  );
}

export async function fetchDashboardUsage(): Promise<ApiResult<DashboardUsage>> {
  return dashboardGet<DashboardUsage>('/v1/dashboard/usage');
}

export async function fetchWorkspaceUsage(
  workspaceId: string,
): Promise<ApiResult<DashboardUsage>> {
  return dashboardGet<DashboardUsage>(
    `/v1/dashboard/workspaces/${workspaceId}/usage`,
  );
}

export async function fetchWorkspaceApprovalSettings(
  workspaceId: string,
): Promise<ApiResult<WorkspaceApprovalSettings>> {
  return dashboardGet<WorkspaceApprovalSettings>(
    `/v1/dashboard/workspaces/${workspaceId}/approval-settings`,
  );
}

export async function updateWorkspaceApprovalSettings(
  workspaceId: string,
  input: {
    approvalEmails: string[];
    approvalLinkTtlMinutes: number;
  },
): Promise<ApiResult<WorkspaceApprovalSettings>> {
  return dashboardPost<WorkspaceApprovalSettings>(
    `/v1/dashboard/workspaces/${workspaceId}/approval-settings`,
    {
      approval_emails: input.approvalEmails,
      approval_link_ttl_minutes: input.approvalLinkTtlMinutes,
    },
  );
}

export async function fetchWorkspacePendingApprovals(
  workspaceId: string,
  query: { limit?: number } = {},
): Promise<ApiResult<PendingApprovalItem[]>> {
  const params = new URLSearchParams();
  if (query.limit && query.limit > 0) {
    params.set('limit', String(query.limit));
  }
  const queryString = params.toString();
  return dashboardGet<PendingApprovalItem[]>(
    `/v1/dashboard/workspaces/${workspaceId}/pending-approvals${
      queryString ? `?${queryString}` : ''
    }`,
  );
}

export async function decideDashboardActionRun(
  actionRunId: string,
  decision: 'approve' | 'reject' | 'block',
): Promise<ApiResult<DashboardActionDecision>> {
  return dashboardPost<DashboardActionDecision>(
    `/v1/dashboard/action-runs/${actionRunId}/${decision}`,
    {},
  );
}

export async function fetchWorkspaceRuns(
  workspaceId: string,
  query: {
    page?: number;
    pageSize?: number;
    search?: string;
    governanceStatus?: GovernanceStatus;
    executionStatus?: ExecutionStatus;
  } = {},
): Promise<ApiResult<ActionRunListResponse>> {
  const params = new URLSearchParams();

  if (query.page && query.page > 0) {
    params.set('page', String(query.page));
  }
  if (query.pageSize && query.pageSize > 0) {
    params.set('page_size', String(query.pageSize));
  }
  if (query.search && query.search.trim()) {
    params.set('search', query.search.trim());
  }
  if (query.governanceStatus) {
    params.set('governance_status', query.governanceStatus);
  }
  if (query.executionStatus) {
    params.set('execution_status', query.executionStatus);
  }

  const queryString = params.toString();
  return dashboardGet<ActionRunListResponse>(
    `/v1/dashboard/workspaces/${workspaceId}/runs${
      queryString ? `?${queryString}` : ''
    }`,
  );
}

export async function fetchWorkspaceRunDetail(
  workspaceId: string,
  actionRunId: string,
): Promise<ApiResult<ActionRunDetail>> {
  return dashboardGet<ActionRunDetail>(
    `/v1/dashboard/workspaces/${workspaceId}/runs/${actionRunId}`,
  );
}

export async function createWorkspace(input: {
  workspaceName: string;
  clientName: string;
}): Promise<ApiResult<CreatedWorkspace>> {
  return dashboardPost<CreatedWorkspace>('/v1/dashboard/workspaces', {
    workspace_name: input.workspaceName,
    client_name: input.clientName,
  });
}

export async function deleteWorkspace(input: {
  workspaceId: string;
  workspaceNameConfirmation: string;
}): Promise<ApiResult<DeletedWorkspace>> {
  return dashboardDelete<DeletedWorkspace>(
    `/v1/dashboard/workspaces/${input.workspaceId}`,
    {
      workspace_name_confirmation: input.workspaceNameConfirmation,
    },
  );
}

export async function fetchDashboardApiKeys(): Promise<ApiResult<DashboardApiKey[]>> {
  return dashboardGet<DashboardApiKey[]>('/v1/dashboard/api-keys');
}

export async function createDashboardApiKey(input: {
  workspaceId: string;
  name: string;
}): Promise<ApiResult<CreatedDashboardApiKey>> {
  return dashboardPost<CreatedDashboardApiKey>('/v1/dashboard/api-keys', {
    workspace_id: input.workspaceId,
    name: input.name,
  });
}

export async function revokeDashboardApiKey(
  apiKeyId: string,
): Promise<ApiResult<DashboardApiKey>> {
  return dashboardPost<DashboardApiKey>(
    `/v1/dashboard/api-keys/${apiKeyId}/revoke`,
    {},
  );
}

export async function fetchWorkspaceKeyInfo(
  workspaceId: string,
): Promise<ApiResult<WorkspaceKeyInfo>> {
  return dashboardGet<WorkspaceKeyInfo>(
    `/v1/dashboard/workspaces/${workspaceId}/key-info`,
  );
}

export async function regenerateWorkspaceKey(
  workspaceId: string,
): Promise<ApiResult<RegeneratedWorkspaceKey>> {
  return dashboardPost<RegeneratedWorkspaceKey>(
    `/v1/dashboard/workspaces/${workspaceId}/regenerate-key`,
    {},
  );
}

export async function fetchAdminOverview(): Promise<ApiResult<AdminOverview>> {
  return dashboardGet<AdminOverview>('/v1/admin/overview');
}

export async function fetchAdminUsers(
  query: {
    search?: string;
    activatedOnly?: boolean;
    sort?: 'newest' | 'last_activity';
  } = {},
): Promise<ApiResult<AdminUser[]>> {
  const params = new URLSearchParams();
  if (query.search && query.search.trim()) {
    params.set('search', query.search.trim());
  }
  if (query.activatedOnly) {
    params.set('activated_only', 'true');
  }
  if (query.sort) {
    params.set('sort', query.sort);
  }
  const queryString = params.toString();
  return dashboardGet<AdminUser[]>(
    `/v1/admin/users${queryString ? `?${queryString}` : ''}`,
  );
}

export async function fetchAdminWorkspaces(
  query: { search?: string } = {},
): Promise<ApiResult<AdminWorkspace[]>> {
  const params = new URLSearchParams();
  if (query.search && query.search.trim()) {
    params.set('search', query.search.trim());
  }
  const queryString = params.toString();
  return dashboardGet<AdminWorkspace[]>(
    `/v1/admin/workspaces${queryString ? `?${queryString}` : ''}`,
  );
}

export async function fetchAdminRecentActionRuns(
  query: {
    search?: string;
    governanceStatus?: GovernanceStatus;
  } = {},
): Promise<ApiResult<AdminActionRun[]>> {
  const params = new URLSearchParams();
  if (query.search && query.search.trim()) {
    params.set('search', query.search.trim());
  }
  if (query.governanceStatus) {
    params.set('governance_status', query.governanceStatus);
  }
  const queryString = params.toString();
  return dashboardGet<AdminActionRun[]>(
    `/v1/admin/action-runs/recent${queryString ? `?${queryString}` : ''}`,
  );
}
