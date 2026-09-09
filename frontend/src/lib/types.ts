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

export type DocKind = "spec" | "estimate" | "passport" | "other";

export type ParseStatusType = "uploaded" | "parsing" | "done" | "error";

export interface ObjectFile {
  id: number;
  object_id: number;
  kind: DocKind;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  status: ParseStatusType;
  error_message: string | null;
  parsed_items: number;
  created_at: string;
  uploader: { id: number; full_name: string; email: string } | null;
}

export interface SourceItem {
  id: number;
  object_id: number;
  source_file_id: number | null;
  source: "rd" | "estimate";
  row_number: number;
  position: string | null;
  name: string;
  mark: string | null;
  doc_ref: string | null;
  product_code: string | null;
  supplier: string | null;
  unit: string | null;
  quantity: number | string | null;
  mass: string | null;
  notes: string | null;
}

