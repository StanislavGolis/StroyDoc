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

export interface Section {
  id: number;
  object_id: number;
  code: string;
  name: string | null;
  sort_order: number;
  created_at: string;
}

export interface ObjectFile {
  id: number;
  object_id: number;
  kind: DocKind;
  section: { id: number; code: string; name: string | null } | null;
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

export type ItemType = "material" | "equipment" | "work";

/** Ключи документов матрицы закрытия (см. backend/app/services/closure.py) */
export type ClosureDocKey = "passport" | "avk" | "aosr" | "vso" | "vr";

export interface SourceItem {
  id: number;
  object_id: number;
  source_file_id: number | null;
  source: "rd" | "estimate";
  /** Тип позиции; null — не определён (требуется классификация) */
  item_type: ItemType | null;
  /** Документы, требуемые для позиции по матрице закрытия */
  required_docs: ClosureDocKey[];
  section: { id: number; code: string; name: string | null } | null;
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
  full_code: string | null;
  page_number: number | null;
  tracked: boolean;
  docs_count: number;
  act_avk: number;
  act_aosr: number;
  act_vso: number;
  act_vr: number;
}

export interface IncomingDoc {
  id: number;
  object_id: number;
  doc_number: string | null;
  doc_title: string | null;
  doc_date: string | null;
  file_id: number | null;
  original_filename: string | null;
  size_bytes: number | null;
  linked_items: number;
  created_at: string;
}

export type ActType = "avk" | "aosr" | "vso" | "vr";

export interface Act {
  id: number;
  object_id: number;
  act_type: ActType;
  doc_number: string | null;
  doc_date: string | null;
  status: "draft" | "ready";
  linked_items: number;
  created_at: string;
}

export interface ObjectDashItem {
  object_id: number;
  name: string;
  code: string | null;
  status: string;
  tracked_items: number;
  items_with_docs: number;
  items_without_docs: number;
  ready_pct: number;
  acts_total: number;
  work_total: number;
  vr_closed: number;
  non_work_total: number;
  avk_closed: number;
  aosr_closed: number;
  vso_closed: number;
  material_total: number;
  equipment_total: number;
  /** Позиции без определённого типа — требуется классификация */
  untyped_total: number;
}

export interface DashboardSummary {
  objects: ObjectDashItem[];
  totals: {
    objects_total: number;
    objects_active: number;
    tracked_items: number;
    items_with_docs: number;
    items_without_docs: number;
    ready_pct: number;
    acts_total: number;
    acts_by_type: Record<string, number>;
    passports: number;
  };
}

