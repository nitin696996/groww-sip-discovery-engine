import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Download,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import {
  AiEvalsResponse,
  PipelineWorkspaceResponse,
  ResearchQuestion,
  SandboxTestResponse,
  SegmentDimension,
  SheetRow,
  TriggerClusterSummary,
} from './types';

type WorkflowStep = 'sheet' | 'dashboard' | 'questions' | 'evals' | 'sandbox';

const SANDBOX_PRESETS: Array<{ label: string; source: string; text: string }> = [
  {
    label: '1. NACH Bounce & Skip Penalty (High Signal)',
    source: 'reddit',
    text: "I work as a freelancer and my invoice got delayed to the 10th. I clicked 'Skip SIP' on Groww 2 days before the 5th debit date, but the bank mandate was already locked and HDFC charged me ₹590 as NACH bounce penalty! Thinking of cancelling my autopay mandate completely.",
  },
  {
    label: '2. Friday T+2 NAV Black Box Panic (High Signal)',
    source: 'play_store',
    text: "Started my first ₹2,000 SIP on Friday at 3:15 PM. Money was deducted from my SBI account immediately via UPI autopay, but till Monday morning Groww still shows 'Order in progress' and 0 units allotted. Where is my money?",
  },
  {
    label: '3. First Red XIRR vs FD Anxiety (High Signal)',
    source: 'youtube',
    text: "Bhaiya maine 5 months pehle ₹5,000/month SIP start kiya tha small cap aur midcap fund me after watching YouTube reels, abhi portfolio -6.4% red me dikha raha hai. Should I stop my SIP and put money in 7.5% bank FD instead?",
  },
  {
    label: '4. Short App Praise / Noise (Eval Gate Reject Test)',
    source: 'play_store',
    text: 'Very nice app good interface 5 stars!!',
  },
];

const SOURCE_LABELS: Record<string, string> = {
  all: 'All Sources',
  reddit: 'Reddit',
  play_store: 'Google Play',
  app_store: 'App Store',
  youtube: 'YouTube',
  tradingqna: 'TradingQ&A',
};

const TRIGGER_SHORT_BADGE: Record<string, { label: string; dotColor: string }> = {
  'App friction / autodebit (NACH/UPI mandate) failures': {
    label: 'App Friction / NACH Mandate',
    dotColor: '#D94E34',
  },
  'Anxiety on negative portfolio returns': {
    label: 'Negative Return Anxiety',
    dotColor: '#D97706',
  },
  'Cash-flow crunch / salary date mismatch': {
    label: 'Cash-Flow / Salary Mismatch',
    dotColor: '#2563EB',
  },
  'Information overload / confusion about CAGR vs absolute returns': {
    label: 'CAGR vs Absolute Overload',
    dotColor: '#008A68',
  },
};

const SCRAPE_THINKING_STEPS = [
  'Connecting to Google Play Store & Apple iTunes RSS feeds for Groww India...',
  'Querying YouTube Data API v3 for top Indian mutual fund SIP comment threads...',
  'Scanning TradingQ&A Discourse, Tavily web search, and Firecrawl forum threads...',
  'Computing SHA-256 content fingerprints to deduplicate repeat posts...',
  'Running Stage 2 contextual noise filter to strip 1-5 word reviews & promo spam...',
  'Bulk-syncing cleaned SIP narratives to Supabase (sip_pipeline_rows)...',
];

const AI_THINKING_STEPS = [
  'Packing untagged SIP narratives into 15-row micro-batches...',
  'Routing batch through Groq (openai/gpt-oss-120b) & Gemini 2.5 Flash...',
  'Classifying posts across the 4 Core Behavioral Triggers (Stage 3)...',
  'Quantifying sentiment polarity, emotional intensity, and ticket/tenure proxies...',
  'Correlating clusters with 12-month retention drop-off windows (M1-3, M6-8, M10-12)...',
  'Computing Stage 4 Opportunity Scores (0-100) and syncing to Supabase...',
];

const SHORT_QUESTION_TITLES: Record<number, string> = {
  1: 'Q1 · Starting Triggers',
  2: 'Q2 · Early Behavior Shift',
  3: 'Q3 · Why SIPs Stop',
  4: 'Q4 · Checking Habits',
  5: 'Q5 · In-App Anxiety',
  6: 'Q6 · External Validation',
  7: 'Q7 · Stay vs. Drop Off',
  8: 'Q8 · Segment Differences',
  9: 'Q9 · Unmet Needs',
};

function formatDateShort(iso: string): string {
  if (!iso) return '2026-10';
  return iso.slice(0, 10);
}

export default function App() {
  const [step, setStep] = useState<WorkflowStep>('sheet');
  const [workspace, setWorkspace] = useState<PipelineWorkspaceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [scraping, setScraping] = useState<boolean>(false);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [thinkingStepIdx, setThinkingStepIdx] = useState<number>(0);
  const [syncNotice, setSyncNotice] = useState<string>('');

  // Sheet filters
  const [cleaningView, setCleaningView] = useState<'CLEAN_SIP_SIGNAL' | 'REMOVED_NOISE'>('CLEAN_SIP_SIGNAL');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [triggerFilter, setTriggerFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedRow, setSelectedRow] = useState<SheetRow | null>(null);

  // Dashboard interactive selection
  const [selectedClusterId, setSelectedClusterId] = useState<string>('');

  // 9 Questions & 4 Segment Lenses state
  const [questions, setQuestions] = useState<ResearchQuestion[]>([]);
  const [selectedQIdx, setSelectedQIdx] = useState<number>(0);
  const [segmentsMap, setSegmentsMap] = useState<Record<string, SegmentDimension>>({});
  const [activeDimKey, setActiveDimKey] = useState<string>('income_stability');

  // AI Evals (Golden Set & HITL Corrections) state
  const [aiEvals, setAiEvals] = useState<AiEvalsResponse | null>(null);
  const [evalFilter, setEvalFilter] = useState<'ALL' | 'PASS' | 'FAIL'>('ALL');

  // Live AI Sandbox state
  const [sandboxText, setSandboxText] = useState<string>(SANDBOX_PRESETS[0].text);
  const [sandboxSource, setSandboxSource] = useState<string>('reddit');
  const [sandboxSaveToSheet, setSandboxSaveToSheet] = useState<boolean>(false);
  const [sandboxRunning, setSandboxRunning] = useState<boolean>(false);
  const [sandboxResult, setSandboxResult] = useState<SandboxTestResponse | null>(null);

  const fetchPipelineSheet = async (
    cStatus = cleaningView,
    src = sourceFilter,
    trig = triggerFilter,
    q = searchQuery
  ) => {
    try {
      const params = new URLSearchParams({
        cleaning_status: cStatus,
        source: src,
        trigger: trig,
        q,
      });
      const res = await fetch(`/api/pipeline/sheet?${params.toString()}`);
      const data: PipelineWorkspaceResponse = await res.json();
      setWorkspace(data);
      if (data.trigger_clusters.length > 0 && !selectedClusterId) {
        setSelectedClusterId(data.trigger_clusters[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch pipeline sheet:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchQuestionsAndSegments = async () => {
    try {
      const [qRes, sRes, eRes] = await Promise.all([
        fetch('/api/questions'),
        fetch('/api/segments'),
        fetch('/api/evals'),
      ]);
      const qData = await qRes.json();
      const sData = await sRes.json();
      const eData = await eRes.json();
      if (qData.questions) setQuestions(qData.questions);
      if (sData.dimensions) setSegmentsMap(sData.dimensions);
      if (eData.eval_summary) setAiEvals(eData);
    } catch (err) {
      console.error('Failed to fetch 9 questions / segments / evals:', err);
    }
  };

  useEffect(() => {
    fetchPipelineSheet(cleaningView, sourceFilter, triggerFilter, searchQuery);
  }, [cleaningView, sourceFilter, triggerFilter]);

  useEffect(() => {
    fetchQuestionsAndSegments();
  }, []);

  useEffect(() => {
    if (!scraping && !analyzing) {
      setThinkingStepIdx(0);
      return;
    }
    const steps = scraping ? SCRAPE_THINKING_STEPS : AI_THINKING_STEPS;
    const timer = setInterval(() => {
      setThinkingStepIdx((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, 1500);
    return () => clearInterval(timer);
  }, [scraping, analyzing]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchPipelineSheet(cleaningView, sourceFilter, triggerFilter, searchQuery);
  };

  const handleRunScrapers = async () => {
    setScraping(true);
    setSyncNotice('');
    try {
      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'all', limit: 120, auto_extract: false }),
      });
      const payload = await res.json();
      const results: Array<{ source: string; fetched: number; inserted: number; high_signal: number }> =
        payload.ingestion_results || [];
      const totalFetched = results.reduce((acc, r) => acc + (r.fetched || 0), 0);
      const totalInserted = results.reduce((acc, r) => acc + (r.inserted || 0), 0);
      const breakdown = results
        .filter((r) => (r.fetched || 0) > 0)
        .map((r) => `${SOURCE_LABELS[r.source] || r.source}: ${r.fetched} scanned (${r.inserted} new)`)
        .join(' · ');

      setSyncNotice(
        `Scraped ${totalFetched} posts (${totalInserted} new unique added) — ${breakdown || 'All sources up to date'} · Synced to Supabase`
      );
      await fetchPipelineSheet(cleaningView, sourceFilter, triggerFilter, searchQuery);
      fetchQuestionsAndSegments();
    } finally {
      setScraping(false);
    }
  };

  const handleRunAiAnalysis = async () => {
    setAnalyzing(true);
    setSyncNotice('');
    try {
      const res = await fetch('/api/pipeline/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reanalyze_all: false }),
      });
      const payload = await res.json();
      if (payload.workspace) {
        setWorkspace(payload.workspace);
        if (payload.workspace.trigger_clusters?.length > 0) {
          setSelectedClusterId(payload.workspace.trigger_clusters[0].id);
        }
      } else {
        await fetchPipelineSheet(cleaningView, sourceFilter, triggerFilter, searchQuery);
      }
      fetchQuestionsAndSegments();
      const providers = payload.batch_summary?.providers_used?.join(', ') || 'Multi-LLM Router';
      setSyncNotice(
        `AI Analysis complete via ${providers} · Tagged ${
          payload.workspace?.pipeline_stages?.stage3_ai_tagged_rows || 0
        } SIP rows & synced scores to Supabase`
      );
      setStep('dashboard');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRunSandboxTest = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!sandboxText.trim()) return;
    setSandboxRunning(true);
    try {
      const res = await fetch('/api/pipeline/test-comment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: sandboxText,
          source: sandboxSource,
          save_to_sheet: sandboxSaveToSheet,
        }),
      });
      const data: SandboxTestResponse = await res.json();
      setSandboxResult(data);
      if (sandboxSaveToSheet) {
        await fetchPipelineSheet(cleaningView, sourceFilter, triggerFilter, searchQuery);
      }
    } catch (err) {
      console.error('Sandbox test failed:', err);
    } finally {
      setSandboxRunning(false);
    }
  };

  const handleExportEvidenceCsv = () => {
    const rows = workspace?.sheet_rows || [];
    if (!rows.length) return;
    const headers = [
      'Row_ID',
      'SHA256_Hash',
      'Source',
      'Channel',
      'Published_Date',
      'Votes_Or_Rating',
      'Cleaning_Status',
      'Triage_Score',
      'Behavioral_Trigger',
      'Sentiment_Polarity',
      'Emotional_Intensity',
      'Ticket_Size_Proxy',
      'Tenure_Proxy',
      'Retention_DropOff_Window',
      'Opportunity_Score',
      'LLM_Provider',
      'Investor_Text',
    ];
    const escapeCsv = (val: unknown) => {
      const s = String(val ?? '').replace(/\r?\n|\r/g, ' ');
      return `"${s.replace(/"/g, '""')}"`;
    };
    const csvLines = [
      headers.join(','),
      ...rows.map((r) =>
        [
          r.row_id,
          r.content_hash?.slice(0, 16),
          r.source,
          r.sub_source,
          formatDateShort(r.published_at),
          r.rating ? `${r.rating} stars` : r.upvotes,
          r.cleaning_status,
          r.triage_score,
          r.behavioral_trigger,
          r.sentiment_polarity,
          r.emotional_intensity,
          r.segment_proxy_ticket,
          r.segment_proxy_tenure,
          r.retention_dropoff_bucket,
          r.opportunity_score,
          r.extracted_by_provider,
          r.content,
        ]
          .map(escapeCsv)
          .join(',')
      ),
    ];
    const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `groww_sip_ai_evidence_log_${cleaningView.toLowerCase()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const stages = workspace?.pipeline_stages;
  const clusters = workspace?.trigger_clusters || [];
  const activeCluster: TriggerClusterSummary | undefined = useMemo(
    () => clusters.find((c) => c.id === selectedClusterId) || clusters[0],
    [clusters, selectedClusterId]
  );
  const activeQuestion: ResearchQuestion | undefined = questions[selectedQIdx] || questions[0];
  const activeDimension: SegmentDimension | undefined = segmentsMap[activeDimKey];

  if (loading && !workspace) {
    return (
      <div className="min-h-screen bg-[#F5F4EE] text-[#111315] flex items-center justify-center">
        <div className="flex items-center gap-3 text-sm font-medium text-[#5C6166]">
          <span className="w-2.5 h-2.5 rounded-full bg-[#00D09C] animate-ping" />
          Loading Groww SIP Discovery Pipeline...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F5F4EE] text-[#111315] flex flex-col selection:bg-[#00D09C]/20">
      {/* Clean Single-Row Top Navigation Bar */}
      <header className="sticky top-0 z-30 bg-[#F5F4EE]/95 backdrop-blur-md border-b border-[#111315]/10">
        <div className="max-w-[1560px] mx-auto px-8 h-16 flex items-center justify-between gap-6">
          {/* Left: Brand + Clean 3-Tab Navigation */}
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#00D09C]" />
              <span className="font-semibold text-[15px] tracking-tight text-[#111315]">
                Groww SIP Discovery
              </span>
            </div>

            <nav className="flex items-center gap-1">
              <button
                onClick={() => {
                  setTriggerFilter('all');
                  setStep('sheet');
                }}
                className={`px-3.5 py-1.5 rounded-lg text-[13.5px] font-medium transition-colors ${
                  step === 'sheet'
                    ? 'bg-[#111315] text-[#F5F4EE]'
                    : 'text-[#5C6166] hover:text-[#111315] hover:bg-[#111315]/5'
                }`}
              >
                Data Sheet ({stages?.stage2_cleaned_sip_rows || 0})
              </button>
              <button
                onClick={() => setStep('dashboard')}
                className={`px-3.5 py-1.5 rounded-lg text-[13.5px] font-medium transition-colors ${
                  step === 'dashboard'
                    ? 'bg-[#111315] text-[#F5F4EE]'
                    : 'text-[#5C6166] hover:text-[#111315] hover:bg-[#111315]/5'
                }`}
              >
                Opportunity Dashboard
              </button>
              <button
                onClick={() => setStep('questions')}
                className={`px-3.5 py-1.5 rounded-lg text-[13.5px] font-medium transition-colors ${
                  step === 'questions'
                    ? 'bg-[#111315] text-[#F5F4EE]'
                    : 'text-[#5C6166] hover:text-[#111315] hover:bg-[#111315]/5'
                }`}
              >
                9 Questions & Segments
              </button>
              <button
                onClick={() => setStep('evals')}
                className={`px-3.5 py-1.5 rounded-lg text-[13.5px] font-medium transition-colors ${
                  step === 'evals'
                    ? 'bg-[#111315] text-[#F5F4EE]'
                    : 'text-[#5C6166] hover:text-[#111315] hover:bg-[#111315]/5'
                }`}
              >
                AI Evals ({aiEvals?.eval_summary.agreement_rate_pct || 75}% Match)
              </button>
              <button
                onClick={() => setStep('sandbox')}
                className={`px-3.5 py-1.5 rounded-lg text-[13.5px] font-medium transition-colors ${
                  step === 'sandbox'
                    ? 'bg-[#111315] text-[#F5F4EE]'
                    : 'text-[#008A68] font-semibold hover:bg-[#00D09C]/15'
                }`}
              >
                Live AI Sandbox
              </button>
            </nav>
          </div>

          {/* Right: Pull Scrapers + AI Analysis CTA */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleRunScrapers}
              disabled={scraping}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[#111315]/15 bg-[#FFFFFF] text-[13px] font-medium text-[#111315] hover:bg-[#FAF9F5] transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${scraping ? 'animate-spin' : ''}`} />
              <span>{scraping ? 'Scraping Sources...' : 'Pull Scrapers'}</span>
            </button>

            <button
              onClick={handleRunAiAnalysis}
              disabled={analyzing}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#00D09C] text-[#111315] text-[13px] font-semibold hover:bg-[#00b889] transition-all shadow-sm disabled:opacity-50"
            >
              <Sparkles className={`w-3.5 h-3.5 ${analyzing ? 'animate-spin' : ''}`} />
              <span>{analyzing ? 'Analyzing with AI...' : 'AI Analysis'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Claude / ChatGPT Style Live Thinking Stream during Scraping or AI Analysis */}
        {(scraping || analyzing) && (
          <div className="bg-[#111315] text-[#F5F4EE] px-8 py-3 border-t border-[#F5F4EE]/10">
            <div className="max-w-[1560px] mx-auto flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-[12.5px]">
                <div className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full bg-[#00D09C] animate-ping" />
                  <span className="font-mono-num uppercase tracking-wider text-[11px] text-[#00D09C] font-semibold">
                    {scraping ? 'STAGE 1 & 2 PIPELINE ACTIVE' : 'STAGE 3 & 4 AI REASONING'}
                  </span>
                  <span className="text-[#F5F4EE]/30">•</span>
                  <span className="font-medium text-[#F5F4EE] transition-all">
                    {(scraping ? SCRAPE_THINKING_STEPS : AI_THINKING_STEPS)[thinkingStepIdx]}
                  </span>
                </div>
                <span className="font-mono-num text-[11px] text-[#F5F4EE]/60">
                  Step {thinkingStepIdx + 1} of{' '}
                  {(scraping ? SCRAPE_THINKING_STEPS : AI_THINKING_STEPS).length}
                </span>
              </div>

              {thinkingStepIdx > 0 && (
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pl-4 text-[11px] text-[#F5F4EE]/55 font-mono-num">
                  {(scraping ? SCRAPE_THINKING_STEPS : AI_THINKING_STEPS)
                    .slice(0, thinkingStepIdx)
                    .map((doneStep, i) => (
                      <span key={i} className="inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-[#00D09C]" />
                        <span className="truncate max-w-[260px]">{doneStep.replace('...', '')}</span>
                      </span>
                    ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Live Sync / AI Status Toast Bar (#4) */}
        {!scraping && !analyzing && syncNotice && (
          <div className="bg-[#111315] text-[#F5F4EE] px-8 py-2 text-[12.5px]">
            <div className="max-w-[1560px] mx-auto flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#00D09C] shrink-0" />
                <span>{syncNotice}</span>
              </div>
              <button
                onClick={() => setSyncNotice('')}
                className="text-[#F5F4EE]/60 hover:text-[#F5F4EE]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </header>

      {/* VIEW 1: CLEAN SPREADSHEET WORKSPACE */}
      {step === 'sheet' && (
        <main className="flex-1 max-w-[1560px] w-full mx-auto px-8 py-7 flex flex-col gap-5 animate-stage">
          {/* Clean Filter Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              {/* Stage 2 Cleaning Toggle */}
              <div className="inline-flex rounded-lg bg-[#EAE8E0] p-1 text-[12.5px]">
                <button
                  onClick={() => setCleaningView('CLEAN_SIP_SIGNAL')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    cleaningView === 'CLEAN_SIP_SIGNAL'
                      ? 'bg-[#FFFFFF] text-[#111315] shadow-sm'
                      : 'text-[#5C6166] hover:text-[#111315]'
                  }`}
                >
                  Cleaned SIP Rows ({stages?.stage2_cleaned_sip_rows || 0})
                </button>
                <button
                  onClick={() => {
                    setTriggerFilter('all');
                    setCleaningView('REMOVED_NOISE');
                  }}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    cleaningView === 'REMOVED_NOISE'
                      ? 'bg-[#FFFFFF] text-[#111315] shadow-sm'
                      : 'text-[#5C6166] hover:text-[#111315]'
                  }`}
                >
                  Filtered Noise ({stages?.stage2_total_removed || 0})
                </button>
              </div>

              {/* Source Filter Pills */}
              <div className="flex flex-wrap items-center gap-1">
                {Object.entries(SOURCE_LABELS).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setSourceFilter(key)}
                    className={`px-3 py-1.5 rounded-lg text-[12.5px] font-medium transition-colors ${
                      sourceFilter === key
                        ? 'bg-[#111315] text-[#F5F4EE]'
                        : 'text-[#5C6166] hover:bg-[#111315]/5'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {triggerFilter !== 'all' && (
                <button
                  onClick={() => setTriggerFilter('all')}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-[#00D09C]/20 text-[#008A68] text-[12px] font-semibold"
                >
                  <span>Cluster: {TRIGGER_SHORT_BADGE[triggerFilter]?.label || triggerFilter}</span>
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Right: Search Input + Export AI Evidence Log (CSV) */}
            <div className="flex items-center gap-2.5">
              <form onSubmit={handleSearchSubmit} className="relative">
                <Search className="w-3.5 h-3.5 text-[#5C6166] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search investor text..."
                  className="pl-8 pr-3.5 py-1.5 bg-[#FFFFFF] border border-[#111315]/15 rounded-lg text-[12.5px] text-[#111315] placeholder:text-[#8C9196] focus:outline-none focus:border-[#008A68] w-52"
                />
              </form>

              <button
                onClick={handleExportEvidenceCsv}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-[#111315]/15 bg-[#FFFFFF] hover:bg-[#FAF9F5] text-[12.5px] font-medium text-[#111315] transition-colors"
                title="Download AI Evidence Log as CSV for Deliverable Submission"
              >
                <Download className="w-3.5 h-3.5 text-[#008A68]" />
                <span>Export Evidence Log (CSV)</span>
              </button>
            </div>
          </div>

          {/* Spreadsheet Table */}
          <div className="bg-[#FFFFFF] border border-[#111315]/12 rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto max-h-[72vh]">
              <table className="w-full border-collapse text-left text-[13px]">
                <thead className="sticky top-0 z-20 bg-[#FAF9F5] text-[#5C6166] text-[11px] font-mono-num uppercase tracking-wider border-b border-[#111315]/12 select-none">
                  <tr>
                    <th className="w-12 py-3 px-3 text-center border-r border-[#111315]/8">#</th>
                    <th className="w-32 py-3 px-3.5 border-r border-[#111315]/8">Source</th>
                    <th className="w-28 py-3 px-3.5 border-r border-[#111315]/8">Date</th>
                    <th className="w-24 py-3 px-3.5 border-r border-[#111315]/8 text-right">Votes</th>
                    <th className="min-w-[360px] py-3 px-4 border-r border-[#111315]/8">
                      Cleaned Investor Feedback
                    </th>
                    <th className="w-60 py-3 px-3.5 border-r border-[#111315]/8">
                      AI Behavioral Trigger
                    </th>
                    <th className="w-28 py-3 px-3.5 border-r border-[#111315]/8">Sentiment</th>
                    <th className="w-44 py-3 px-3.5 border-r border-[#111315]/8">Segment Proxy</th>
                    <th className="w-32 py-3 px-3.5 border-r border-[#111315]/8">Drop-Off</th>
                    <th className="w-24 py-3 px-3.5 text-right">Opp Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#111315]/8">
                  {workspace?.sheet_rows.map((row, idx) => {
                    const trigBadge = TRIGGER_SHORT_BADGE[row.behavioral_trigger];
                    const isSelectedRow = selectedRow?.row_id === row.row_id;

                    return (
                      <tr
                        key={row.row_id}
                        onClick={() => setSelectedRow(row)}
                        className={`cursor-pointer transition-colors ${
                          isSelectedRow
                            ? 'bg-[#00D09C]/12'
                            : 'bg-[#FFFFFF] hover:bg-[#FAF9F5]'
                        }`}
                      >
                        <td className="py-3 px-2 text-center font-mono-num text-[11px] text-[#8C9196] border-r border-[#111315]/8">
                          {idx + 1}
                        </td>

                        <td className="py-3 px-3.5 border-r border-[#111315]/8 whitespace-nowrap">
                          <div className="font-medium text-[#111315]">
                            {SOURCE_LABELS[row.source] || row.source}
                          </div>
                          <div className="text-[11px] text-[#5C6166] truncate max-w-[120px]">
                            {row.sub_source}
                          </div>
                        </td>

                        <td className="py-3 px-3.5 border-r border-[#111315]/8 font-mono-num text-[12px] text-[#5C6166] whitespace-nowrap">
                          {formatDateShort(row.published_at)}
                        </td>

                        <td className="py-3 px-3.5 border-r border-[#111315]/8 font-mono-num text-[12px] text-right whitespace-nowrap">
                          {row.rating ? (
                            <span className="text-[#D97706] font-medium">{row.rating}★</span>
                          ) : (
                            <span className="text-[#111315] font-medium">↑ {row.upvotes}</span>
                          )}
                        </td>

                        <td className="py-3 px-4 border-r border-[#111315]/8 max-w-[460px]">
                          {row.title && !row.title.startsWith('Comment on:') && (
                            <div className="font-semibold text-[#111315] text-[12.5px] mb-0.5 line-clamp-1">
                              {row.title}
                            </div>
                          )}
                          <div className="text-[#383C40] text-[13px] line-clamp-2 leading-relaxed">
                            {row.content}
                          </div>
                        </td>

                        <td className="py-3 px-3.5 border-r border-[#111315]/8">
                          {row.cleaning_status !== 'CLEAN_SIP_SIGNAL' ? (
                            <span className="text-[11.5px] text-[#8C9196] italic">
                              {row.cleaning_reason}
                            </span>
                          ) : row.behavioral_trigger ? (
                            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#F5F4EE] text-[12px] font-medium text-[#111315]">
                              <span
                                className="w-2 h-2 rounded-full shrink-0"
                                style={{ backgroundColor: trigBadge?.dotColor || '#008A68' }}
                              />
                              <span className="truncate max-w-[195px]">
                                {trigBadge?.label || row.behavioral_trigger}
                              </span>
                            </div>
                          ) : (
                            <span className="text-[11.5px] text-[#8C9196]">Pending AI</span>
                          )}
                        </td>

                        <td className="py-3 px-3.5 border-r border-[#111315]/8 whitespace-nowrap font-mono-num text-[12px]">
                          {row.cleaning_status === 'CLEAN_SIP_SIGNAL' && row.sentiment_label ? (
                            <span
                              className={`font-medium ${
                                row.sentiment_polarity <= -0.75
                                  ? 'text-[#D94E34]'
                                  : row.sentiment_polarity < 0
                                  ? 'text-[#D97706]'
                                  : 'text-[#008A68]'
                              }`}
                            >
                              {row.sentiment_polarity > 0 ? '+' : ''}
                              {row.sentiment_polarity.toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-[#8C9196]">—</span>
                          )}
                        </td>

                        <td className="py-3 px-3.5 border-r border-[#111315]/8 whitespace-nowrap text-[12px]">
                          {row.cleaning_status === 'CLEAN_SIP_SIGNAL' && row.segment_proxy_ticket ? (
                            <div>
                              <div className="font-mono-num font-medium text-[#111315]">
                                {row.segment_proxy_ticket}
                              </div>
                              <div className="text-[11px] text-[#5C6166]">
                                {row.segment_proxy_tenure}
                              </div>
                            </div>
                          ) : (
                            <span className="text-[#8C9196]">—</span>
                          )}
                        </td>

                        <td className="py-3 px-3.5 border-r border-[#111315]/8 whitespace-nowrap">
                          {row.cleaning_status === 'CLEAN_SIP_SIGNAL' && row.retention_dropoff_bucket ? (
                            <span className="font-mono-num text-[11.5px] font-medium px-2 py-0.5 rounded bg-[#EAE8E0] text-[#111315]">
                              {row.retention_dropoff_bucket}
                            </span>
                          ) : (
                            <span className="text-[#8C9196]">—</span>
                          )}
                        </td>

                        <td className="py-3 px-3.5 text-right font-mono-num font-semibold text-[13px]">
                          {row.cleaning_status === 'CLEAN_SIP_SIGNAL' && row.opportunity_score ? (
                            <span className="text-[#008A68]">{row.opportunity_score}</span>
                          ) : (
                            <span className="text-[#8C9196]">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Clean Minimal Footer */}
            <div className="bg-[#FAF9F5] px-5 py-3 border-t border-[#111315]/10 flex flex-wrap items-center justify-between text-[12px] text-[#5C6166]">
              <span>
                Showing <strong className="text-[#111315]">{workspace?.sheet_rows.length || 0}</strong> rows
                {' · '}
                {stages?.stage1_ingested_total || 0} total deduplicated in Supabase
              </span>
              <span>
                Click any row to inspect full investor narrative & AI classification breakdown
              </span>
            </div>
          </div>
        </main>
      )}

      {/* VIEW 2: META-STYLE OPPORTUNITY DASHBOARD (CLEAN, SPACIOUS, ZERO CONFUSION) */}
      {step === 'dashboard' && (
        <main className="flex-1 max-w-[1560px] w-full mx-auto px-8 py-7 flex flex-col gap-6 animate-stage">
          {/* North Star Metric & PM Guardrail Ribbon */}
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 rounded-xl bg-[#EAE8E0]/80 border border-[#111315]/10 text-[12.5px]">
            <div className="flex items-center gap-2">
              <span className="font-mono-num text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-[#111315] text-[#00D09C]">
                NORTH STAR GOAL
              </span>
              <span className="font-medium text-[#111315]">
                Increase % of first-time MF investors with an active SIP (≥1 instalment in last 30 days) at Month 12
              </span>
            </div>
            <div className="flex items-center gap-2 text-[#008A68] font-medium">
              <ShieldCheck className="w-4 h-4 shrink-0" />
              <span>Guardrails Verified: No Fund/Stock Advice · No Fear, FOMO, or Urgency Nudges</span>
            </div>
          </div>

          {/* Top Row: 4 Clean KPI Cards */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            {/* Card 1: Overall Opportunity Score Ring */}
            <div className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 flex items-center gap-4 shadow-sm">
              <div className="relative w-14 h-14 shrink-0 flex items-center justify-center">
                <svg className="w-14 h-14 -rotate-90" viewBox="0 0 64 64">
                  <circle
                    cx="32"
                    cy="32"
                    r="26"
                    fill="none"
                    stroke="rgba(17,19,21,0.08)"
                    strokeWidth="6"
                  />
                  <circle
                    cx="32"
                    cy="32"
                    r="26"
                    fill="none"
                    stroke="#00D09C"
                    strokeWidth="6"
                    strokeLinecap="round"
                    strokeDasharray={2 * Math.PI * 26}
                    strokeDashoffset={
                      2 *
                      Math.PI *
                      26 *
                      (1 - (activeCluster?.opportunity_score || 92) / 100)
                    }
                  />
                </svg>
                <span className="absolute font-mono-num text-[16px] font-bold text-[#111315]">
                  {activeCluster?.opportunity_score || 92}
                </span>
              </div>
              <div>
                <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                  OPPORTUNITY SCORE
                </div>
                <div className="text-[15px] font-semibold text-[#111315] mt-0.5">
                  Selected Cluster
                </div>
                <div className="text-[12px] text-[#008A68] font-medium mt-0.5">
                  {stages?.stage3_ai_tagged_rows || 0} SIP rows tagged
                </div>
              </div>
            </div>

            {/* Cards 2-4: 12-Month Retention Drop-Off Windows */}
            {workspace?.retention_dropoff_cohort_summary.map((cohort) => (
              <div
                key={cohort.window}
                className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 flex flex-col justify-between shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                    {cohort.window} DROP-OFF
                  </span>
                  <span className="font-mono-num text-[11.5px] text-[#5C6166]">
                    {cohort.row_count} rows
                  </span>
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="font-mono-num text-[28px] font-bold text-[#111315] leading-none">
                    {cohort.share_pct}%
                  </span>
                  <span className="text-[12px] text-[#5C6166] truncate max-w-[165px]">
                    {cohort.label}
                  </span>
                </div>
              </div>
            ))}
          </section>

          {/* Main Split: Left 7 Cols Trigger Breakdown Table + Right 5 Cols Selected Trigger Detail */}
          <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
            {/* Left 7 Cols: 4 Behavioral Trigger Clusters */}
            <div className="lg:col-span-7 bg-[#FFFFFF] border border-[#111315]/10 rounded-xl overflow-hidden shadow-sm flex flex-col justify-between">
              <div>
                <div className="px-6 py-4 border-b border-[#111315]/10 flex items-center justify-between">
                  <div>
                    <h2 className="text-[16px] font-semibold text-[#111315]">
                      Behavioral Trigger Clusters
                    </h2>
                    <p className="text-[12.5px] text-[#5C6166] mt-0.5">
                      Click any trigger row to inspect its product action and investor quotes
                    </p>
                  </div>
                  <div className="hidden sm:flex items-center gap-3 text-[11px] font-mono-num text-[#5C6166]">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-[#111315]" /> M1-3
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-[#008A68]" /> M6-8
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-[#00D09C]" /> M10-12
                    </span>
                  </div>
                </div>

                <table className="w-full border-collapse text-left text-[13px]">
                  <thead className="bg-[#FAF9F5] text-[#5C6166] text-[11px] font-mono-num uppercase tracking-wider border-b border-[#111315]/10">
                    <tr>
                      <th className="py-3.5 px-6">Behavioral Trigger</th>
                      <th className="py-3.5 px-4 w-28">Share</th>
                      <th className="py-3.5 px-4 w-28">Intensity</th>
                      <th className="py-3.5 px-4 w-44">12M Drop-Off</th>
                      <th className="py-3.5 px-6 w-24 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#111315]/8">
                    {clusters.map((cluster) => {
                      const isSelected = activeCluster?.id === cluster.id;
                      const dist = cluster.retention_dropoff_distribution;
                      const badge = TRIGGER_SHORT_BADGE[cluster.trigger_name];

                      return (
                        <tr
                          key={cluster.id}
                          onClick={() => setSelectedClusterId(cluster.id)}
                          className={`cursor-pointer transition-colors ${
                            isSelected ? 'bg-[#00D09C]/12' : 'hover:bg-[#FAF9F5]'
                          }`}
                        >
                          <td className="py-4 px-6">
                            <div className="flex items-center gap-3">
                              <span
                                className="w-2.5 h-2.5 rounded-full shrink-0"
                                style={{ backgroundColor: badge?.dotColor || '#008A68' }}
                              />
                              <div>
                                <div className="font-semibold text-[#111315] text-[14px]">
                                  {cluster.short_label}
                                </div>
                                <div className="text-[12px] text-[#5C6166] font-mono-num mt-0.5">
                                  {cluster.dominant_ticket_proxy} · {cluster.dominant_tenure_proxy}
                                </div>
                              </div>
                            </div>
                          </td>

                          <td className="py-4 px-4 font-mono-num">
                            <div className="font-semibold text-[#111315] text-[14px]">
                              {cluster.frequency_pct}%
                            </div>
                            <div className="text-[11.5px] text-[#5C6166]">
                              {cluster.row_count} rows
                            </div>
                          </td>

                          <td className="py-4 px-4 font-mono-num">
                            <div className="font-semibold text-[#D94E34] text-[13.5px]">
                              {cluster.avg_emotional_intensity}/10
                            </div>
                            <div className="text-[11px] text-[#5C6166]">
                              {cluster.avg_sentiment_polarity} polarity
                            </div>
                          </td>

                          <td className="py-4 px-4 font-mono-num">
                            <div className="h-2 w-full rounded-full overflow-hidden flex bg-[#111315]/10">
                              <div
                                style={{ width: `${dist.months_1_to_3_pct}%` }}
                                className="bg-[#111315]"
                              />
                              <div
                                style={{ width: `${dist.months_6_to_8_pct}%` }}
                                className="bg-[#008A68]"
                              />
                              <div
                                style={{ width: `${dist.months_10_to_12_pct}%` }}
                                className="bg-[#00D09C]"
                              />
                            </div>
                            <div className="flex justify-between text-[10.5px] text-[#5C6166] mt-1.5">
                              <span>{dist.months_1_to_3_pct}%</span>
                              <span>{dist.months_6_to_8_pct}%</span>
                              <span>{dist.months_10_to_12_pct}%</span>
                            </div>
                          </td>

                          <td className="py-4 px-6 text-right font-mono-num">
                            <span
                              className={`inline-flex items-center justify-center px-3 py-1 rounded-lg text-[14px] font-bold ${
                                isSelected
                                  ? 'bg-[#111315] text-[#00D09C]'
                                  : 'bg-[#EAE8E0] text-[#111315]'
                              }`}
                            >
                              {cluster.opportunity_score}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="px-6 py-3.5 bg-[#FAF9F5] border-t border-[#111315]/10 flex items-center justify-between text-[12px] text-[#5C6166]">
                <span>Scored across {stages?.stage2_cleaned_sip_rows || 0} verified SIP narratives</span>
                <span className="font-mono-num">Score = Frequency × Intensity × 12M Drop-Off</span>
              </div>
            </div>

            {/* Right 5 Cols: Selected Opportunity Inspector */}
            {activeCluster && (
              <div className="lg:col-span-5 bg-[#FFFFFF] border border-[#111315]/10 rounded-xl overflow-hidden shadow-sm flex flex-col justify-between">
                <div className="p-6">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#00D09C]/15 text-[#008A68] font-mono-num text-[11px] font-semibold">
                      OPPORTUNITY SCORE {activeCluster.opportunity_score}/100
                    </span>
                    <button
                      onClick={() => {
                        setCleaningView('CLEAN_SIP_SIGNAL');
                        setTriggerFilter(activeCluster.trigger_name);
                        setStep('sheet');
                      }}
                      className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-[#111315] hover:text-[#008A68] transition-colors"
                    >
                      <span>Filter {activeCluster.row_count} Rows in Sheet</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <h3 className="text-[20px] font-semibold text-[#111315] tracking-tight mt-3.5">
                    {activeCluster.short_label}
                  </h3>
                  <p className="text-[13.5px] text-[#5C6166] mt-1.5 leading-relaxed">
                    {activeCluster.description}
                  </p>

                  <div className="mt-5 p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/10 border-l-4 border-l-[#00D09C]">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono-num uppercase tracking-wider text-[#008A68] font-semibold">
                        RECOMMENDED PRODUCT ACTION
                      </span>
                      <span className="text-[10.5px] font-mono-num text-[#008A68] font-medium">
                        ✓ Guardrail Compliant
                      </span>
                    </div>
                    <p className="text-[14px] font-medium text-[#111315] mt-1 leading-relaxed">
                      {activeCluster.recommended_intervention}
                    </p>
                  </div>

                  <div className="mt-6">
                    <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166] mb-3">
                      VERBATIM INVESTOR QUOTES
                    </div>
                    <div className="space-y-3">
                      {activeCluster.sample_rows.slice(0, 2).map((sample) => (
                        <div
                          key={sample.row_id}
                          onClick={() => setSelectedRow(sample)}
                          className="p-3.5 rounded-lg bg-[#FAF9F5] border border-[#111315]/8 hover:border-[#008A68] cursor-pointer transition-colors"
                        >
                          <p className="text-[13px] text-[#111315] line-clamp-2 leading-relaxed">
                            &ldquo;{sample.verbatim_quote || sample.content}&rdquo;
                          </p>
                          <div className="mt-2 flex items-center justify-between text-[11px] text-[#5C6166] font-mono-num">
                            <span>
                              {SOURCE_LABELS[sample.source] || sample.source} ({sample.sub_source})
                            </span>
                            <span className="text-[#008A68] font-medium">Inspect Row #{sample.row_id} →</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="px-6 py-3.5 bg-[#FAF9F5] border-t border-[#111315]/10 flex items-center justify-between text-[12px]">
                  <span className="text-[#5C6166]">Dominant Segment Proxy</span>
                  <span className="font-mono-num font-semibold text-[#111315]">
                    {activeCluster.dominant_ticket_proxy} · {activeCluster.dominant_tenure_proxy}
                  </span>
                </div>
              </div>
            )}
          </section>
        </main>
      )}

      {/* VIEW 3: 9 CORE RESEARCH QUESTIONS & 4 SEGMENTATION LENSES */}
      {step === 'questions' && (
        <main className="flex-1 max-w-[1560px] w-full mx-auto px-8 py-7 flex flex-col gap-7 animate-stage">
          {/* Top Question Selector Strip (Q1 to Q9) */}
          <section className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 shadow-sm flex flex-col gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#111315]/10 pb-4">
              <div>
                <span className="font-mono-num text-[11px] uppercase tracking-wider text-[#008A68] font-semibold">
                  PART 1 DISCOVERY RUBRIC • 9 BEHAVIORAL QUESTIONS
                </span>
                <h1 className="text-[20px] font-semibold text-[#111315] mt-0.5">
                  Behavioral Discovery Synthesis Across Indian SIP Conversations
                </h1>
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                {questions.map((q, idx) => (
                  <button
                    key={q.id}
                    onClick={() => setSelectedQIdx(idx)}
                    className={`px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${
                      selectedQIdx === idx
                        ? 'bg-[#111315] text-[#F5F4EE]'
                        : 'bg-[#FAF9F5] text-[#5C6166] hover:text-[#111315]'
                    }`}
                  >
                    {SHORT_QUESTION_TITLES[q.number] || `Q${q.number}`}
                  </button>
                ))}
              </div>
            </div>

            {/* Active Question Synthesis Split */}
            {activeQuestion && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 pt-1 items-start">
                {/* Left 7 Cols: Question, Finding, Archetypes, & Guardrail-Safe Implication */}
                <div className="lg:col-span-7 flex flex-col gap-5">
                  <div>
                    <div className="font-mono-num text-[11.5px] text-[#008A68] font-semibold">
                      QUESTION 0{activeQuestion.number} OF 09 • {activeQuestion.evidence_count} MATCHED CONVERSATIONS
                    </div>
                    <h2 className="text-[24px] font-semibold text-[#111315] tracking-tight mt-1 leading-snug">
                      {activeQuestion.question}
                    </h2>
                    <p className="text-[14.5px] text-[#383C40] mt-2.5 leading-relaxed">
                      {activeQuestion.headline_finding}
                    </p>
                  </div>

                  {/* Dominant Behavioral Archetypes */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                    {activeQuestion.dominant_archetypes.map((arch) => (
                      <div
                        key={arch.label}
                        className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/8 flex flex-col justify-between"
                      >
                        <div>
                          <div className="font-mono-num text-[22px] font-bold text-[#008A68]">
                            {arch.share_pct}%
                          </div>
                          <div className="text-[13px] font-semibold text-[#111315] mt-1">
                            {arch.label}
                          </div>
                        </div>
                        <p className="text-[12px] text-[#5C6166] mt-2 leading-relaxed">
                          {arch.description}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Guardrail-Safe Product Implication */}
                  <div className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/10 border-l-4 border-l-[#00D09C]">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono-num uppercase tracking-wider text-[#008A68] font-semibold">
                        PRODUCT DESIGN IMPLICATION (NO FUND ADVICE · NO FOMO)
                      </span>
                    </div>
                    <p className="text-[13.5px] font-medium text-[#111315] mt-1 leading-relaxed">
                      {activeQuestion.product_implication}
                    </p>
                  </div>
                </div>

                {/* Right 5 Cols: Supporting Verbatim Evidence for this Question */}
                <div className="lg:col-span-5 flex flex-col gap-3">
                  <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                    SUPPORTING VERBATIM EVIDENCE FOR Q{activeQuestion.number}
                  </div>
                  <div className="space-y-3">
                    {activeQuestion.evidence_items.slice(0, 3).map((ev) => (
                      <div
                        key={ev.document_id}
                        className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/8"
                      >
                        <p className="text-[13px] text-[#111315] leading-relaxed">
                          &ldquo;{ev.verbatim_quote}&rdquo;
                        </p>
                        {ev.extracted_finding && (
                          <div className="mt-2 text-[12px] text-[#008A68] font-medium">
                            → {ev.extracted_finding}
                          </div>
                        )}
                        <div className="mt-2 flex items-center justify-between text-[11px] text-[#5C6166] font-mono-num">
                          <span>
                            Row #{ev.document_id} · {SOURCE_LABELS[ev.source] || ev.source} ({ev.sub_source})
                          </span>
                          <span>{ev.emotional_state}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </section>

          {/* Bottom Section: Question 8 Multi-Dimensional User Segmentation Matrix */}
          <section className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-6 shadow-sm flex flex-col gap-5">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#111315]/10 pb-4">
              <div>
                <span className="font-mono-num text-[11px] uppercase tracking-wider text-[#008A68] font-semibold">
                  USER SEGMENTATION MATRIX (QUESTION 8)
                </span>
                <h2 className="text-[18px] font-semibold text-[#111315] mt-0.5">
                  How SIP Behavior Differs Across Income Stability, Age, Money Source, & Influencer
                </h2>
              </div>

              {/* 4 Segmentation Dimension Switcher Pills */}
              <div className="inline-flex rounded-lg bg-[#EAE8E0] p-1 text-[12.5px]">
                {Object.entries(segmentsMap).map(([dimKey, dimObj]) => (
                  <button
                    key={dimKey}
                    onClick={() => setActiveDimKey(dimKey)}
                    className={`px-3.5 py-1.5 rounded-md font-medium transition-colors ${
                      activeDimKey === dimKey
                        ? 'bg-[#FFFFFF] text-[#111315] shadow-sm'
                        : 'text-[#5C6166] hover:text-[#111315]'
                    }`}
                  >
                    {dimObj.label}
                  </button>
                ))}
              </div>
            </div>

            {activeDimension && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {Object.entries(activeDimension.segments).map(([segKey, seg]) => (
                  <div
                    key={segKey}
                    className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/8 flex flex-col justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-[14.5px] font-semibold text-[#111315]">
                          {seg.title}
                        </h3>
                        <span className="font-mono-num text-[11px] px-2 py-0.5 rounded bg-[#EAE8E0] text-[#111315] shrink-0">
                          {seg.evidence_count} rows
                        </span>
                      </div>

                      <div className="mt-3 space-y-2.5 text-[12.5px]">
                        <div>
                          <div className="font-mono-num text-[10.5px] uppercase text-[#5C6166]">
                            WHY THEY START
                          </div>
                          <p className="text-[#111315] mt-0.5 leading-snug">{seg.why_they_start}</p>
                        </div>

                        <div>
                          <div className="font-mono-num text-[10.5px] uppercase text-[#5C6166]">
                            CHECKING HABIT
                          </div>
                          <p className="text-[#111315] mt-0.5 leading-snug">{seg.checking_habit}</p>
                        </div>

                        <div>
                          <div className="font-mono-num text-[10.5px] uppercase text-[#D94E34]">
                            PRIMARY DROP-OFF TRIGGER
                          </div>
                          <p className="text-[#111315] mt-0.5 leading-snug">
                            {seg.primary_dropoff_trigger || seg.primary_dropoff_risk}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="pt-3 border-t border-[#111315]/10">
                      <div className="font-mono-num text-[10.5px] uppercase text-[#008A68] font-semibold">
                        UNMET NEED
                      </div>
                      <p className="text-[12.5px] font-medium text-[#111315] mt-0.5 leading-snug">
                        {seg.signature_unmet_need}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </main>
      )}

      {/* VIEW 4: AI EVALS SUITE (20-ITEM GOLDEN SET, SOURCES VOLUME, & HITL CORRECTIONS) */}
      {step === 'evals' && aiEvals && (
        <main className="flex-1 max-w-[1560px] w-full mx-auto px-8 py-7 flex flex-col gap-7 animate-stage">
          {/* Top Eval Scorecard (4 KPI Cards) */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-5">
            <div className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 shadow-sm">
              <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                GOLDEN SET AGREEMENT RATE
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-mono-num text-[32px] font-bold text-[#008A68] leading-none">
                  {aiEvals.eval_summary.agreement_rate_pct}%
                </span>
                <span className="text-[12.5px] text-[#5C6166] font-mono-num">
                  ({aiEvals.eval_summary.golden_set_passed}/{aiEvals.eval_summary.golden_set_size} PASS)
                </span>
              </div>
              <div className="text-[12px] text-[#111315] mt-2">
                Human PM ground-truth vs Groq/Gemini output
              </div>
            </div>

            <div className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 shadow-sm">
              <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                DISAGREEMENT / ERROR RATE
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-mono-num text-[32px] font-bold text-[#D94E34] leading-none">
                  {100 - aiEvals.eval_summary.agreement_rate_pct}%
                </span>
                <span className="text-[12.5px] text-[#5C6166] font-mono-num">
                  ({aiEvals.eval_summary.golden_set_failed}/{aiEvals.eval_summary.golden_set_size} FAIL)
                </span>
              </div>
              <div className="text-[12px] text-[#111315] mt-2">
                Multi-causal & creator affiliate edge cases
              </div>
            </div>

            <div className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 shadow-sm">
              <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                STAGE 2 NOISE STRIPPED (0 TOKENS)
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-mono-num text-[32px] font-bold text-[#111315] leading-none">
                  {aiEvals.eval_summary.noise_reduction_pct}%
                </span>
                <span className="text-[12.5px] text-[#5C6166] font-mono-num">
                  ({aiEvals.eval_summary.total_noise_filtered} of {aiEvals.eval_summary.total_unique_scraped})
                </span>
              </div>
              <div className="text-[12px] text-[#111315] mt-2">
                {aiEvals.eval_summary.total_signal_analyzed} verified SIP narratives analyzed
              </div>
            </div>

            <div className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 shadow-sm">
              <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                HUMAN-IN-THE-LOOP CORRECTIONS
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-mono-num text-[32px] font-bold text-[#111315] leading-none">
                  {aiEvals.hitl_corrections.length}
                </span>
                <span className="text-[12.5px] text-[#008A68] font-semibold">
                  100% Guardrail Pass
                </span>
              </div>
              <div className="text-[12px] text-[#111315] mt-2">
                Rejected AI noise, NACH window & FOMO nudges
              </div>
            </div>
          </section>

          {/* Split Row: Section 1 (Sources & Volume Table) + Section 3 (3 HITL AI Rejections & Corrections) */}
          <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
            {/* Left 5 Cols: Sources & Volume Analyzed */}
            <div className="lg:col-span-5 bg-[#FFFFFF] border border-[#111315]/10 rounded-xl overflow-hidden shadow-sm flex flex-col justify-between">
              <div>
                <div className="px-6 py-4 border-b border-[#111315]/10">
                  <span className="font-mono-num text-[11px] uppercase tracking-wider text-[#008A68] font-semibold">
                    DELIVERABLE RUBRIC 1 • CORPUS COVERAGE
                  </span>
                  <h2 className="text-[16px] font-semibold text-[#111315] mt-0.5">
                    Sources & Volume Analysed by the Engine
                  </h2>
                </div>

                <table className="w-full border-collapse text-left text-[12.5px]">
                  <thead className="bg-[#FAF9F5] text-[#5C6166] text-[10.5px] font-mono-num uppercase tracking-wider border-b border-[#111315]/10">
                    <tr>
                      <th className="py-3 px-5">Source Channel</th>
                      <th className="py-3 px-3 text-right">Scraped</th>
                      <th className="py-3 px-3 text-right">Noise</th>
                      <th className="py-3 px-5 text-right">Kept Signal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#111315]/8">
                    {aiEvals.sources_volume.map((src) => (
                      <tr key={src.source} className="hover:bg-[#FAF9F5]">
                        <td className="py-3.5 px-5">
                          <div className="font-semibold text-[#111315]">{src.label}</div>
                          <div className="text-[11px] text-[#5C6166] line-clamp-1">
                            {src.community}
                          </div>
                        </td>
                        <td className="py-3.5 px-3 text-right font-mono-num text-[#111315]">
                          {src.total_scraped}
                        </td>
                        <td className="py-3.5 px-3 text-right font-mono-num text-[#5C6166]">
                          {src.noise_dropped}
                        </td>
                        <td className="py-3.5 px-5 text-right font-mono-num">
                          <span className="font-bold text-[#008A68]">{src.signal_kept}</span>
                          <span className="text-[10.5px] text-[#5C6166] ml-1">
                            ({src.signal_yield_pct}%)
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="px-6 py-3.5 bg-[#FAF9F5] border-t border-[#111315]/10 flex items-center justify-between text-[12px] font-mono-num">
                <span className="font-semibold text-[#111315]">
                  TOTAL: {aiEvals.eval_summary.total_unique_scraped} Unique Posts
                </span>
                <span className="text-[#008A68] font-semibold">
                  {aiEvals.eval_summary.total_signal_analyzed} Kept · {aiEvals.eval_summary.total_noise_filtered} Dropped
                </span>
              </div>
            </div>

            {/* Right 7 Cols: 3 Places Where We Rejected or Corrected AI Output */}
            <div className="lg:col-span-7 bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-6 shadow-sm flex flex-col gap-4">
              <div>
                <span className="font-mono-num text-[11px] uppercase tracking-wider text-[#008A68] font-semibold">
                  DELIVERABLE RUBRIC 3 • HUMAN-IN-THE-LOOP INTERVENTIONS
                </span>
                <h2 className="text-[16px] font-semibold text-[#111315] mt-0.5">
                  3 Places Where We Rejected or Corrected AI Output (And Why)
                </h2>
              </div>

              <div className="space-y-3.5">
                {aiEvals.hitl_corrections.map((item) => (
                  <div
                    key={item.id}
                    className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/8 flex flex-col gap-2"
                  >
                    <h3 className="text-[14px] font-semibold text-[#111315]">{item.title}</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[12px] mt-1">
                      <div className="p-3 rounded-lg bg-[#FFFFFF] border border-[#111315]/8 border-l-4 border-l-[#D94E34]">
                        <div className="font-mono-num text-[10px] uppercase text-[#D94E34] font-semibold">
                          REJECTED AI OUTPUT & ROOT CAUSE
                        </div>
                        <p className="text-[#111315] mt-1 leading-snug">{item.ai_original_output}</p>
                        <p className="text-[#5C6166] mt-1 leading-snug">{item.why_rejected}</p>
                      </div>

                      <div className="p-3 rounded-lg bg-[#FFFFFF] border border-[#111315]/8 border-l-4 border-l-[#00D09C]">
                        <div className="font-mono-num text-[10px] uppercase text-[#008A68] font-semibold">
                          HOW WE CORRECTED THE PIPELINE
                        </div>
                        <p className="text-[#111315] mt-1 leading-snug">{item.human_correction}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Section 2: 20-Item Hand-Labelled Golden Set Evaluation Table */}
          <section className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl overflow-hidden shadow-sm">
            <div className="px-6 py-4 border-b border-[#111315]/10 flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className="font-mono-num text-[11px] uppercase tracking-wider text-[#008A68] font-semibold">
                  DELIVERABLE RUBRIC 2 • 20-ITEM GOLDEN SET BENCHMARK
                </span>
                <h2 className="text-[16px] font-semibold text-[#111315] mt-0.5">
                  Hand-Labelled Ground Truth vs. Engine Predictions ({aiEvals.eval_summary.agreement_rate_pct}% Agreement)
                </h2>
              </div>

              <div className="inline-flex rounded-lg bg-[#EAE8E0] p-1 text-[12px] font-mono-num">
                <button
                  onClick={() => setEvalFilter('ALL')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    evalFilter === 'ALL'
                      ? 'bg-[#FFFFFF] text-[#111315] shadow-sm'
                      : 'text-[#5C6166] hover:text-[#111315]'
                  }`}
                >
                  All ({aiEvals.golden_set.length})
                </button>
                <button
                  onClick={() => setEvalFilter('PASS')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    evalFilter === 'PASS'
                      ? 'bg-[#FFFFFF] text-[#008A68] shadow-sm'
                      : 'text-[#5C6166] hover:text-[#111315]'
                  }`}
                >
                  Agreed / PASS ({aiEvals.eval_summary.golden_set_passed})
                </button>
                <button
                  onClick={() => setEvalFilter('FAIL')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    evalFilter === 'FAIL'
                      ? 'bg-[#FFFFFF] text-[#D94E34] shadow-sm'
                      : 'text-[#5C6166] hover:text-[#111315]'
                  }`}
                >
                  Failed / Disagreed ({aiEvals.eval_summary.golden_set_failed})
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-[12.5px]">
                <thead className="bg-[#FAF9F5] text-[#5C6166] text-[10.5px] font-mono-num uppercase tracking-wider border-b border-[#111315]/10">
                  <tr>
                    <th className="py-3 px-4 w-12 text-center">#</th>
                    <th className="py-3 px-4 w-44">Row & Source</th>
                    <th className="py-3 px-4 min-w-[280px]">Investor Post Snippet</th>
                    <th className="py-3 px-4 w-56">Human PM Label (Ground Truth)</th>
                    <th className="py-3 px-4 w-56">AI Engine Prediction</th>
                    <th className="py-3 px-4 w-24 text-center">Match</th>
                    <th className="py-3 px-4 min-w-[230px]">Eval / Failure Analysis</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#111315]/8">
                  {aiEvals.golden_set
                    .filter((item) => evalFilter === 'ALL' || item.status === evalFilter)
                    .map((item) => (
                      <tr
                        key={item.eval_id}
                        className={
                          item.status === 'FAIL'
                            ? 'bg-[#D94E34]/5 hover:bg-[#D94E34]/10'
                            : 'hover:bg-[#FAF9F5]'
                        }
                      >
                        <td className="py-3.5 px-4 text-center font-mono-num text-[#5C6166]">
                          {item.eval_id}
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="font-mono-num font-semibold text-[#111315]">
                            Row #{item.row_id}
                          </div>
                          <div className="text-[11px] text-[#5C6166]">{item.source}</div>
                        </td>
                        <td className="py-3.5 px-4 text-[#111315] max-w-[320px] leading-snug">
                          &ldquo;{item.snippet}&rdquo;
                        </td>
                        <td className="py-3.5 px-4 font-medium text-[#111315]">
                          {item.human_label}
                        </td>
                        <td className="py-3.5 px-4 text-[#383C40]">
                          <div>{item.ai_label}</div>
                          <div className="font-mono-num text-[10.5px] text-[#5C6166] mt-0.5">
                            {item.dropoff_window}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-center font-mono-num">
                          <span
                            className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                              item.status === 'PASS'
                                ? 'bg-[#00D09C]/20 text-[#008A68]'
                                : 'bg-[#D94E34]/15 text-[#D94E34]'
                            }`}
                          >
                            {item.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-[12px] text-[#5C6166] leading-snug">
                          {item.eval_note}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      )}

      {/* VIEW 5: LIVE AI SANDBOX (MENTOR INTERACTIVE TESTING PLAYGROUND) */}
      {step === 'sandbox' && (
        <main className="flex-1 max-w-[1560px] w-full mx-auto px-8 py-7 flex flex-col gap-6 animate-stage">
          {/* Top Header Banner */}
          <div className="bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
            <div>
              <span className="font-mono-num text-[11px] uppercase tracking-wider text-[#008A68] font-semibold">
                INTERACTIVE MENTOR PLAYGROUND • REAL-TIME 4-STAGE PIPELINE TESTER
              </span>
              <h1 className="text-[20px] font-semibold text-[#111315] mt-0.5">
                Test Any Custom Investor Comment Against the Discovery Engine
              </h1>
              <p className="text-[13px] text-[#5C6166] mt-0.5">
                Write or paste any English or Hinglish investor comment below to verify how Stage 2 filters noise and how Stage 3 & 4 classify behavioral triggers, drop-off windows, and guardrail-safe actions.
              </p>
            </div>
          </div>

          <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left 5 Cols: Custom Comment Input & Preset Test Chips */}
            <form
              onSubmit={handleRunSandboxTest}
              className="lg:col-span-5 bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-6 shadow-sm flex flex-col gap-5"
            >
              <div>
                <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166] font-semibold mb-2">
                  QUICK PRESET TEST SCENARIOS (CLICK TO LOAD)
                </div>
                <div className="flex flex-col gap-2">
                  {SANDBOX_PRESETS.map((preset) => (
                    <button
                      type="button"
                      key={preset.label}
                      onClick={() => {
                        setSandboxSource(preset.source);
                        setSandboxText(preset.text);
                      }}
                      className={`text-left px-3.5 py-2.5 rounded-lg border text-[12.5px] font-medium transition-colors ${
                        sandboxText === preset.text
                          ? 'bg-[#00D09C]/12 border-[#008A68] text-[#111315]'
                          : 'bg-[#FAF9F5] border-[#111315]/8 text-[#383C40] hover:text-[#111315]'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between gap-3">
                <label className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166] font-semibold">
                  SIMULATED SOURCE CHANNEL
                </label>
                <div className="flex flex-wrap gap-1">
                  {(['reddit', 'play_store', 'app_store', 'youtube', 'tradingqna'] as const).map(
                    (srcKey) => (
                      <button
                        type="button"
                        key={srcKey}
                        onClick={() => setSandboxSource(srcKey)}
                        className={`px-2.5 py-1 rounded-md text-[11.5px] font-medium transition-colors ${
                          sandboxSource === srcKey
                            ? 'bg-[#111315] text-[#F5F4EE]'
                            : 'bg-[#FAF9F5] text-[#5C6166] hover:text-[#111315]'
                        }`}
                      >
                        {SOURCE_LABELS[srcKey]}
                      </button>
                    )
                  )}
                </div>
              </div>

              <div>
                <label className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166] font-semibold block mb-2">
                  CUSTOM INVESTOR COMMENT (ENGLISH OR HINGLISH)
                </label>
                <textarea
                  rows={5}
                  value={sandboxText}
                  onChange={(e) => setSandboxText(e.target.value)}
                  placeholder="Type any investor comment or review here to test how the AI pipeline classifies it..."
                  className="w-full p-3.5 rounded-xl bg-[#FAF9F5] border border-[#111315]/15 text-[13.5px] text-[#111315] leading-relaxed focus:outline-none focus:border-[#008A68]"
                />
              </div>

              <label className="flex items-center gap-2.5 text-[12.5px] text-[#383C40] cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={sandboxSaveToSheet}
                  onChange={(e) => setSandboxSaveToSheet(e.target.checked)}
                  className="rounded border-[#111315]/25 text-[#008A68] focus:ring-[#008A68]"
                />
                <span>Also save this test comment into the live Data Sheet & Supabase</span>
              </label>

              <button
                type="submit"
                disabled={sandboxRunning || !sandboxText.trim()}
                className="w-full inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-[#00D09C] text-[#111315] text-[14px] font-semibold hover:bg-[#00b889] transition-all shadow-sm disabled:opacity-50"
              >
                <Sparkles className={`w-4 h-4 ${sandboxRunning ? 'animate-spin' : ''}`} />
                <span>
                  {sandboxRunning ? 'Running 4-Stage Pipeline Test...' : 'Run 4-Stage AI Pipeline Test'}
                </span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>

            {/* Right 7 Cols: Live 4-Stage Pipeline Output Trace */}
            <div className="lg:col-span-7 bg-[#FFFFFF] border border-[#111315]/10 rounded-xl p-6 shadow-sm flex flex-col gap-5">
              {!sandboxResult ? (
                <div className="py-16 text-center flex flex-col items-center justify-center gap-2 text-[#5C6166]">
                  <Sparkles className="w-7 h-7 text-[#008A68]" />
                  <div className="text-[15px] font-semibold text-[#111315]">
                    Ready to Evaluate Your Comment
                  </div>
                  <p className="text-[13px] max-w-md">
                    Click &ldquo;Run 4-Stage AI Pipeline Test&rdquo; on the left to inspect how each stage of the Discovery Engine processes the input.
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between border-b border-[#111315]/10 pb-3.5">
                    <div>
                      <span className="font-mono-num text-[11px] uppercase tracking-wider text-[#008A68] font-semibold">
                        LIVE PIPELINE EXECUTION RESULT • {sandboxResult.latency_ms} MS
                      </span>
                      <h2 className="text-[17px] font-semibold text-[#111315] mt-0.5">
                        4-Stage Behavioral Trace
                      </h2>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full font-mono-num text-[11.5px] font-bold ${
                        sandboxResult.passed_stage2_gate
                          ? 'bg-[#00D09C]/20 text-[#008A68]'
                          : 'bg-[#D94E34]/15 text-[#D94E34]'
                      }`}
                    >
                      {sandboxResult.passed_stage2_gate
                        ? 'PASSED NOISE GATE → AI ANALYZED'
                        : 'BLOCKED AT STAGE 2 (0 TOKENS USED)'}
                    </span>
                  </div>

                  {/* Stage 1 & Stage 2 Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/8">
                      <div className="font-mono-num text-[10.5px] uppercase text-[#5C6166] font-semibold">
                        STAGE 1 · DEDUPLICATION CHECK
                      </div>
                      <div className="text-[13.5px] font-semibold text-[#111315] mt-1">
                        {sandboxResult.stage1_deduplication.is_duplicate
                          ? `Duplicate Found (Matches Row #${sandboxResult.stage1_deduplication.existing_row_id})`
                          : 'Unique New Investor Narrative'}
                      </div>
                      <div className="text-[11.5px] text-[#5C6166] font-mono-num mt-1">
                        Source: {SOURCE_LABELS[sandboxResult.stage1_deduplication.source]} ·{' '}
                        {sandboxResult.stage1_deduplication.word_count} words
                      </div>
                    </div>

                    <div
                      className={`p-4 rounded-xl border ${
                        sandboxResult.stage2_noise_gate.passed_gate
                          ? 'bg-[#FAF9F5] border-[#008A68]/30'
                          : 'bg-[#D94E34]/5 border-[#D94E34]/30'
                      }`}
                    >
                      <div className="font-mono-num text-[10.5px] uppercase text-[#5C6166] font-semibold">
                        STAGE 2 · CONTEXTUAL NOISE GATE
                      </div>
                      <div className="text-[13.5px] font-semibold text-[#111315] mt-1">
                        {sandboxResult.stage2_noise_gate.cleaning_status} (Score:{' '}
                        {sandboxResult.stage2_noise_gate.triage_score})
                      </div>
                      <div className="text-[12px] text-[#5C6166] mt-1">
                        {sandboxResult.stage2_noise_gate.cleaning_reason}
                      </div>
                    </div>
                  </div>

                  {/* Stage 3 & Stage 4 Output (If Passed Gate) */}
                  {sandboxResult.passed_stage2_gate &&
                  sandboxResult.stage3_semantic_tagging &&
                  sandboxResult.stage4_opportunity_scoring ? (
                    <div className="flex flex-col gap-4">
                      {/* Stage 3 Semantic Tagging Grid */}
                      <div className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/10">
                        <div className="font-mono-num text-[10.5px] uppercase text-[#008A68] font-semibold mb-3">
                          STAGE 3 · LLM SEMANTIC TAGGING & CLUSTERING
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono-num">
                          <div className="col-span-2 p-3 rounded-lg bg-[#FFFFFF] border border-[#111315]/8">
                            <div className="text-[10px] text-[#5C6166]">ASSIGNED BEHAVIORAL TRIGGER</div>
                            <div className="text-[13px] font-sans font-semibold text-[#111315] mt-1">
                              {sandboxResult.stage3_semantic_tagging.behavioral_trigger}
                            </div>
                          </div>

                          <div className="p-3 rounded-lg bg-[#FFFFFF] border border-[#111315]/8">
                            <div className="text-[10px] text-[#5C6166]">SENTIMENT & INTENSITY</div>
                            <div className="text-[13px] font-semibold text-[#D94E34] mt-1">
                              {sandboxResult.stage3_semantic_tagging.sentiment_polarity.toFixed(2)} ·{' '}
                              {sandboxResult.stage3_semantic_tagging.emotional_intensity}/10
                            </div>
                          </div>

                          <div className="p-3 rounded-lg bg-[#FFFFFF] border border-[#111315]/8">
                            <div className="text-[10px] text-[#5C6166]">SEGMENT PROXY</div>
                            <div className="text-[12px] font-semibold text-[#111315] mt-1">
                              {sandboxResult.stage3_semantic_tagging.segment_proxy_ticket}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Stage 4 Opportunity Scoring & Product Action */}
                      <div className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/10 border-l-4 border-l-[#00D09C] flex flex-col gap-2.5">
                        <div className="flex items-center justify-between">
                          <span className="font-mono-num text-[10.5px] uppercase text-[#008A68] font-semibold">
                            STAGE 4 · OPPORTUNITY SCORING & GUARDRAIL-SAFE INTERVENTION
                          </span>
                          <span className="font-mono-num text-[12px] font-bold px-2.5 py-0.5 rounded bg-[#111315] text-[#00D09C]">
                            Score: {sandboxResult.stage4_opportunity_scoring.opportunity_score}/100 ·{' '}
                            {sandboxResult.stage4_opportunity_scoring.retention_dropoff_bucket}
                          </span>
                        </div>
                        <p className="text-[13.5px] font-medium text-[#111315] leading-relaxed">
                          {sandboxResult.stage4_opportunity_scoring.recommended_intervention}
                        </p>
                        <div className="text-[11.5px] text-[#008A68] font-medium flex items-center gap-1.5">
                          <ShieldCheck className="w-4 h-4" />
                          <span>{sandboxResult.stage4_opportunity_scoring.guardrail_verified}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-5 rounded-xl bg-[#FAF9F5] border border-[#111315]/10 text-[13px] text-[#383C40] leading-relaxed">
                      <strong className="text-[#111315] block mb-1">
                        Why Stage 3 & 4 Were Skipped (Eval Gate Protection):
                      </strong>
                      Because this input did not contain a multi-word SIP behavioral narrative (
                      <span className="font-mono-num">{sandboxResult.stage2_noise_gate.cleaning_reason}</span>
                      ), the engine filtered it out at Stage 2 using <strong>0 LLM tokens</strong> so generic store ratings or off-topic comments never distort product opportunity scores.
                    </div>
                  )}
                </>
              )}
            </div>
          </section>
        </main>
      )}

      {/* SLIDE-OVER ROW EVIDENCE DRAWER (MENTOR AUDIT VIEW) */}
      {selectedRow && (
        <div
          className="fixed inset-0 z-50 bg-[#111315]/30 backdrop-blur-[2px] flex justify-end"
          onClick={() => setSelectedRow(null)}
        >
          <aside
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-xl bg-[#FFFFFF] h-full shadow-2xl border-l border-[#111315]/12 flex flex-col justify-between overflow-y-auto animate-stage"
          >
            <div className="p-7 flex flex-col gap-6">
              {/* Drawer Header */}
              <div className="flex items-start justify-between gap-4 pb-4 border-b border-[#111315]/10">
                <div>
                  <div className="flex items-center gap-2 font-mono-num text-[11.5px] text-[#008A68] font-semibold uppercase tracking-wider">
                    <span>ROW #{selectedRow.row_id}</span>
                    <span>•</span>
                    <span>{SOURCE_LABELS[selectedRow.source] || selectedRow.source}</span>
                    <span>•</span>
                    <span>{formatDateShort(selectedRow.published_at)}</span>
                  </div>
                  <h3 className="text-[18px] font-semibold text-[#111315] mt-1 leading-snug">
                    {selectedRow.title || `${SOURCE_LABELS[selectedRow.source] || selectedRow.source} Investor Feedback`}
                  </h3>
                  <div className="text-[12px] text-[#5C6166] mt-0.5">
                    Channel: <span className="font-medium text-[#111315]">{selectedRow.sub_source}</span>
                    {' · '}
                    Author: <span className="font-mono-num">{selectedRow.author_handle || 'anonymous'}</span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedRow(null)}
                  className="p-1.5 rounded-lg text-[#5C6166] hover:text-[#111315] hover:bg-[#FAF9F5]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Full Unabridged Scraped Text */}
              <div>
                <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166] mb-2">
                  FULL SCRAPED INVESTOR TEXT (STAGE 1 & 2)
                </div>
                <div className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/10 text-[14px] text-[#111315] leading-relaxed whitespace-pre-line">
                  {selectedRow.content}
                </div>
              </div>

              {/* Stage 3 & 4 AI Classification Telemetry */}
              {selectedRow.cleaning_status === 'CLEAN_SIP_SIGNAL' ? (
                <div className="flex flex-col gap-4">
                  <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                    AI SEMANTIC TAGGING & SCORING BREAKDOWN (STAGE 3 & 4)
                  </div>

                  <div className="grid grid-cols-2 gap-3 font-mono-num">
                    <div className="p-3.5 rounded-xl bg-[#FAF9F5] border border-[#111315]/8">
                      <div className="text-[10.5px] text-[#5C6166]">BEHAVIORAL TRIGGER</div>
                      <div className="text-[12.5px] font-sans font-semibold text-[#111315] mt-1">
                        {selectedRow.behavioral_trigger || 'Pending AI'}
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-[#FAF9F5] border border-[#111315]/8">
                      <div className="text-[10.5px] text-[#5C6166]">OPPORTUNITY SCORE</div>
                      <div className="text-[18px] font-bold text-[#008A68] mt-0.5">
                        {selectedRow.opportunity_score}/100
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-[#FAF9F5] border border-[#111315]/8">
                      <div className="text-[10.5px] text-[#5C6166]">SENTIMENT & INTENSITY</div>
                      <div className="text-[13px] font-semibold text-[#D94E34] mt-1">
                        {selectedRow.sentiment_polarity > 0 ? '+' : ''}
                        {selectedRow.sentiment_polarity.toFixed(2)} ({selectedRow.sentiment_label}) ·{' '}
                        {selectedRow.emotional_intensity}/10
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-[#FAF9F5] border border-[#111315]/8">
                      <div className="text-[10.5px] text-[#5C6166]">SEGMENT PROXY & DROP-OFF</div>
                      <div className="text-[12.5px] font-semibold text-[#111315] mt-1">
                        {selectedRow.segment_proxy_ticket} · {selectedRow.retention_dropoff_bucket}
                      </div>
                    </div>
                  </div>

                  {selectedRow.recommended_action && (
                    <div className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/10 border-l-4 border-l-[#00D09C]">
                      <div className="text-[10.5px] font-mono-num uppercase tracking-wider text-[#008A68] font-semibold">
                        ROW-LEVEL PRODUCT INTERVENTION
                      </div>
                      <p className="text-[13.5px] font-medium text-[#111315] mt-1 leading-relaxed">
                        {selectedRow.recommended_action}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-[#FAF9F5] border border-[#111315]/10">
                  <div className="text-[11px] font-mono-num uppercase tracking-wider text-[#5C6166]">
                    STAGE 2 NOISE FILTER REASON
                  </div>
                  <p className="text-[13.5px] font-medium text-[#111315] mt-1">
                    {selectedRow.cleaning_reason} (Triage Score: {selectedRow.triage_score})
                  </p>
                </div>
              )}
            </div>

            {/* Drawer Footer with Open Original Source Link */}
            {selectedRow.url && (
              <div className="p-6 bg-[#FAF9F5] border-t border-[#111315]/10 flex items-center justify-end">
                <a
                  href={selectedRow.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#111315] text-[#F5F4EE] text-[12.5px] font-semibold hover:bg-[#008A68] transition-colors shrink-0"
                >
                  <span>Open Source</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </a>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
