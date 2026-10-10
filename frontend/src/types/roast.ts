// Backend returns snake_case JSON; these types mirror it exactly (no mapping layer).

export type SpiceLevel = 'mild' | 'medium' | 'extra_spicy';

export type RoastStatus = 'completed' | 'refused' | 'failed';

export interface Roast {
  id: string;
  source_url: string;
  source_domain: string;
  article_title: string;
  spice_level: SpiceLevel;
  roast_text: string | null;
  status: RoastStatus;
  refusal_reason: string | null;
  message: string | null;
  cached: boolean;
  created_at: string;
}

export interface RoastCreate {
  url: string;
  spice_level: SpiceLevel;
}

export interface RoastList {
  items: Roast[];
  total: number;
  page: number;
  size: number;
}
