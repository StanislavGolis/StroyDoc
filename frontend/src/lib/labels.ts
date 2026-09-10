import type { ItemType } from "./types";

export const ROLE_LABELS: Record<string, string> = {
  admin: "Администратор",
  pto_head: "Руководитель ПТО",
  pto_engineer: "Инженер ПТО",
};

export const STATUS_LABELS: Record<string, string> = {
  planning: "Планируется",
  active: "В работе",
  closed: "Закрыт",
};

export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU");
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
}

export const STATUS_COLORS: Record<string, string> = {
  planning: "default",
  active: "processing",
  closed: "success",
};

/** Подписи типа позиции (матрица закрытия: материал / оборудование / работа) */
export const ITEM_TYPE_LABELS: Record<ItemType, string> = {
  material: "материал",
  equipment: "оборудование",
  work: "работа",
};

export const ITEM_TYPE_COLORS: Record<ItemType, string> = {
  material: "geekblue",
  equipment: "purple",
  work: "gold",
};

/** Подписи колонок закрывающих документов */
export const CLOSURE_DOC_LABELS: Record<string, string> = {
  passport: "Паспорт/Сертификат",
  avk: "АВК",
  aosr: "АОСР",
  vso: "ВСО",
  vr: "ВР",
};
