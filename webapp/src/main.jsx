import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowRight,
  Check,
  CircleDollarSign,
  MessageSquare,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { registerPwaShell } from "./pwa";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

registerPwaShell();

const SIGNALS = [
  {
    kind: "portfolio_loss",
    label: "투자 손실 알림",
    icon: Activity,
    severity: "high",
    receivedFrom: "투자계좌 잔고 조회",
    customerSummary: "고위험 투자 비중이 높고 최근 평가금액이 내려가 방어 조정이 필요할 수 있습니다.",
    checkItems: ["투자 위험 비중", "가용 현금", "카드 결제 예정액", "대출 상환 부담"],
    apiBody: {
      rsp_code: "A0000",
      account_name: "JB 종합계좌",
      valuation_amount_krw: 100000000,
      high_risk_weight: 0.7,
      drawdown_pct: 14,
      available_cash_krw: 23800000,
      upcoming_card_payment_krw: 1130000,
    },
  },
  {
    kind: "insurance_gap",
    label: "보험 보장 공백",
    icon: ShieldCheck,
    severity: "mid",
    receivedFrom: "보험 가입내역 조회",
    customerSummary: "현재 보험 목록에서 심혈관 관련 특약이 보이지 않아 보장 점검이 필요할 수 있습니다.",
    checkItems: ["가입 보험 목록", "보장 항목", "월 보험료", "고객의 의료비 예산"],
    apiBody: {
      rsp_code: "A0000",
      insurance_list: [
        { product_name: "JB 실손의료보험", policy_type: "실손", active: true },
      ],
      missing_coverage_hint: "심혈관 특약 없음",
      monthly_premium_krw: 120000,
    },
  },
  {
    kind: "upcoming_card_payment_pressure",
    label: "결제 부담 알림",
    icon: CircleDollarSign,
    severity: "mid",
    receivedFrom: "카드 청구·계좌 잔액 조회",
    customerSummary: "다가오는 카드 결제와 대출 상환액이 현금흐름에 부담이 될 수 있습니다.",
    checkItems: ["카드 결제 예정액", "대출 월 상환액", "입출금 잔액", "최근 3개월 지출"],
    apiBody: {
      rsp_code: "A0000",
      charge_month: "2026-06",
      upcoming_card_payment_krw: 1130000,
      monthly_loan_payment_krw: 800000,
      available_cash_krw: 5800000,
      medical_charge_krw: 246000,
    },
  },
];

const STATE_LABELS = {
  Monitoring: "대기 중",
  UserApproval: "승인 필요",
};

const KIND_LABELS = {
  report: "요약 리포트",
  cashflow_plan: "현금흐름 계획",
  rebalance_portfolio: "투자 비중 조정",
  review_insurance: "보험 보장 점검",
  notify: "알림 보내기",
  book_hospital: "예약 요청",
};

const STATUS_LABELS = {
  proposed: "제안됨",
  approved: "승인됨",
  rejected: "거절됨",
  deferred: "수정 요청",
  executed: "완료",
  failed: "실패",
};

const FLOW_STEPS = [
  { key: "DataRefresh", label: "데이터 받음", description: "계좌·카드·보험·투자 데이터를 모음" },
  { key: "SignalDetect", label: "이벤트 파악", description: "무슨 일이 생겼는지 분류" },
  { key: "SignalGate", label: "진행 여부 확인", description: "중복과 중요도를 점검" },
  { key: "BuildContext", label: "고객 자료 정리", description: "한 고객의 정보만 묶음" },
  { key: "SpawnAgent", label: "에이전트 분석", description: "상황을 해석하고 제안 작성" },
  { key: "ValidateOutput", label: "결과 검증", description: "형식과 보안 규칙 확인" },
  { key: "PolicyCheck", label: "승인 필요 판단", description: "자동 처리와 승인 대상을 나눔" },
  { key: "ApprovalInterrupt", label: "고객 승인 대기", description: "외부 효과 있는 일은 멈춤" },
  { key: "ExecuteAction", label: "승인 후 실행", description: "승인된 일만 처리" },
  { key: "VerifyResult", label: "처리 확인", description: "실제로 처리됐는지 확인" },
  { key: "Done", label: "완료/기록", description: "결과와 메모리를 저장" },
];

const IS_DEV_PAGE = window.location.pathname.startsWith("/dev");

function App() {
  const [customers, setCustomers] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [session, setSession] = useState(null);
  const [selectedSignal, setSelectedSignal] = useState(SIGNALS[0].kind);
  const [lastEvent, setLastEvent] = useState(null);
  const [reply, setReply] = useState("");
  const [decisionNote, setDecisionNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState("");
  const [error, setError] = useState(null);

  const currentCustomer = useMemo(
    () => customers.find((customer) => customer.id === customerId),
    [customers, customerId],
  );
  const selectedSignalDef = useMemo(
    () => SIGNALS.find((signal) => signal.kind === selectedSignal) ?? SIGNALS[0],
    [selectedSignal],
  );
  const receivedEvent = useMemo(
    () => latestReceivedEvent(session) ?? lastEvent ?? selectedSignalDef,
    [session, lastEvent, selectedSignalDef],
  );

  useEffect(() => {
    request("/customers")
      .then((data) => {
        setCustomers(data);
        if (data[0]) setCustomerId(data[0].id);
      })
      .catch(setApiError(setError));
  }, []);

  useEffect(() => {
    if (!customerId) return;
    createSession(false);
  }, [customerId]);

  async function loadSession(forceNew = false) {
    const data = await request(`/customers/${customerId}/workflow-sessions?force_new=${forceNew}`, {
      method: "POST",
    });
    setSession(data);
    return data;
  }

  async function createSession(forceNew = false) {
    await runBusy("세션 준비 중", async () => {
      await loadSession(forceNew);
    });
  }

  async function triggerSignal() {
    if (!session) return;
    const eventPayload = buildEventPayload(selectedSignalDef);
    setLastEvent({ ...selectedSignalDef, payload: eventPayload });
    await runBusy("금융 데이터를 살펴보는 중", async () => {
      try {
        await streamRequest(`/workflow-sessions/${session.thread_id}/events/stream`, {
          method: "POST",
          body: { source: "event", payload: eventPayload },
        }, updateFromStream);
      } catch (err) {
        if (isMissingWorkflowThread(err)) {
          await recoverAppSession();
          return;
        }
        throw err;
      }
    });
  }

  async function sendReply(event) {
    event.preventDefault();
    if (!session || !reply.trim()) return;
    const text = reply.trim();
    setReply("");
    await runBusy("답장을 남기는 중", async () => {
      try {
        await streamRequest(`/workflow-sessions/${session.thread_id}/messages/stream`, {
          method: "POST",
          body: { text },
        }, updateFromStream);
      } catch (err) {
        if (isMissingWorkflowThread(err)) {
          await recoverAppSession();
          return;
        }
        throw err;
      }
    });
  }

  async function decide(decision, proposalId) {
    if (!session) return;
    await runBusy(decision === "approve" ? "승인한 일을 처리하는 중" : "결정을 반영하는 중", async () => {
      try {
        await streamRequest(`/workflow-sessions/${session.thread_id}/decisions/stream`, {
          method: "POST",
          body: { decision, proposal_id: proposalId, note: decisionNote },
        }, updateFromStream);
        setDecisionNote("");
      } catch (err) {
        if (isMissingWorkflowThread(err)) {
          await recoverAppSession();
          return;
        }
        throw err;
      }
    });
  }

  async function recoverAppSession() {
    await loadSession(true);
    setError({
      status: 200,
      title: "상담 세션을 새로 준비했습니다",
      message: "이전 테스트 세션이 더 이상 남아 있지 않아 새로 만들었습니다. 방금 하려던 일을 다시 눌러주세요.",
    });
  }

  function updateFromStream(event) {
    const streamedSession = event.session ?? event.data?.session ?? null;
    const nextSession = streamedSession
      ? { ...streamedSession, live_stage: event.type === "stage" ? event.data?.stage : undefined }
      : event.type === "complete" || event.type === "session"
        ? event.data
        : null;
    if (nextSession?.thread_id) {
      setSession((current) => {
        const previousStages = event.type === "session" ? [] : current?.stream_seen_stages ?? [];
        const stage = event.type === "stage" ? event.data?.stage : null;
        const streamSeenStages = stage ? Array.from(new Set([...previousStages, stage])) : previousStages;
        return {
          ...nextSession,
          stream_seen_stages: streamSeenStages,
        };
      });
    }
  }

  async function runBusy(label, fn) {
    setBusy(true);
    setActivity(label);
    setError("");
    const startedAt = performance.now();
    try {
      await fn();
    } catch (err) {
      setApiError(setError)(err);
    } finally {
      const elapsed = performance.now() - startedAt;
      if (elapsed < 650) {
        await new Promise((resolve) => setTimeout(resolve, 650 - elapsed));
      }
      setBusy(false);
      setActivity("");
    }
  }

  return (
    <main className="app-shell">
      <aside className="side-rail">
        <div className="brand-block">
          <div className="brand-mark">JB</div>
          <div>
            <h1>금융 도우미</h1>
            <p>상담 테스트 화면</p>
          </div>
        </div>

        <label className="field-label" htmlFor="customer-select">
          고객
        </label>
        <select
          id="customer-select"
          value={customerId}
          onChange={(event) => setCustomerId(event.target.value)}
        >
          {customers.map((customer) => (
            <option key={customer.id} value={customer.id}>
              {customer.name} · {customer.age_band}
            </option>
          ))}
        </select>

        <button className="ghost-button" onClick={() => createSession(true)} disabled={!customerId || busy}>
          <RefreshCw size={16} />
          새 세션
        </button>

        <div className="scope-box">
          <span>상담 상태</span>
          <strong>{STATE_LABELS[session?.state] ?? "준비 중"}</strong>
          <small>{currentCustomer?.name ?? "고객 선택 대기"}</small>
        </div>
      </aside>

      <section className="workspace">
        <header className="toolbar">
          <div>
            <h2>고객 상황 확인</h2>
            <p>{currentCustomer ? `${currentCustomer.name} 고객의 금융 이벤트를 테스트합니다.` : "고객을 선택하세요."}</p>
          </div>
          <button className="primary-button" onClick={triggerSignal} disabled={!session || busy}>
            <Play size={16} />
            데이터 들어온 것처럼 테스트
          </button>
        </header>

        {error ? <SecurityNotice error={error} /> : null}
        <AgentActivity busy={busy} label={activity} session={session} />

        <section className="signal-band">
          {SIGNALS.map((signal) => {
            const Icon = signal.icon;
            return (
              <button
                key={signal.kind}
                className={selectedSignal === signal.kind ? "signal selected" : "signal"}
                onClick={() => setSelectedSignal(signal.kind)}
              >
                <Icon size={18} />
                <span>{signal.label}</span>
              </button>
            );
          })}
        </section>

        <EventDataPanel event={receivedEvent} />

        <section className="main-grid">
          <Conversation messages={session?.messages ?? []} reply={reply} setReply={setReply} onSubmit={sendReply} busy={busy} />
          <Proposals
            proposals={session?.proposals ?? []}
            pending={session?.pending_proposal}
            executions={session?.executions ?? []}
            session={session}
            note={decisionNote}
            setNote={setDecisionNote}
            onDecision={decide}
            busy={busy}
            activity={activity}
          />
        </section>

        <Timeline events={session?.events ?? []} jobs={session?.agent_jobs ?? []} snapshots={session?.snapshots ?? []} />
      </section>
    </main>
  );
}

function DevApp() {
  const [customers, setCustomers] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [session, setSession] = useState(null);
  const [debug, setDebug] = useState(null);
  const [selectedSignal, setSelectedSignal] = useState(SIGNALS[0].kind);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const selectedSignalDef = useMemo(
    () => SIGNALS.find((signal) => signal.kind === selectedSignal) ?? SIGNALS[0],
    [selectedSignal],
  );
  const pending = session?.pending_proposal;

  useEffect(() => {
    request("/customers")
      .then((data) => {
        setCustomers(data);
        if (data[0]) setCustomerId(data[0].id);
      })
      .catch(setApiError(setError));
  }, []);

  useEffect(() => {
    if (!customerId) return;
    createDevSession(false);
  }, [customerId]);

  useEffect(() => {
    if (!session?.thread_id) return;
    const timer = window.setInterval(() => {
      refreshDebug(session.thread_id, { silent: true }).catch(() => {});
    }, 3000);
    return () => window.clearInterval(timer);
  }, [session?.thread_id]);

  async function loadDevSession(forceNew = false) {
    const data = await request(`/customers/${customerId}/workflow-sessions?force_new=${forceNew}`, {
      method: "POST",
    });
    setSession(data);
    setDebug(null);
    return data;
  }

  async function createDevSession(forceNew = false) {
    await devRun(async () => {
      const data = await loadDevSession(forceNew);
      await refreshDebug(data.thread_id, { skipRecovery: true });
    });
  }

  async function triggerDevSignal() {
    if (!session) return;
    await devRun(async () => {
      try {
        const data = await request(`/workflow-sessions/${session.thread_id}/events`, {
          method: "POST",
          body: { source: "event", payload: buildEventPayload(selectedSignalDef) },
        });
        setSession(data);
        await refreshDebug(data.thread_id);
      } catch (err) {
        if (isMissingWorkflowThread(err)) {
          await recoverDevSession();
          return;
        }
        throw err;
      }
    });
  }

  async function refreshDebug(threadId = session?.thread_id, options = {}) {
    if (!threadId) return;
    try {
      const data = await request(`/workflow-sessions/${threadId}/debug`);
      setDebug(data);
      setSession((current) => (current?.thread_id === data.thread_id ? data : current));
      if (!options.silent) setError(null);
    } catch (err) {
      if (isMissingWorkflowThread(err) && !options.skipRecovery) {
        await recoverDevSession(options);
        return;
      }
      throw err;
    }
  }

  async function recoverDevSession(options = {}) {
    const data = await loadDevSession(true);
    await refreshDebug(data.thread_id, { silent: true, skipRecovery: true });
    if (!options.silent) {
      setError({
        status: 200,
        title: "개발자 화면 세션을 새로 준비했습니다",
        message: "이전 workflow thread가 더 이상 없어서 새 thread로 바꿨습니다. 이제 이벤트를 다시 실행하면 됩니다.",
      });
    }
  }

  async function devRun(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setApiError(setError)(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="dev-shell">
      <header className="dev-header">
        <div>
          <h1>개발자용 실행 흐름</h1>
          <p>고객 화면에서 누른 이벤트가 어느 단계까지 갔는지 봅니다. 원문 로그는 아래에 접어둡니다.</p>
        </div>
        <a href="/">고객 화면으로 이동</a>
      </header>

      {error ? <SecurityNotice error={error} /> : null}

      <section className="dev-controls">
        <select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
          {customers.map((customer) => (
            <option key={customer.id} value={customer.id}>
              {customer.name} · {customer.age_band}
            </option>
          ))}
        </select>
        <select value={selectedSignal} onChange={(event) => setSelectedSignal(event.target.value)}>
          {SIGNALS.map((signal) => (
            <option key={signal.kind} value={signal.kind}>
              {signal.label}
            </option>
          ))}
        </select>
        <button className="primary-button" onClick={triggerDevSignal} disabled={!session || busy}>
          이벤트 실행
        </button>
        <button className="ghost-button" onClick={() => refreshDebug()} disabled={!session || busy}>
          상태 새로고침
        </button>
        <button className="ghost-button" onClick={() => createDevSession(true)} disabled={!customerId || busy}>
          새 세션
        </button>
      </section>

      {pending ? (
        <section className="dev-pending">
          <div>
            <strong>고객 화면에서 승인 대기 중</strong>
            <p>{pending.summary}</p>
            <small>개발자 화면은 상태 확인 전용입니다. 승인은 고객 화면에서만 처리합니다.</small>
          </div>
        </section>
      ) : null}

      <DevFlow debug={debug} busy={busy} />

      <section className="dev-grid">
        <DevSummary debug={debug} busy={busy} />
        <DevActivityFeed debug={debug} />
        <DevAgentJobs jobs={debug?.debug_agent_jobs ?? []} runtime={debug?.runtime} />
        <DevPlans proposals={debug?.proposals ?? []} executions={debug?.executions ?? []} />
        <DevRawDetails debug={debug} />
      </section>
    </main>
  );
}

function DevFlow({ debug, busy }) {
  const stage = debug?.graph_snapshot?.values?.stage;
  const latestJob = debug?.debug_agent_jobs?.[0];
  const seen = new Set(
    (debug?.events ?? [])
      .map((event) => event.detail?.stage)
      .filter(Boolean),
  );
  if (seen.has("UpdateMemory")) seen.add("Done");
  if (debug?.debug_agent_jobs?.length) seen.add("SpawnAgent");
  if (debug?.proposals?.length) seen.add("PolicyCheck");
  if (debug?.executions?.length) seen.add("ExecuteAction");
  if (debug?.state === "UserApproval") seen.add("ApprovalInterrupt");
  const activeIndex = FLOW_STEPS.findIndex((step) => step.key === stage);
  const pending = debug?.pending_proposal;

  return (
    <section className="flow-board">
      <div className="flow-board-head">
        <div>
          <span className="section-label">현재 한눈에 보기</span>
          <h2>{flowHeadline(debug, busy)}</h2>
          <p>{flowSubtext(debug, busy)}</p>
        </div>
        <span className={busy ? "live-chip running" : "live-chip"}>{busy ? "실행 중" : "자동 새로고침"}</span>
      </div>
      <ol className="flow-steps">
        {FLOW_STEPS.map((step, index) => {
          const current = step.key === stage || (step.key === "ApprovalInterrupt" && pending);
          const done = seen.has(step.key) || (activeIndex >= 0 && index < activeIndex);
          return (
            <li key={step.key} className={current ? "current" : done ? "done" : ""}>
              <span>{index + 1}</span>
              <div>
                <strong>{step.label}</strong>
                <p>{step.description}</p>
                {step.key === "SpawnAgent" ? <AgentStepIO job={latestJob} /> : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function DevSummary({ debug, busy }) {
  const graph = debug?.graph_snapshot;
  return (
    <section className="dev-panel">
      <h2>현재 상태</h2>
      <dl className="dev-kv">
        <div>
          <dt>상담 상태</dt>
          <dd>{STATE_LABELS[debug?.state] ?? debug?.state ?? "없음"}</dd>
        </div>
        <div>
          <dt>thread</dt>
          <dd>{debug?.thread_id?.slice(0, 8) ?? "-"}</dd>
        </div>
        <div>
          <dt>현재 단계</dt>
          <dd>{stageLabel(graph?.values?.stage) || (busy ? "실행 중" : "대기")}</dd>
        </div>
        <div>
          <dt>승인 대기</dt>
          <dd>{debug?.pending_proposal ? "있음" : "없음"}</dd>
        </div>
      </dl>
      {debug?.pending_proposal ? (
        <div className="mini-state warning">
          <strong>고객 화면에서 멈춰 있음</strong>
          <p>{debug.pending_proposal.summary}</p>
        </div>
      ) : (
        <div className="mini-state">
          <strong>지금은 추가 고객 입력을 기다리는 중</strong>
          <p>이벤트를 다시 넣거나 고객 화면에서 승인/답장을 하면 흐름이 갱신됩니다.</p>
        </div>
      )}
    </section>
  );
}

function DevActivityFeed({ debug }) {
  const latestSignal = [...(debug?.messages ?? [])].reverse().find((message) => message.metadata?.kind === "signal");
  const latestJob = debug?.debug_agent_jobs?.[0];
  const latestEvents = (debug?.events ?? []).slice(-6).reverse();
  return (
    <section className="dev-panel">
      <h2>방금 바뀐 것</h2>
      <div className="activity-cards">
        <div>
          <span>들어온 이벤트</span>
          <strong>{latestSignal?.metadata?.signal?.payload?.title ?? stageLabel(latestSignal?.metadata?.signal?.kind) ?? "없음"}</strong>
          <p>{latestSignal?.content ?? "아직 이벤트가 들어오지 않았습니다."}</p>
        </div>
        <div>
          <span>에이전트 실행</span>
          <strong>{latestJob ? `${latestJob.mode} · ${latestJob.status}` : "없음"}</strong>
          <p>{latestJob ? "입력 context.json을 보고 output.json을 만들었습니다." : "이벤트가 들어오면 실행됩니다."}</p>
        </div>
      </div>
      <ol className="compact-event-list">
        {latestEvents.map((event, index) => (
          <li key={`${event.created_at}-${index}`}>
            <strong>{eventLabel(event.type)}</strong>
            <span>{stageLabel(event.detail?.stage ?? event.detail?.kind)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function AgentStepIO({ job }) {
  const output = job?.output_json ?? job?.result;
  if (!job) {
    return (
      <div className="flow-agent-io empty">
        <span>아직 에이전트 입력/출력이 없습니다.</span>
      </div>
    );
  }
  return (
    <div className="flow-agent-io">
      <span>{agentModeLabel(job.mode)}</span>
      <dl>
        <div>
          <dt>입력</dt>
          <dd>{shortAgentInput(job.input_json)}</dd>
        </div>
        <div>
          <dt>출력</dt>
          <dd>{shortAgentOutput(output)}</dd>
        </div>
      </dl>
    </div>
  );
}

function DevAgentJobs({ jobs, runtime }) {
  const latest = jobs[0];
  const output = latest?.output_json ?? latest?.result;
  const mode = latest?.mode ?? runtime?.agent_job_mode;
  const runtimeInfo = latest?.result?.runtime;
  return (
    <section className="dev-panel wide">
      <h2>에이전트 입력/출력</h2>
      <div className={mode === "codex_cli" ? "runtime-strip real" : "runtime-strip stub"}>
        <strong>현재 에이전트 모드: {agentModeLabel(mode)}</strong>
        <p>
          {mode === "codex_cli"
            ? "이벤트마다 Codex CLI child process를 스폰하고 output.json을 회수합니다."
            : "지금은 실제 Codex CLI가 아니라 데모/테스트용 로컬 스텁 결과를 사용합니다."}
        </p>
      </div>
      {jobs.length === 0 ? <p className="muted">아직 agent job이 없습니다.</p> : null}
      {latest ? (
        <article className="dev-job" key={latest.id}>
          <div className="dev-job-title">
            <strong>{latest.mode} · {latest.status}</strong>
            <span>{latest.id}</span>
          </div>
          {runtimeInfo ? (
            <dl className="job-runtime-kv">
              <div>
                <dt>모델</dt>
                <dd>{runtimeInfo.codex_model ?? "-"}</dd>
              </div>
              <div>
                <dt>추론 정도</dt>
                <dd>{runtimeInfo.codex_reasoning_effort ?? "-"}</dd>
              </div>
              <div>
                <dt>걸린 시간</dt>
                <dd>{runtimeInfo.duration_seconds}s</dd>
              </div>
              <div>
                <dt>입력 크기</dt>
                <dd>{formatBytes(runtimeInfo.input_bytes)}</dd>
              </div>
              <div>
                <dt>출력 크기</dt>
                <dd>{formatBytes(runtimeInfo.output_bytes)}</dd>
              </div>
            </dl>
          ) : null}
          <div className="agent-io-summary">
            <SummaryCard title="입력으로 준 것" rows={agentInputSummary(latest.input_json)} />
            <SummaryCard title="에이전트가 돌려준 것" rows={agentOutputSummary(output)} />
          </div>
          <div className="json-grid raw-json-grid">
            <JsonBlock title="원문 input: context.json" value={latest.input_json} collapsed />
            <JsonBlock title="원문 output: output.json" value={output} collapsed />
          </div>
        </article>
      ) : null}
    </section>
  );
}

function DevPlans({ proposals, executions }) {
  return (
    <section className="dev-panel">
      <h2>제안/실행 결과</h2>
      <div className="dev-readable-list">
        {proposals.length === 0 ? <p className="muted">아직 만들어진 제안이 없습니다.</p> : null}
        {proposals.map((proposal) => (
          <article key={proposal.id} className="dev-proposal-card">
            <div className="dev-card-title">
              <strong>{proposal.summary}</strong>
              <span>{STATUS_LABELS[proposal.status] ?? proposal.status}</span>
            </div>
            <p>{proposal.rationale}</p>
            <div className="proposal-meta">
              <span>{KIND_LABELS[proposal.kind] ?? proposal.kind}</span>
              <span>{proposal.has_external_effect ? "고객 승인 필요" : "자동 처리 가능"}</span>
            </div>
          </article>
        ))}
      </div>

      <div className="dev-readable-list">
        <h3>실제로 처리한 일</h3>
        {executions.length === 0 ? <p className="muted">아직 실행된 일이 없습니다.</p> : null}
        {executions.map((execution) => {
          const proposal = proposals.find((item) => item.id === execution.proposal_id);
          const summary = executionSummary(execution, proposal);
          return (
            <article key={execution.id} className="dev-execution-card">
              <strong>{summary.title}</strong>
              <p>{summary.description}</p>
            </article>
          );
        })}
      </div>

      <JsonBlock title="원문 proposals / executions" value={{ proposals, executions }} collapsed />
    </section>
  );
}

function SummaryCard({ title, rows }) {
  return (
    <div className="summary-card">
      <span>{title}</span>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function JsonBlock({ title, value, collapsed = false }) {
  return (
    <details className="json-block" open={!collapsed}>
      <summary>{title}</summary>
      <pre>{JSON.stringify(value ?? null, null, 2)}</pre>
    </details>
  );
}

function DevRawDetails({ debug }) {
  return (
    <section className="dev-panel wide">
      <h2>원문 로그와 스냅샷</h2>
      <JsonBlock title="전체 LangGraph checkpoint" value={debug?.graph_snapshot?.values ?? {}} collapsed />
      <JsonBlock title="전체 이벤트 로그" value={debug?.events ?? []} collapsed />
      <JsonBlock title="redacted data snapshots" value={debug?.debug_snapshots ?? []} collapsed />
      <JsonBlock title="agent jobs 전체" value={debug?.debug_agent_jobs ?? []} collapsed />
    </section>
  );
}

function flowHeadline(debug, busy) {
  if (busy) return "지금 실행 중입니다";
  if (!debug) return "아직 볼 흐름이 없습니다";
  if (debug.pending_proposal) return "고객 승인 지점에서 멈춰 있습니다";
  const stage = debug.graph_snapshot?.values?.stage;
  if (stage === "Done") return "이번 흐름이 끝났습니다";
  if (debug.debug_agent_jobs?.length) return "에이전트 분석 결과가 준비됐습니다";
  return "새 이벤트를 기다리는 중입니다";
}

function flowSubtext(debug, busy) {
  if (busy) return "이벤트를 받아 고객 자료를 정리하고 에이전트 작업을 실행하고 있습니다.";
  if (!debug) return "고객을 선택하거나 새 세션을 만들면 흐름이 표시됩니다.";
  if (debug.pending_proposal) return debug.pending_proposal.summary;
  if (debug.executions?.length) return "승인된 일과 자동 처리 결과가 실행 내역에 기록되었습니다.";
  return "고객 화면에서 이벤트를 넣거나 답장을 보내면 이 화면이 자동으로 갱신됩니다.";
}

function visibleProposals(session, fallback) {
  return fallback;
}

function visibleExecutions(session, fallback) {
  return fallback;
}

function proposalClassName(proposal, visiblePending) {
  const classes = ["proposal", "stream-card"];
  if (visiblePending?.id === proposal.id) classes.push("pending");
  return classes.join(" ");
}

function proposalStatusLabel(proposal) {
  return STATUS_LABELS[proposal.status] ?? proposal.status;
}

function proposalNeedsApproval(proposal) {
  return proposal?.has_external_effect || ["book_hospital", "submit_claim", "transfer_money", "rebalance_portfolio"].includes(proposal?.kind);
}

function visibleWorkflowSteps(session, busy, activity) {
  if (!session?.thread_id) return [];
  const seen = seenWorkflowStages(session);
  const workflowBusy = busy && activity !== "세션 준비 중";
  const hasStarted = workflowBusy || seen.size > 0 || session.proposals?.length || session.executions?.length || session.pending_proposal;
  if (!hasStarted) return [];

  const currentKey = currentWorkflowStage(session, seen, workflowBusy);
  const currentIndex = Math.max(0, FLOW_STEPS.findIndex((step) => step.key === currentKey));
  const lastSeenIndex = lastSeenWorkflowIndex(seen);
  const revealUntil = session.pending_proposal
    ? Math.max(currentIndex, lastSeenIndex)
    : workflowBusy
      ? Math.min(FLOW_STEPS.length - 1, Math.max(currentIndex, lastSeenIndex + 1))
      : Math.min(FLOW_STEPS.length - 1, Math.max(currentIndex, lastSeenIndex));

  return FLOW_STEPS.slice(0, revealUntil + 1).map((step, index) => {
    let status = "waiting";
    if (step.key === "ApprovalInterrupt" && session.pending_proposal) {
      status = "waiting-action";
    } else if (workflowBusy && step.key === currentKey) {
      status = "running";
    } else if (seen.has(step.key) || index < currentIndex) {
      status = "done";
    }
    return { step, index, status };
  });
}

function currentWorkflowStage(session, seen, busy) {
  if (session?.pending_proposal) return "ApprovalInterrupt";
  if (busy) {
    const next = FLOW_STEPS.find((step) => !seen.has(step.key));
    return next?.key ?? "Done";
  }
  return latestWorkflowStage(session) ?? "DataRefresh";
}

function seenWorkflowStages(session) {
  const seen = new Set(
    (session?.events ?? [])
      .map((event) => event.detail?.stage)
      .filter(Boolean),
  );
  if (seen.has("UpdateMemory")) seen.add("Done");
  if (session?.live_stage) seen.add(session.live_stage === "UpdateMemory" ? "Done" : session.live_stage);
  for (const stage of session?.stream_seen_stages ?? []) {
    seen.add(stage === "UpdateMemory" ? "Done" : stage);
  }
  if (session?.agent_jobs?.some((job) => job.status === "completed")) seen.add("SpawnAgent");
  if (session?.proposals?.length) seen.add("PolicyCheck");
  if (session?.pending_proposal) seen.add("ApprovalInterrupt");
  return seen;
}

function latestWorkflowStage(session) {
  const events = session?.events ?? [];
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const stage = events[index]?.detail?.stage;
    if (stage) return stage === "UpdateMemory" ? "Done" : stage;
  }
  if (session?.pending_proposal) return "ApprovalInterrupt";
  if (session?.executions?.length) return "ExecuteAction";
  if (session?.proposals?.length) return "PolicyCheck";
  return null;
}

function lastSeenWorkflowIndex(seen) {
  let index = -1;
  FLOW_STEPS.forEach((step, stepIndex) => {
    if (seen.has(step.key)) index = Math.max(index, stepIndex);
  });
  return index;
}

function workflowProgressTitle(session, busy, activity) {
  if (busy) return activity || "처리 중입니다";
  if (session?.pending_proposal) return "고객 승인을 기다리고 있습니다";
  const latest = latestWorkflowStage(session);
  if (latest === "Done") return "이번 작업이 끝났습니다";
  if (session?.executions?.length) return "승인한 일을 처리했습니다";
  if (session?.proposals?.length) return "제안을 만들었습니다";
  return "진행 기록을 준비 중입니다";
}

function workflowStatusLabel(status) {
  return {
    done: "끝남",
    running: "처리 중",
    waiting: "다음",
    "waiting-action": "승인 필요",
  }[status] ?? "대기";
}


function AgentActivity({ busy, label, session }) {
  const latestJob = session?.agent_jobs?.[0];
  if (!busy && !latestJob) return null;
  return (
    <section className={busy ? "agent-activity running" : "agent-activity"}>
      <div className="activity-icon">
        {busy ? <span className="spinner" /> : <Sparkles size={18} />}
      </div>
      <div>
        <strong>{busy ? label || "도우미가 확인 중" : "최근 확인 완료"}</strong>
        <p>
          {busy
            ? "계좌, 카드, 보험, 투자 정보를 함께 보고 필요한 조치를 정리합니다."
            : "방금 들어온 데이터를 바탕으로 제안과 처리 결과를 업데이트했습니다."}
        </p>
      </div>
    </section>
  );
}

function SecurityNotice({ error }) {
  return (
    <section className={error.status === 403 ? "security-notice blocked" : "security-notice"}>
      <strong>{error.title ?? "요청을 처리할 수 없습니다"}</strong>
      <p>{error.message ?? String(error)}</p>
    </section>
  );
}

function EventDataPanel({ event }) {
  const payload = event?.payload ?? buildEventPayload(event);
  const apiBody = payload?.api_body ?? event?.apiBody ?? {};
  const checkItems = payload?.check_items ?? event?.checkItems ?? [];
  return (
    <section className="data-panel">
      <div className="data-card">
        <span className="section-label">방금 들어온 데이터</span>
        <h3>{payload?.title ?? event?.label}</h3>
        <p>{payload?.customer_summary ?? event?.customerSummary}</p>
        <dl className="data-facts">
          <div>
            <dt>들어온 곳</dt>
            <dd>{payload?.received_from ?? event?.receivedFrom}</dd>
          </div>
          <div>
            <dt>중요도</dt>
            <dd>{severityLabel(payload?.severity ?? event?.severity)}</dd>
          </div>
        </dl>
      </div>
      <div className="data-card">
        <span className="section-label">도우미가 확인한 것</span>
        <ul className="check-list">
          {checkItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <details className="api-body-box">
        <summary>목업 API 응답 보기</summary>
        <pre>{JSON.stringify(apiBody, null, 2)}</pre>
      </details>
    </section>
  );
}

function Conversation({ messages, reply, setReply, onSubmit, busy }) {
  return (
    <section className="panel conversation-panel">
      <div className="panel-header">
        <h3>대화와 안내</h3>
        <MessageSquare size={18} />
      </div>
      <div className="message-list">
        {messages.length === 0 ? <div className="empty-row">아직 메시지가 없습니다.</div> : null}
        {messages.map((message) => (
          <article key={message.id} className={`message ${message.role}`}>
            <span>{roleLabel(message.role)}</span>
            <p>{message.content}</p>
          </article>
        ))}
      </div>
      <form className="reply-form" onSubmit={onSubmit}>
        <input
          value={reply}
          onChange={(event) => setReply(event.target.value)}
          placeholder="도우미에게 답장하기"
          disabled={busy}
        />
        <button className="icon-button" disabled={!reply.trim() || busy} aria-label="답장 보내기">
          <ArrowRight size={18} />
        </button>
      </form>
    </section>
  );
}

function Proposals({ proposals, pending, executions, session, note, setNote, onDecision, busy, activity }) {
  const displayProposals = busy ? [] : visibleProposals(session, proposals);
  const displayExecutions = busy ? [] : visibleExecutions(session, executions);
  const visiblePending = pending && displayProposals.some((proposal) => proposal.id === pending.id) ? pending : null;
  const executed = new Set(displayExecutions.map((execution) => execution.proposal_id));
  return (
    <section className="panel proposal-panel">
      <div className="panel-header">
        <h3>제안과 처리 결과</h3>
        <span className={visiblePending ? "status waiting" : "status"}>{visiblePending ? "승인 필요" : "확인 완료"}</span>
      </div>
      <WorkflowProgress session={session} busy={busy} activity={activity} />
      <div className="proposal-list">
        {displayProposals.length === 0 ? (
          <div className="empty-row">
            {busy ? "도우미가 일하는 중입니다. 끝나면 제안과 처리 결과를 한 번에 보여드릴게요." : "데이터를 넣으면 도우미 제안이 표시됩니다."}
          </div>
        ) : null}
        {displayProposals.map((proposal) => {
          return (
          <article key={proposal.id} className={proposalClassName(proposal, visiblePending)}>
            <div className="proposal-top">
              <strong>{proposal.summary}</strong>
              <span>{proposalStatusLabel(proposal)}</span>
            </div>
            <p>{proposal.rationale}</p>
            <div className="proposal-meta">
              <span>{KIND_LABELS[proposal.kind] ?? proposal.kind}</span>
              <span>{proposalNeedsApproval(proposal) ? "고객 승인 후 처리" : "바로 정리됨"}</span>
              {executed.has(proposal.id) ? <span>처리 완료</span> : null}
            </div>
          </article>
          );
        })}
      </div>

      {busy ? null : <ExecutionDetails executions={displayExecutions} proposals={displayProposals} />}

      {visiblePending ? (
        <div className="decision-box">
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="승인/거절 전에 남길 메모"
            disabled={busy}
          />
          <div className="decision-actions">
            <button onClick={() => onDecision("approve", visiblePending.id)} disabled={busy} className="approve-button">
              <Check size={16} />
              승인
            </button>
            <button onClick={() => onDecision("reject", visiblePending.id)} disabled={busy} className="reject-button">
              <X size={16} />
              거절
            </button>
            <button onClick={() => onDecision("revise", visiblePending.id)} disabled={busy} className="ghost-button">
              수정
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function WorkflowProgress({ session, busy, activity }) {
  const steps = visibleWorkflowSteps(session, busy, activity);
  if (steps.length === 0) return null;
  return (
    <div className="workflow-progress">
      <div className="workflow-progress-head">
        <span className="section-label">진행 상황</span>
        <strong>{workflowProgressTitle(session, busy, activity)}</strong>
      </div>
      <ol>
        {steps.map(({ step, index, status }) => (
          <li key={step.key} className={status}>
            <span>{index + 1}</span>
            <div>
              <strong>{step.label}</strong>
              <small>{workflowStatusLabel(status)}</small>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ExecutionDetails({ executions, proposals }) {
  if (executions.length === 0) {
    return (
      <div className="execution-list empty">
        <span className="section-label">실제로 처리한 일</span>
        <p>아직 처리된 일이 없습니다. 승인하면 처리 결과가 여기에 표시됩니다.</p>
      </div>
    );
  }

  return (
    <div className="execution-list">
      <span className="section-label">실제로 처리한 일</span>
      {executions.map((execution) => {
        const proposal = proposals.find((item) => item.id === execution.proposal_id);
        const summary = executionSummary(execution, proposal);
        return (
          <article key={execution.id} className="execution-card">
            <div>
              <strong>{summary.title}</strong>
              <p>{summary.description}</p>
            </div>
            <details>
              <summary>자세히 보기</summary>
              <dl>
                {summary.details.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </article>
        );
      })}
    </div>
  );
}

function Timeline({ events, jobs, snapshots }) {
  const recentEvents = events.slice(-8).reverse();
  return (
    <section className="timeline-strip">
      <div>
        <span>받은 일</span>
        <strong>{events.length}</strong>
      </div>
      <div>
        <span>최근 확인</span>
        <strong>{jobs[0]?.status === "completed" ? "완료" : "없음"}</strong>
      </div>
      <div>
        <span>데이터 묶음</span>
        <strong>{snapshots[0] ? "저장됨" : "없음"}</strong>
      </div>
      <ol>
        {recentEvents.map((event, index) => (
          <li key={`${event.created_at}-${index}`}>
            <span>{eventLabel(event.type)}</span>
            <small>{stageLabel(event.detail?.stage ?? event.detail?.kind)}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}

function buildEventPayload(signal) {
  return {
    kind: signal.kind,
    severity: signal.severity,
    title: signal.label,
    received_from: signal.receivedFrom,
    customer_summary: signal.customerSummary,
    check_items: signal.checkItems,
    api_body: signal.apiBody,
  };
}

function latestReceivedEvent(session) {
  const signalMessage = [...(session?.messages ?? [])]
    .reverse()
    .find((message) => message.metadata?.kind === "signal");
  const payload = signalMessage?.metadata?.signal?.payload;
  if (!payload) return null;
  return {
    kind: payload.kind,
    label: payload.title,
    severity: payload.severity,
    receivedFrom: payload.received_from,
    customerSummary: payload.customer_summary,
    checkItems: payload.check_items,
    apiBody: payload.api_body,
    payload,
  };
}

function executionSummary(execution, proposal) {
  const result = execution.result ?? {};
  const kind = proposal?.kind;
  if (kind === "report") {
    return {
      title: "요약 리포트를 만들었습니다",
      description: result.report ?? proposal?.summary ?? "고객 상황을 정리했습니다.",
      details: [["처리 상태", statusText(execution.status)], ["내용", result.report ?? proposal?.summary ?? "-"]],
    };
  }
  if (kind === "cashflow_plan") {
    return {
      title: "현금흐름 계획을 만들었습니다",
      description: result.plan ?? "앞으로 3개월 결제와 상환을 버틸 수 있는 계획을 정리했습니다.",
      details: [["처리 상태", statusText(execution.status)], ["계획", result.plan ?? "-"]],
    };
  }
  if (kind === "rebalance_portfolio") {
    return {
      title: "투자 비중 조정을 반영했습니다",
      description: "고객이 승인한 뒤, 데모 계좌에서 고위험 비중을 낮추는 조정을 처리했습니다.",
      details: [
        ["처리 상태", statusText(execution.status)],
        ["조정 결과", cleanText(result.proposal)],
        ["고위험 목표", percentText(result.target_high_risk_weight)],
        ["안정형 목표", percentText(result.target_low_risk_weight)],
      ],
    };
  }
  if (kind === "review_insurance") {
    return {
      title: "보험 보장 점검을 기록했습니다",
      description: "승인한 보장 점검 내용을 데모 기록에 반영했습니다.",
      details: [
        ["처리 상태", statusText(execution.status)],
        ["점검 항목", result.coverage ?? "보장 공백"],
        ["기록 상태", cleanText(result.status)],
        ["확인 번호", result.claim_id ?? "-"],
      ],
    };
  }
  if (kind === "notify") {
    return {
      title: "알림을 보냈습니다",
      description: proposal?.summary ?? "필요한 안내를 전달했습니다.",
      details: [["처리 상태", statusText(execution.status)], ...Object.entries(result).map(([key, value]) => [key, String(value)])],
    };
  }
  if (kind === "book_hospital") {
    return {
      title: "예약 요청을 처리했습니다",
      description: proposal?.summary ?? "고객이 승인한 예약 요청을 처리했습니다.",
      details: [["처리 상태", statusText(execution.status)], ...Object.entries(result).map(([key, value]) => [key, String(value)])],
    };
  }
  return {
    title: `${KIND_LABELS[kind] ?? "요청"}을 처리했습니다`,
    description: proposal?.summary ?? "승인된 요청을 처리했습니다.",
    details: Object.entries(result).map(([key, value]) => [key, String(value)]),
  };
}

function agentInputSummary(input) {
  const signal = input?.signal ?? {};
  const payload = signal.payload ?? {};
  const context = input?.context ?? {};
  const sections = Object.keys(context)
    .filter((key) => context[key] && typeof context[key] === "object")
    .map((key) => contextSectionLabel(key));
  return [
    ["들어온 이벤트", payload.title ?? stageLabel(signal.kind) ?? "이벤트"],
    ["고객 범위", input?.scope?.label === "single_customer_snapshot" ? "한 고객 자료만 전달" : "제한된 자료"],
    ["함께 본 자료", sections.slice(0, 6).join(", ") || "고객 자료 없음"],
  ];
}

function shortAgentInput(input) {
  const signal = input?.signal ?? {};
  const payload = signal.payload ?? {};
  const context = input?.context ?? {};
  const sections = Object.keys(context)
    .filter((key) => context[key] && typeof context[key] === "object")
    .map((key) => contextSectionLabel(key));
  return `${payload.title ?? stageLabel(signal.kind)} · ${sections.slice(0, 4).join(", ") || "고객 자료"}`;
}

function shortAgentOutput(output) {
  const assessment = output?.assessment ?? {};
  const proposals = output?.plan?.proposals ?? [];
  return `${needLabel(assessment.primary_need)} · 제안 ${proposals.length}개`;
}

function agentOutputSummary(output) {
  const assessment = output?.assessment ?? {};
  const plan = output?.plan ?? {};
  const proposals = plan.proposals ?? [];
  return [
    ["가장 중요한 필요", needLabel(assessment.primary_need)],
    ["확신도", assessment.confidence !== undefined ? `${Math.round(Number(assessment.confidence) * 100)}%` : "-"],
    ["만든 제안", `${proposals.length}개`],
    ["요약", output?.message ?? plan.explanation ?? assessment.rationale ?? "-"],
  ];
}

function formatBytes(value) {
  const bytes = Number(value ?? 0);
  if (bytes < 1024) return `${bytes}B`;
  return `${(bytes / 1024).toFixed(1)}KB`;
}

function contextSectionLabel(key) {
  return {
    profile: "고객 기본정보",
    health: "건강",
    insurance: "보험",
    portfolio: "투자",
    loans: "대출",
    accounts: "계좌",
    card_bills: "카드",
    memory: "기억/선호",
  }[key] ?? key;
}

function needLabel(value) {
  return {
    none: "추가 조치 없음",
    cashflow: "현금흐름",
    insurance: "보험 점검",
    asset_defense: "자산 방어",
    investment_adjust: "투자 조정",
    medical_cost: "의료비 대비",
    life_plan: "생활 계획",
  }[value] ?? value ?? "-";
}

function agentModeLabel(mode) {
  return {
    codex_cli: "Codex CLI",
    local_stub: "로컬 스텁",
  }[mode] ?? mode ?? "미확인";
}

function roleLabel(role) {
  return { assistant: "도우미", user: "고객", system: "받은 데이터", tool: "처리 결과" }[role] ?? role;
}

function severityLabel(value) {
  return { high: "높음", mid: "보통", low: "낮음" }[value] ?? "보통";
}

function eventLabel(type) {
  return {
    graph_state: "진행",
    context_pack: "자료 정리",
    agent_job: "도우미 확인",
    policy: "제안 분류",
    approval: "고객 결정",
    execution: "처리",
    memory: "기록",
  }[type] ?? "기록";
}

function stageLabel(value) {
  return {
    DataRefresh: "데이터 확인",
    SignalDetect: "이벤트 확인",
    SignalGate: "중복 점검",
    BuildContext: "자료 묶기",
    SpawnAgent: "도우미 분석",
    ValidateOutput: "결과 확인",
    PolicyCheck: "승인 필요 확인",
    ApprovalInterrupt: "승인 대기",
    ExecuteAction: "처리 실행",
    VerifyResult: "결과 확인",
    Done: "완료",
    portfolio_loss: "투자 손실 알림",
    insurance_gap: "보험 보장 공백",
    upcoming_card_payment_pressure: "결제 부담 알림",
  }[value] ?? "기록됨";
}

function statusText(status) {
  return status === "success" ? "완료" : "실패";
}

function cleanText(value) {
  return String(value ?? "-").replace(" (mock)", "").replace("mock ", "데모 ");
}

function percentText(value) {
  if (value === undefined || value === null) return "-";
  return `${Math.round(Number(value) * 100)}%`;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    throw parseApiError(text, response.status, response.statusText);
  }
  return response.json();
}

async function streamRequest(path, options = {}, onEvent) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    throw parseApiError(text, response.status, response.statusText);
  }
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const event = parseSseChunk(chunk);
      if (event) {
        if (event.type === "error") throw event.data;
        onEvent?.(event);
      }
    }
  }
  buffer += decoder.decode();
  const finalEvent = parseSseChunk(buffer);
  if (finalEvent) {
    if (finalEvent.type === "error") throw finalEvent.data;
    onEvent?.(finalEvent);
  }
}

function parseSseChunk(chunk) {
  if (!chunk.trim()) return null;
  let type = "message";
  const dataLines = [];
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  const raw = dataLines.join("\n");
  let data = raw;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = raw;
    }
  }
  return { type, data, session: data?.session };
}

function setApiError(setError) {
  return (err) => {
    if (err && typeof err === "object" && "message" in err) {
      setError(err);
      return;
    }
    setError({ title: "요청을 처리할 수 없습니다", message: String(err) });
  };
}

function parseApiError(text, status, fallback) {
  try {
    const parsed = JSON.parse(text);
    const detail = parsed.detail;
    if (detail && typeof detail === "object") {
      return { status, title: detail.title, message: detail.message };
    }
    if (typeof detail === "string") {
      return { status, title: status === 403 ? "접근할 수 없습니다" : fallback, message: detail };
    }
  } catch {
    // Fall through to plain-text handling.
  }
  return { status, title: fallback, message: text || fallback };
}

function isMissingWorkflowThread(error) {
  return error?.status === 404 && String(error?.message ?? "").includes("워크플로우 thread");
}

createRoot(document.getElementById("root")).render(IS_DEV_PAGE ? <DevApp /> : <App />);
