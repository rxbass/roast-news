// Backend returns snake_case JSON; these types mirror it exactly (no mapping layer).

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
