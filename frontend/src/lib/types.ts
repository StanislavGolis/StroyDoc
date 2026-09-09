export type Role = "admin" | "pto_head" | "pto_engineer";

export type ObjectStatus = "planning" | "active" | "closed";

export interface User {
  id: number;
  company_id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface ConstructionObject {
  id: number;
  company_id: number;
  name: string;
  code: string | null;
  start_date: string | null;
  end_date: string | null;
  status: ObjectStatus;
  created_at: string;
}

export interface Assignment {
  id: number;
  object_id: number;
  created_at: string;
  user: {
    id: number;
    full_name: string;
    email: string;
    role: string;
  };
}

export interface CreatedUserResponse {
  user: User;
  generated_password: string;
}

export interface ResetPasswordResponse {
  user: User;
  generated_password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}
