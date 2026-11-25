export type Role = "EMPLOYEE" | "HR";

export interface Me {
  id: string;
  email: string;
  role: Role;
  organization_id: string;
  team_id: string | null;
}

export interface CheckIn {
  id: string;
  status: "DRAFT" | "SUBMITTED";
  connectedness: number | null;
  support: number | null;
  workload: number | null;
  score: number | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
}

export interface CurrentCheckIns {
  draft: CheckIn | null;
  latest_submitted: CheckIn | null;
}

export interface DraftInput {
  connectedness?: number;
  support?: number;
  workload?: number;
}

export interface Team {
  id: string;
  name: string;
}

export interface Wellbeing {
  reporting_month: string;
  team_id: string | null;
  respondent_count: number;
  eligible_count: number;
  participation_rate: number | null;
  average_score: number | null;
  suppressed: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}
