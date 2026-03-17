import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Activity, Settings, Plus, LayoutDashboard, GitMerge, TrendingUp, CheckCircle, XCircle, ArrowDownToLine } from "lucide-react";

import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { api, type FusionStats } from "@/lib/api";

function AcceptancePieChart({ stats }: { stats: { accepted: number; rejected: number; total: number } }) {
  const total = stats.total || 1;
  const acceptedPct = (stats.accepted / total) * 100;
  const rejectedPct = (stats.rejected / total) * 100;
  
  return (
    <div className="flex items-center gap-4">
      <div className="relative h-16 w-16 overflow-hidden rounded-full border-4 border-ink-200 dark:border-white/20">
        <div 
          className="absolute inset-0 bg-emerald-500"
          style={{ clipPath: `inset(0 ${100 - acceptedPct}% 0 0)` }}
        />
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle className="h-4 w-4 text-emerald-500" />
          <span className="font-medium">{stats.accepted} accepted ({acceptedPct.toFixed(1)}%)</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <XCircle className="h-4 w-4 text-red-500" />
          <span className="font-medium">{stats.rejected} rejected ({rejectedPct.toFixed(1)}%)</span>
        </div>
      </div>
    </div>
  );
}

function FusionPanel({ stats, isLoading, error }: { stats: FusionStats | undefined; isLoading: boolean; error: Error | null }) {
  if (isLoading) {
    return (
      <section className="panel-muted p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <GitMerge className="h-5 w-5 text-signal-blue" />
            Oracle Fusion
          </h2>
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-signal-blue border-t-transparent" />
        </div>
      </section>
    );
  }

  if (error || !stats) {
    return (
      <section className="panel-muted p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <GitMerge className="h-5 w-5 text-signal-blue" />
            Oracle Fusion
          </h2>
        </div>
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
          Failed to load fusion stats: {error?.message || "Unknown error"}
        </div>
      </section>
    );
  }

  return (
    <section className="panel-muted p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <GitMerge className="h-5 w-5 text-signal-blue" />
          Oracle Fusion
        </h2>
        <span className="rounded-full bg-signal-blue/10 px-2 py-1 text-xs font-medium text-signal-blue">
          Phase 6
        </span>
      </div>
      
      {/* Incoming Goals */}
      <div className="mb-4 grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-ink-50 p-3 dark:bg-white/5">
          <div className="text-2xl font-bold">{stats.incoming_goals.count}</div>
          <div className="text-xs text-ink-500 dark:text-ink-300">Total Goals</div>
        </div>
        <div className="rounded-lg bg-ink-50 p-3 dark:bg-white/5">
          <div className="text-2xl font-bold text-emerald-500">{stats.incoming_goals.active}</div>
          <div className="text-xs text-ink-500 dark:text-ink-300">Active</div>
        </div>
        <div className="rounded-lg bg-ink-50 p-3 dark:bg-white/5">
          <div className="text-2xl font-bold text-amber-500">{stats.incoming_goals.pending}</div>
          <div className="text-xs text-ink-500 dark:text-ink-300">Pending</div>
        </div>
      </div>

      {/* Candidate Rankings Preview */}
      {stats.candidate_rankings.length > 0 && (
        <div className="mb-4">
          <h3 className="mb-2 text-sm font-semibold">Top Candidate Rankings</h3>
          <div className="space-y-1">
            {stats.candidate_rankings.slice(0, 3).map((ranking, idx) => (
              <div key={`${ranking.goal_id}-${ranking.candidate_id}`} className="flex items-center justify-between rounded bg-ink-50 px-3 py-2 text-xs dark:bg-white/5">
                <span className="font-mono">{ranking.candidate_id.slice(0, 20)}...</span>
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 ${
                    ranking.source === "aae_advised" ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" :
                    ranking.source === "hybrid" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" :
                    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                  }`}>
                    {ranking.source}
                  </span>
                  <span className="font-medium">{(ranking.predicted_score * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Acceptance Pie Chart */}
      <div className="mb-4">
        <h3 className="mb-2 text-sm font-semibold">Acceptance Rate</h3>
        <AcceptancePieChart stats={stats.acceptance_stats} />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-ink-200/70 p-3 dark:border-white/10">
          <div className="flex items-center gap-1 text-xs text-ink-500 dark:text-ink-300">
            <CheckCircle className="h-3 w-3 text-emerald-500" />
            Test Pass Rate
          </div>
          <div className="text-lg font-bold">{(stats.test_pass_rate * 100).toFixed(1)}%</div>
        </div>
        <div className="rounded-lg border border-ink-200/70 p-3 dark:border-white/10">
          <div className="flex items-center gap-1 text-xs text-ink-500 dark:text-ink-300">
            <TrendingUp className="h-3 w-3 text-purple-500" />
            Avg Score Lift
          </div>
          <div className="text-lg font-bold">+{(stats.average_score_lift * 100).toFixed(1)}%</div>
        </div>
      </div>
      
      {/* Fallback Frequency */}
      <div className="mt-3 rounded-lg border border-ink-200/70 p-3 dark:border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 text-xs text-ink-500 dark:text-ink-300">
            <ArrowDownToLine className="h-3 w-3 text-amber-500" />
            Fallback to Oracle-Native
          </div>
          <div className="font-bold">{(stats.fallback_frequency * 100).toFixed(1)}%</div>
        </div>
      </div>
    </section>
  );
}

export function OverviewScreen() {
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: api.listWorkflows, refetchInterval: 4000 });
  const benchmarks = useQuery({ queryKey: ["benchmarks"], queryFn: api.benchmarkSummary, refetchInterval: 15000 });
  const diagnostics = useQuery({ queryKey: ["diagnostics"], queryFn: api.diagnostics, refetchInterval: 10000 });
  const fusionStats = useQuery({ queryKey: ["fusionStats"], queryFn: api.fusionStats, refetchInterval: 8000 });

  const latestMetrics = benchmarks.data?.latest?.metrics ?? {};

  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-4">
        <MetricCard label="Active Workflows" value={workflows.data?.filter((item) => item.status === "running" || item.status === "cancel_requested").length ?? 0} />
        <MetricCard label="Strict Fix Rate" value={latestMetrics.strict_fix_rate ?? 0} hint="Strict metric excludes degraded sandbox runs." />
        <MetricCard label="Raw Fix Rate" value={latestMetrics.raw_fix_rate ?? 0} hint="Raw metric shows all successes before trust gating." />
        <MetricCard label="Degraded Runs" value={latestMetrics.degraded_run_count ?? 0} hint="Local fallback runs never count as solved." />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="panel-muted p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Activity className="h-5 w-5 text-signal-blue" />
              Recent Workflows
            </h2>
            <Link to="/launch" className="group flex items-center gap-1 text-sm font-medium text-signal-blue transition-colors hover:text-signal-blue/80">
              Launch new
              <Plus className="h-4 w-4 transition-transform group-hover:scale-110" />
            </Link>
          </div>
          <div className="space-y-3">
            {(workflows.data ?? []).slice(0, 8).map((workflow) => (
              <Link
                key={workflow.workflow_id}
                to="/workflows/$workflowId"
                params={{ workflowId: workflow.workflow_id }}
                className="flex items-start justify-between rounded-xl border border-ink-200/70 px-4 py-3 transition hover:border-signal-blue/40 dark:border-white/10"
              >
                <div>
                  <div className="font-medium">{workflow.workflow_type}</div>
                  <div className="mt-1 font-mono text-xs text-ink-500 dark:text-ink-300">{workflow.workflow_id}</div>
                </div>
                <StatusBadge value={workflow.status} />
              </Link>
            ))}
          </div>
        </section>

        <section className="panel-muted p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <LayoutDashboard className="h-5 w-5 text-signal-blue" />
              System Diagnostics
            </h2>
            <Link to="/settings" className="group flex items-center gap-1 text-sm font-medium text-signal-blue transition-colors hover:text-signal-blue/80">
              Runtime settings
              <Settings className="h-4 w-4 transition-transform group-hover:rotate-45" />
            </Link>
          </div>
          <div className="space-y-3">
            {(diagnostics.data ?? []).map((diagnostic) => (
              <div key={diagnostic.name} className="rounded-xl border border-ink-200/70 px-4 py-3 dark:border-white/10">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{diagnostic.name}</div>
                  <StatusBadge value={diagnostic.status} />
                </div>
                <div className="mt-2 text-sm text-ink-600 dark:text-ink-200">{diagnostic.summary}</div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Oracle Fusion Panel - Full Width */}
      <div className="grid gap-4 xl:grid-cols-[1fr_1fr_1fr]">
        <FusionPanel 
          stats={fusionStats.data} 
          isLoading={fusionStats.isLoading} 
          error={fusionStats.error as Error | null} 
        />
        
        <section className="panel-muted p-5 xl:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <GitMerge className="h-5 w-5 text-signal-blue" />
              Fusion Insights
            </h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-ink-200/70 p-4 dark:border-white/10">
              <div className="text-sm text-ink-500 dark:text-ink-300">AAE Advice Utilization</div>
              <div className="mt-1 text-2xl font-bold">
                {fusionStats.data 
                  ? ((1 - (fusionStats.data.fallback_frequency)) * 100).toFixed(1) 
                  : "—"
                }%
              </div>
              <div className="mt-1 text-xs text-ink-400">Percentage using AAE candidates</div>
            </div>
            <div className="rounded-lg border border-ink-200/70 p-4 dark:border-white/10">
              <div className="text-sm text-ink-500 dark:text-ink-300">Hybrid Plan Rate</div>
              <div className="mt-1 text-2xl font-bold">
                {fusionStats.data 
                  ? (fusionStats.data.candidate_rankings.filter(r => r.source === "hybrid").length / 
                     (fusionStats.data.candidate_rankings.length || 1) * 100).toFixed(1)
                  : "—"
                }%
              </div>
              <div className="mt-1 text-xs text-ink-400">Fused Oracle + AAE plans</div>
            </div>
            <div className="rounded-lg border border-ink-200/70 p-4 dark:border-white/10">
              <div className="text-sm text-ink-500 dark:text-ink-300">Avg Candidates/Goal</div>
              <div className="mt-1 text-2xl font-bold">
                {fusionStats.data 
                  ? (fusionStats.data.candidate_rankings.length / 
                     (fusionStats.data.incoming_goals.count || 1)).toFixed(1)
                  : "—"
                }
              </div>
              <div className="mt-1 text-xs text-ink-400">Mean candidate count per goal</div>
            </div>
            <div className="rounded-lg border border-ink-200/70 p-4 dark:border-white/10">
              <div className="text-sm text-ink-500 dark:text-ink-300">Oracle-Native Only</div>
              <div className="mt-1 text-2xl font-bold">
                {fusionStats.data 
                  ? fusionStats.data.candidate_rankings.filter(r => r.source === "oracle_native").length
                  : "—"
                }
              </div>
              <div className="mt-1 text-xs text-ink-400">Plans without AAE input</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
