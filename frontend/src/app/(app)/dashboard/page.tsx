"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { App as AntApp, Button, Card, Progress, Space, Spin, Tag, Typography } from "antd";
import { ApartmentOutlined } from "@ant-design/icons";
import { dashboardApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { STATUS_LABELS } from "@/lib/labels";
import type { DashboardSummary, ObjectDashItem } from "@/lib/types";

const GAP = 14;
const CARD_W = 360;
const CARD_H = 238;
const CELL_W = CARD_W + GAP;
const CELL_H = CARD_H + GAP;
const STORE_KEY = "sd-dash-grid";

type Pos = { c: number; r: number };

function clampCell(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

export default function DashboardPage() {
  const { loading, isManager } = useAuth();
  const { message } = AntApp.useApp();
  const router = useRouter();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [cols, setCols] = useState(3);
  const [layout, setLayout] = useState<Record<number, Pos>>({});
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const drag = useRef<{
    id: number;
    startX: number;
    startY: number;
    base: Pos;
    cols: number;
  } | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!isManager) {
      router.replace("/objects");
      return;
    }
    dashboardApi
      .summary()
      .then((d) => {
        setData(d);
        try {
          const raw = JSON.parse(localStorage.getItem(STORE_KEY) ?? "{}") as Record<string, Pos>;
          const next: Record<number, Pos> = {};
          for (const key of Object.keys(raw)) {
            const v = raw[key];
            if (v && Number.isFinite(v.c) && Number.isFinite(v.r) && v.c >= 0 && v.r >= 0) {
              next[Number(key)] = { c: Math.round(v.c), r: Math.round(v.r) };
            }
          }
          setLayout(next);
        } catch {
          /* ignore */
        }
      })
      .catch((err: unknown) =>
        message.error(err instanceof Error ? err.message : "Не удалось загрузить дашборд")
      );
  }, [loading, isManager, router, message]);

  // ширина рабочей области → число колонок сетки (горизонтальной прокрутки нет)
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => setCols(Math.max(1, Math.floor(el.clientWidth / CELL_W)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  if (loading || !data) {
    return (
      <div style={{ padding: 80, textAlign: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  const stored = (o: ObjectDashItem, idx: number): Pos => {
    const s = layout[o.object_id];
    if (!s) return { c: idx % cols, r: Math.floor(idx / cols) };
    return { c: Math.min(s.c, cols - 1), r: Math.max(0, Math.round(s.r)) };
  };

  const maxRow = Math.max(
    0,
    ...data.objects.map((o, i) => stored(o, i).r)
  );
  const areaHeight = (maxRow + 1) * CELL_H + GAP;

  const persist = (next: Record<number, Pos>) => {
    setLayout(next);
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  const startDrag = (e: React.MouseEvent, oid: number) => {
    if (e.button !== 0) return;
    const idx = data.objects.findIndex((o) => o.object_id === oid);
    if (idx < 0) return;
    const base = stored(data.objects[idx], idx);
    drag.current = { id: oid, startX: e.clientX, startY: e.clientY, base, cols };
    e.preventDefault();
    document.body.style.userSelect = "none";

    const move = (ev: MouseEvent) => {
      const d = drag.current;
      if (!d) return;
      const dx = ev.clientX - d.startX;
      const dy = ev.clientY - d.startY;
      const c = clampCell(Math.round((d.base.c * CELL_W + dx) / CELL_W), 0, Math.max(0, d.cols - 1));
      const r = clampCell(Math.round((d.base.r * CELL_H + dy) / CELL_H), 0, Number.MAX_SAFE_INTEGER);
      setLayout((prev) => ({ ...prev, [d.id]: { c, r } }));
      if (ev.clientY > window.innerHeight - 70) window.scrollBy(0, 24);
    };
    const up = () => {
      const d = drag.current;
      if (!d) return;
      setLayout((prev) => {
        persist({ ...prev });
        return prev;
      });
      drag.current = null;
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const meter = (label: string, closed: number, total: number) => {
    const pct = total > 0 ? Math.round((closed / total) * 100) : 0;
    return (
      <div style={{ marginBottom: 3 }}>
        <div style={{ display: "flex", justifyContent: "space-between", lineHeight: "16px" }}>
          <Typography.Text style={{ fontSize: 12 }}>{label}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {closed}/{total}
          </Typography.Text>
        </div>
        <Progress
          percent={pct}
          size="small"
          showInfo={false}
          strokeColor={pct >= 90 ? "#22c55e" : "#3b82f6"}
        />
      </div>
    );
  };
  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0, marginBottom: 4 }}>
        Прогресс по объектам
      </Typography.Title>
      <Space style={{ marginBottom: 12 }} wrap>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          Перетащите карточку за любое место — она встанет на ближайшую ячейку сетки.
        </Typography.Text>
        <Button size="small" onClick={() => persist({})}>
          Сбросить раскладку
        </Button>
      </Space>

      <div
        ref={wrapRef}
        style={{
          position: "relative",
          width: "100%",
          minHeight: areaHeight,
          backgroundImage:
            "repeating-linear-gradient(90deg, transparent 0, transparent " +
            (CELL_W - 1) +
            "px, #eef2f7 " +
            (CELL_W - 1) +
            "px, #eef2f7 " +
            CELL_W +
            "px), repeating-linear-gradient(0deg, transparent 0, transparent " +
            (CELL_H - 1) +
            "px, #eef2f7 " +
            (CELL_H - 1) +
            "px, #eef2f7 " +
            CELL_H +
            "px)",
        }}
      >
        {data.objects.map((o, i) => {
          const p = stored(o, i);
          return (
            <div
              key={o.object_id}
              style={{
                position: "absolute",
                left: p.c * CELL_W,
                top: p.r * CELL_H,
                width: CARD_W,
                height: CARD_H,
                cursor: "grab",
                userSelect: "none",
              }}
              onMouseDown={(e) => startDrag(e, o.object_id)}
            >
              <Card
                size="small"
                style={{ width: "100%", height: "100%" }}
                styles={{ body: { height: "100%", overflow: "hidden" } }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <Typography.Text strong ellipsis style={{ maxWidth: 250 }}>
                    <ApartmentOutlined style={{ color: "#3b82f6", marginRight: 6 }} />
                    {o.name}
                  </Typography.Text>
                  <Tag style={{ marginInlineEnd: 0 }}>{STATUS_LABELS[o.status] ?? o.status}</Tag>
                </div>
                <Typography.Paragraph
                  type="secondary"
                  style={{ fontSize: 12, marginBottom: 6, lineHeight: "16px" }}
                >
                  Позиций: {o.tracked_items} • работ: {o.work_total} • без паспорта:{" "}
                  {o.items_without_docs}
                </Typography.Paragraph>
                {o.untyped_total > 0 && (
                  <Typography.Text
                    type="warning"
                    style={{ fontSize: 11, display: "block", marginBottom: 3 }}
                  >
                    Тип не определён: {o.untyped_total} поз. — уточните в «Позициях»
                  </Typography.Text>
                )}
                {meter("АВК (материалы и оборудование)", o.avk_closed, o.non_work_total)}
                {meter("АОСР (материалы)", o.aosr_closed, o.material_total)}
                {meter("ВСО (оборудование)", o.vso_closed, o.equipment_total)}
                {meter("ВР (работы)", o.vr_closed, o.work_total)}
              </Card>
            </div>
          );
        })}
      </div>
    </div>
  );
}

