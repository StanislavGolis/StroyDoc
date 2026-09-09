"use client";

import { useEffect, useState } from "react";
import { App as AntApp, Button, DatePicker, Form, Input, Modal, Select } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { objectsApi, type ObjectPayload } from "@/lib/api";
import type { ConstructionObject, ObjectStatus } from "@/lib/types";

const { RangePicker } = DatePicker;

interface ObjectFormValues {
  name: string;
  code?: string;
  dates?: [Dayjs, Dayjs];
  status?: ObjectStatus;
}

interface Props {
  open: boolean;
  initial?: ConstructionObject | null;
  onCancel: () => void;
  onSaved: (obj: ConstructionObject) => void;
}

export function ObjectFormModal({ open, initial, onCancel, onSaved }: Props) {
  const [form] = Form.useForm<ObjectFormValues>();
  const { message } = AntApp.useApp();
  const [saving, setSaving] = useState(false);
  const isEdit = Boolean(initial);

  useEffect(() => {
    if (open) {
      form.resetFields();
      if (initial) {
        form.setFieldsValue({
          name: initial.name,
          code: initial.code ?? "",
          dates:
            initial.start_date && initial.end_date
              ? [dayjs(initial.start_date), dayjs(initial.end_date)]
              : undefined,
          status: initial.status,
        });
      } else {
        form.setFieldsValue({ name: "", status: "planning" });
      }
    }
  }, [open, initial, form]);

  const handleOk = async () => {
    const values = await form.validateFields();
    const range = values.dates ?? [];
    const payload: ObjectPayload = {
      name: values.name.trim(),
      code: values.code?.trim() || null,
      start_date: range[0] ? range[0].format("YYYY-MM-DD") : null,
      end_date: range[1] ? range[1].format("YYYY-MM-DD") : null,
      status: values.status ?? "planning",
    };
    setSaving(true);
    try {
      const saved = initial
        ? await objectsApi.update(initial.id, payload)
        : await objectsApi.create(payload);
      message.success(initial ? "Объект обновлён" : "Объект создан");
      onSaved(saved);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось сохранить");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEdit ? "Редактировать объект" : "Новый объект"}
      open={open}
      onCancel={onCancel}
      onOk={handleOk}
      confirmLoading={saving}
      destroyOnHidden
      width={520}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="Название" rules={[{ required: true, message: "Укажите название" }]}>
          <Input placeholder="Например: ЖК Солнечный, корпус 2" maxLength={500} />
        </Form.Item>
        <Form.Item name="code" label="Шифр">
          <Input placeholder="Шифр объекта" maxLength={100} />
        </Form.Item>
        <Form.Item name="dates" label="Период работ">
          <RangePicker style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="status" label="Статус">
          <Select
            options={[
              { value: "planning", label: "Планируется" },
              { value: "active", label: "В работе" },
              { value: "closed", label: "Закрыт" },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
