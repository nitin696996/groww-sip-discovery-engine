export interface SheetRow {
  row_id: number;
  external_id: string;
  content_hash: string;
  source: string;
  sub_source: string;
  author_handle: string;
  title: string;
  content: string;
  url: string;
  rating: number | null;
  upvotes: number;
  published_at: string;
  ingested_at: string;
  triage_score: number;
  triage_status: string;
  cleaning_status: 'CLEAN_SIP_SIGNAL' | 'FILTERED_SPAM_PROMO' | 'FILTERED_NON_SIP' | string;
  cleaning_reason: string;
  processed_by_llm: number;
  behavioral_trigger: string;
  sentiment_polarity: number;
  sentiment_label: string;
  emotional_intensity: number;
  segment_proxy_ticket: string;
  segment_proxy_tenure: string;
  retention_dropoff_bucket: string;
  opportunity_score: number;
  recommended_action: string;
  verbatim_quote: string;
  extracted_by_provider: string;
  analyzed_at: string;
}

export interface TriggerClusterSummary {
  id: string;
  trigger_name: string;
  short_label: string;
  description: string;
  row_count: number;
  frequency_pct: number;
  avg_sentiment_polarity: number;
  avg_emotional_intensity: number;
  dominant_ticket_proxy: string;
  dominant_tenure_proxy: string;
  opportunity_score: number;
  dropoff_correlation_weight: number;
  retention_dropoff_distribution: {
    months_1_to_3_pct: number;
    months_6_to_8_pct: number;
    months_10_to_12_pct: number;
  };
  recommended_intervention: string;
  sample_rows: SheetRow[];
}

export interface RetentionCohortSummary {
  window: string;
  label: string;
  row_count: number;
  share_pct: number;
  primary_driver: string;
}

export interface PipelineWorkspaceResponse {
  pipeline_stages: {
    stage1_ingested_total: number;
    stage2_cleaned_sip_rows: number;
    stage2_removed_spam_promo: number;
    stage2_removed_non_sip: number;
    stage2_total_removed: number;
    stage3_ai_tagged_rows: number;
    stage4_opportunities_scored: number;
  };
  supabase_storage: {
    configured: boolean;
    mode: string;
    table: string;
    status: string;
    last_synced_rows: number;
    keys_exposed_to_frontend: boolean;
  };
  sheet_rows: SheetRow[];
  trigger_clusters: TriggerClusterSummary[];
  retention_dropoff_cohort_summary: RetentionCohortSummary[];
}

export interface Archetype {
  label: string;
  share_pct: number;
  description: string;
}

export interface ResearchQuestionEvidence {
  document_id: number;
  source: string;
  sub_source: string;
  author_handle: string;
  title: string;
  verbatim_quote: string;
  extracted_finding: string;
  sip_journey_stage: string;
  emotional_state: string;
}

export interface ResearchQuestion {
  id: string;
  number: number;
  question: string;
  field: string;
  headline_finding: string;
  dominant_archetypes: Archetype[];
  product_implication: string;
  evidence_count: number;
  evidence_items: ResearchQuestionEvidence[];
}

export interface SegmentDetail {
  title: string;
  why_they_start: string;
  checking_habit: string;
  primary_dropoff_trigger?: string;
  primary_dropoff_risk?: string;
  signature_unmet_need: string;
  evidence_count: number;
  sample_quotes: {
    document_id: number;
    source: string;
    sub_source: string;
    verbatim_quote: string;
  }[];
}

export interface SegmentDimension {
  label: string;
  segments: Record<string, SegmentDetail>;
}

export interface EvalSourceVolume {
  source: string;
  label: string;
  community: string;
  total_scraped: number;
  noise_dropped: number;
  signal_kept: number;
  signal_yield_pct: number;
}

export interface GoldenSetEvalItem {
  eval_id: number;
  row_id: number;
  source: string;
  snippet: string;
  human_label: string;
  ai_label: string;
  dropoff_window: string;
  model_used: string;
  status: 'PASS' | 'FAIL';
  eval_note: string;
}

export interface HitlCorrectionItem {
  id: string;
  title: string;
  ai_original_output: string;
  why_rejected: string;
  human_correction: string;
}

export interface AiEvalsResponse {
  eval_summary: {
    total_unique_scraped: number;
    total_noise_filtered: number;
    total_signal_analyzed: number;
    noise_reduction_pct: number;
    golden_set_size: number;
    golden_set_passed: number;
    golden_set_failed: number;
    agreement_rate_pct: number;
    guardrail_compliance_pct: number;
  };
  sources_volume: EvalSourceVolume[];
  golden_set: GoldenSetEvalItem[];
  hitl_corrections: HitlCorrectionItem[];
}

export interface SandboxTestResponse {
  passed_stage2_gate: boolean;
  latency_ms: number;
  saved_row_id: number | null;
  stage1_deduplication: {
    content_hash: string;
    is_duplicate: boolean;
    existing_row_id: number | null;
    source: string;
    word_count: number;
  };
  stage2_noise_gate: {
    passed_gate: boolean;
    triage_score: number;
    triage_status: string;
    cleaning_status: string;
    cleaning_reason: string;
    matched_dimensions: string[];
  };
  stage3_semantic_tagging: {
    behavioral_trigger: string;
    short_label: string;
    sentiment_polarity: number;
    sentiment_label: string;
    emotional_intensity: number;
    segment_proxy_ticket: string;
    segment_proxy_tenure: string;
    sip_journey_stage: string;
    question_tags: string[];
    verbatim_quote: string;
  } | null;
  stage4_opportunity_scoring: {
    retention_dropoff_bucket: string;
    opportunity_score: number;
    evidence_backed_finding: string;
    recommended_intervention: string;
    what_needs_validation: string;
    guardrail_verified: string;
  } | null;
}


