'use client';

import Link from 'next/link';
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {
  ExecutableBadge,
  ExecutionStatusBadge,
  GovernanceStatusBadge,
} from '@/components/badges';
import {
  buttonStyles,
  fieldStyles,
  MetricCard,
  Notice,
  selectStyles,
  StatusBadge,
  TableShell,
} from '@/components/console-ui';
import { EmptyState } from '@/components/states';
import { formatTimestamp } from '@/lib/format';
import {
  ActionRunListResponse,
  ExecutionStatus,
  GovernanceStatus,
  WorkspaceRunMetrics,
} from '@/lib/types';

const GOVERNANCE_STATUS_OPTIONS: GovernanceStatus[] = [
  'allowed',
  'pending_approval',
  'approved',
  'rejected',
  'blocked',
];

const EXECUTION_STATUS_OPTIONS: ExecutionStatus[] = [
  'not_executed',
  'awaiting_execution_report',
  'executed',
  'failed',
];

type DraftFilters = {
  search: string;
  governanceStatus: GovernanceStatus | '';
  executionStatus: ExecutionStatus | '';
  pageSize: number;
};

type AppliedQuery = {
  page: number;
  search: string;
  governanceStatus: GovernanceStatus | '';
  executionStatus: ExecutionStatus | '';
  pageSize: number;
};

function clampPageSize(value: number): number {
  if (!Number.isFinite(value)) {
    return 25;
  }
  return Math.min(100, Math.max(1, value));
}

function clampPage(value: number): number {
  if (!Number.isFinite(value) || value < 1) {
    return 1;
  }
  return value;
}

function summarizeReason(reason: string, maxLength = 72): string {
  if (reason.length <= maxLength) {
    return reason;
  }
  return `${reason.slice(0, maxLength - 3)}...`;
}

function receiptLabel(outcome: string | undefined): string {
  return outcome ? `generated: ${outcome.replaceAll('_', ' ')}` : 'not generated';
}

function receiptTone(outcome: string | undefined): 'success' | 'danger' | 'neutral' {
  if (outcome === 'allowed' || outcome === 'approved') {
    return 'success';
  }
  if (outcome === 'blocked' || outcome === 'rejected') {
    return 'danger';
  }
  return 'neutral';
}

function queryToSearchParams(query: AppliedQuery): URLSearchParams {
  const params = new URLSearchParams();
  params.set('page', String(query.page));
  params.set('page_size', String(query.pageSize));
  if (query.search.trim()) {
    params.set('search', query.search.trim());
  }
  if (query.governanceStatus) {
    params.set('governance_status', query.governanceStatus);
  }
  if (query.executionStatus) {
    params.set('execution_status', query.executionStatus);
  }
  return params;
}

function SkeletonRows({ rows = 6 }: { rows?: number }) {
  return (
    <tbody className="divide-y divide-border bg-canvas">
      {Array.from({ length: rows }).map((_, index) => (
        <tr key={index} className="align-top">
          <td className="px-3 py-3">
            <div className="h-4 w-28 animate-pulse rounded bg-panelHover" />
          </td>
          <td className="px-3 py-3">
            <div className="h-4 w-36 animate-pulse rounded bg-panelHover" />
          </td>
          <td className="px-3 py-3">
            <div className="h-6 w-24 animate-pulse rounded-full bg-panelHover" />
          </td>
          <td className="px-3 py-3">
            <div className="h-6 w-28 animate-pulse rounded-full bg-panelHover" />
          </td>
          <td className="px-3 py-3">
            <div className="h-4 w-56 animate-pulse rounded bg-panelHover" />
          </td>
          <td className="px-3 py-3">
            <div className="h-6 w-20 animate-pulse rounded-full bg-panelHover" />
          </td>
          <td className="px-3 py-3">
            <div className="h-4 w-12 animate-pulse rounded bg-panelHover" />
          </td>
          <td className="px-3 py-3">
            <div className="h-8 w-16 animate-pulse rounded bg-panelHover" />
          </td>
        </tr>
      ))}
    </tbody>
  );
}

export function WorkspaceRunsTable({
  workspaceId,
  initialMetrics,
  initialMetricsError,
  initialPage = 1,
  initialPageSize = 25,
  initialSearch = '',
  initialGovernanceStatus = '',
  initialExecutionStatus = '',
}: {
  workspaceId: string;
  initialMetrics?: WorkspaceRunMetrics | null;
  initialMetricsError?: string | null;
  initialPage?: number;
  initialPageSize?: number;
  initialSearch?: string;
  initialGovernanceStatus?: GovernanceStatus | '';
  initialExecutionStatus?: ExecutionStatus | '';
}) {
  const safeInitialPage = clampPage(initialPage);
  const safeInitialPageSize = clampPageSize(initialPageSize);

  const [draft, setDraft] = useState<DraftFilters>({
    search: initialSearch,
    governanceStatus: initialGovernanceStatus,
    executionStatus: initialExecutionStatus,
    pageSize: safeInitialPageSize,
  });
  const [query, setQuery] = useState<AppliedQuery>({
    page: safeInitialPage,
    search: initialSearch,
    governanceStatus: initialGovernanceStatus,
    executionStatus: initialExecutionStatus,
    pageSize: safeInitialPageSize,
  });
  const [runsPage, setRunsPage] = useState<ActionRunListResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadRuns = useCallback(
    async (nextQuery: AppliedQuery) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      setError(null);

      const params = queryToSearchParams(nextQuery);

      try {
        const response = await fetch(
          `/api/dashboard/workspaces/${workspaceId}/runs?${params.toString()}`,
          {
            method: 'GET',
            cache: 'no-store',
            signal: controller.signal,
          },
        );

        const payload = (await response.json()) as
          | ActionRunListResponse
          | { detail?: string };

        if (!response.ok) {
          const detail =
            typeof (payload as { detail?: string }).detail === 'string'
              ? (payload as { detail?: string }).detail
              : `Request failed (${response.status})`;
          throw new Error(detail);
        }

        if (!controller.signal.aborted) {
          setRunsPage(payload as ActionRunListResponse);
          setLoading(false);
        }
      } catch (fetchError) {
        if (controller.signal.aborted) {
          return;
        }
        const message =
          fetchError instanceof Error ? fetchError.message : 'Unknown error';
        setError(message);
        setLoading(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    void loadRuns(query);

    const params = queryToSearchParams(query);
    const searchText = params.toString();
    const nextUrl = `/workspaces/${workspaceId}/runs${
      searchText ? `?${searchText}` : ''
    }`;
    window.history.replaceState(null, '', nextUrl);

    return () => {
      abortRef.current?.abort();
    };
  }, [query, loadRuns, workspaceId]);

  const hasPrevious = (runsPage?.page ?? query.page) > 1;
  const hasNext = runsPage ? runsPage.page < runsPage.total_pages : false;

  const summary = useMemo(
    () => ({
      page: runsPage?.page ?? query.page,
      totalPages: runsPage?.total_pages ?? 1,
      total: runsPage?.total ?? 0,
    }),
    [runsPage, query.page],
  );

  const runMetrics = useMemo(() => {
    const items = runsPage?.items ?? [];
    return {
      pendingApproval: items.filter((run) => run.governance_status === 'pending_approval')
        .length,
      approved: items.filter((run) => run.governance_status === 'approved').length,
      rejected: items.filter((run) => run.governance_status === 'rejected').length,
      blocked: items.filter((run) => run.governance_status === 'blocked').length,
      executed: items.filter((run) => run.execution_status === 'executed').length,
      failed: items.filter((run) => run.execution_status === 'failed').length,
    };
  }, [runsPage]);
  const metrics = initialMetrics
    ? {
        total: initialMetrics.total_runs,
        pendingApproval: initialMetrics.pending_approval,
        approved: initialMetrics.approved,
        rejected: initialMetrics.rejected,
        blocked: initialMetrics.blocked,
        executed: initialMetrics.executed,
        failed: initialMetrics.failed,
      }
    : {
        total: summary.total,
        ...runMetrics,
      };

  const onApplyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery({
      page: 1,
      search: draft.search.trim(),
      governanceStatus: draft.governanceStatus,
      executionStatus: draft.executionStatus,
      pageSize: clampPageSize(draft.pageSize),
    });
  };

  const onResetFilters = () => {
    const resetDraft: DraftFilters = {
      search: '',
      governanceStatus: '',
      executionStatus: '',
      pageSize: 25,
    };
    setDraft(resetDraft);
    setQuery({
      page: 1,
      search: '',
      governanceStatus: '',
      executionStatus: '',
      pageSize: 25,
    });
  };

  const onRetry = () => {
    void loadRuns(query);
  };

  return (
    <>
      {initialMetricsError ? (
        <Notice tone="warning">
          {initialMetricsError}
        </Notice>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-7">
        <MetricCard label="Total" value={metrics.total} compact />
        <MetricCard
          label="Pending approval"
          value={metrics.pendingApproval}
          tone={metrics.pendingApproval > 0 ? 'warning' : 'neutral'}
          compact
        />
        <MetricCard label="Approved" value={metrics.approved} compact />
        <MetricCard
          label="Rejected"
          value={metrics.rejected}
          tone={metrics.rejected > 0 ? 'danger' : 'neutral'}
          compact
        />
        <MetricCard
          label="Blocked"
          value={metrics.blocked}
          tone={metrics.blocked > 0 ? 'danger' : 'neutral'}
          compact
        />
        <MetricCard
          label="Executed"
          value={metrics.executed}
          tone={metrics.executed > 0 ? 'success' : 'neutral'}
          compact
        />
        <MetricCard
          label="Failed"
          value={metrics.failed}
          tone={metrics.failed > 0 ? 'danger' : 'neutral'}
          compact
        />
      </div>

      <p className="mt-4 text-sm text-muted">
        Governance status decides whether an action may proceed. Execution status tells
        whether the connected system later reported success or failure.
      </p>

      <form
        onSubmit={onApplyFilters}
        className="mt-4 rounded-lg border border-border bg-canvas p-4"
      >
        <div className="grid gap-3 md:grid-cols-5">
          <label className="md:col-span-2">
            <span className="text-xs font-medium uppercase text-subtle">
              Search action or reason
            </span>
            <input
              type="text"
              name="search"
              value={draft.search}
              onChange={(event) =>
                setDraft((current) => ({ ...current, search: event.target.value }))
              }
              placeholder="Search action or reason"
              disabled={loading}
              className={`mt-1 ${fieldStyles}`}
            />
          </label>

          <label>
            <span className="text-xs font-medium uppercase text-subtle">
              Governance status
            </span>
            <select
              name="governance_status"
              value={draft.governanceStatus}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  governanceStatus: event.target.value as GovernanceStatus | '',
                }))
              }
              disabled={loading}
              className={`mt-1 ${selectStyles}`}
            >
              <option value="">All governance statuses</option>
              {GOVERNANCE_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="text-xs font-medium uppercase text-subtle">
              Execution status
            </span>
            <select
              name="execution_status"
              value={draft.executionStatus}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  executionStatus: event.target.value as ExecutionStatus | '',
                }))
              }
              disabled={loading}
              className={`mt-1 ${selectStyles}`}
            >
              <option value="">All execution statuses</option>
              {EXECUTION_STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="text-xs font-medium uppercase text-subtle">Page size</span>
            <select
              name="page_size"
              value={String(draft.pageSize)}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  pageSize: clampPageSize(Number(event.target.value)),
                }))
              }
              disabled={loading}
              className={`mt-1 ${selectStyles}`}
            >
              <option value="10">10 / page</option>
              <option value="25">25 / page</option>
              <option value="50">50 / page</option>
              <option value="100">100 / page</option>
            </select>
          </label>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={loading}
            className={buttonStyles.primary}
          >
            {loading ? 'Loading...' : 'Apply'}
          </button>
          <button
            type="button"
            onClick={onResetFilters}
            disabled={loading}
            className={buttonStyles.secondary}
          >
            Reset filters
          </button>
        </div>
      </form>

      {error ? (
        <Notice tone="danger" className="mt-4">
          <p>{error}</p>
          <button
            type="button"
            onClick={onRetry}
            className={`mt-2 ${buttonStyles.secondary}`}
          >
            Retry
          </button>
        </Notice>
      ) : null}

      <div className="mt-4">
        <TableShell>
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-panelHover">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-text">Created</th>
                <th className="px-3 py-2 text-left font-semibold text-text">Action</th>
                <th className="px-3 py-2 text-left font-semibold text-text">
                  Governance Status
                </th>
                <th className="px-3 py-2 text-left font-semibold text-text">
                  Execution Status
                </th>
                <th className="px-3 py-2 text-left font-semibold text-text">Reason</th>
                <th className="px-3 py-2 text-left font-semibold text-text">Executable</th>
                <th className="px-3 py-2 text-left font-semibold text-text">Receipt</th>
                <th className="px-3 py-2 text-left font-semibold text-text">View</th>
              </tr>
            </thead>

            {loading ? (
              <SkeletonRows rows={Math.min(8, Math.max(4, draft.pageSize))} />
            ) : runsPage && runsPage.items.length > 0 ? (
              <tbody className="divide-y divide-border bg-canvas">
                {runsPage.items.map((run) => (
                  <tr key={run.action_run_id} className="align-top transition hover:bg-panelHover">
                    <td className="whitespace-nowrap px-3 py-3 text-xs text-muted">
                      {formatTimestamp(run.created_at)}
                    </td>
                    <td className="px-3 py-3 font-mono text-xs font-medium text-text">
                      {run.action}
                    </td>
                    <td className="px-3 py-3">
                      <GovernanceStatusBadge value={run.governance_status} />
                    </td>
                    <td className="px-3 py-3">
                      <ExecutionStatusBadge value={run.execution_status} />
                    </td>
                    <td
                      className="max-w-sm px-3 py-3 text-sm text-muted"
                      title={run.governance_reason}
                    >
                      {summarizeReason(run.governance_reason, 96)}
                    </td>
                    <td className="px-3 py-3">
                      <ExecutableBadge value={run.executable} />
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge
                        label={receiptLabel(run.receipt?.outcome)}
                        tone={receiptTone(run.receipt?.outcome)}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <Link
                        href={`/workspaces/${workspaceId}/runs/${run.action_run_id}`}
                        className={`${buttonStyles.subtle} px-2.5 py-1.5 text-xs`}
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            ) : (
              <tbody>
                <tr>
                  <td colSpan={8} className="bg-canvas p-4">
                    <EmptyState
                      title="No action runs found"
                      message="Every proposed agent action appears here after the SDK calls intercept(). Try changing filters or run a demo action."
                    />
                  </td>
                </tr>
              </tbody>
            )}
          </table>
        </TableShell>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-4">
        <p className="text-sm text-muted">
          Page {summary.page} / {summary.totalPages}
        </p>
        <p className="text-sm text-muted">Total results: {summary.total}</p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() =>
              setQuery((current) => ({ ...current, page: Math.max(1, current.page - 1) }))
            }
            disabled={!hasPrevious || loading}
            className={buttonStyles.secondary}
          >
            Previous
          </button>

          <button
            type="button"
            onClick={() => setQuery((current) => ({ ...current, page: current.page + 1 }))}
            disabled={!hasNext || loading}
            className={buttonStyles.secondary}
          >
            Next
          </button>
        </div>
      </div>
    </>
  );
}
