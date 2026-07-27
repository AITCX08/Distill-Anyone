export type JobStatus = "queued" | "running" | "pause_requested" | "paused" | "partial" | "completed" | "failed";
export interface JobSummary { job_id: string; status: JobStatus; revision: number; platform: string; creator_name: string; total_items: number; completed_items: number; failed_items: number; unsupported_items: number; updated_at: string; }
export interface JobItem { source_id: string; processing_status: string; retryable: boolean; stage_progress: number; overall_progress: number; last_error: string | null; updated_at: string; }
export interface DashboardEvent { eventType: "snapshot" | "job.updated" | "item.updated" | "trace.appended"; data: Record<string, unknown>; }
