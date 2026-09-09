"use client";

import { Tag } from "antd";

export type StatusTone = "done" | "warn" | "danger" | "muted" | "info";

/** Единый бейдж статуса по палитре DESIGN.md */
export function StatusBadge({
  tone,
  children,
  title,
}: {
  tone: StatusTone;
  children: React.ReactNode;
  title?: string;
}) {
  const cls: Record<StatusTone, string> = {
    done: "status-done",
    warn: "status-warn",
    danger: "status-danger",
    muted: "status-muted",
    info: "status-info",
  };
  return (
    <Tag className={cls[tone]} title={title}>
      {children}
    </Tag>
  );
}
