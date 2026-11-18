// Kiro Crew App Kit Frontend Entry (`ui/dist/index.mjs`)
// Resolved at runtime by Kiro Crew Host import maps (`@kirocrew/app-sdk` & `@kirocrew/app-sdk/ui`)
// Note: UIConfig.entry ("dist/index.mjs") resolves relative to `<app_root>/ui/`, i.e. `<app_root>/ui/dist/index.mjs`.

import React, { useEffect, useState } from "react";
import { useAppApi, useAppEvents, useAppInfo, useNotify, useChatLauncher } from "@kirocrew/app-sdk";
import { Card, CardTitle, PageHeader, StatCard } from "@kirocrew/app-sdk/ui";

export default function GhostForemanApp() {
  const api = useAppApi();
  const appInfo = useAppInfo();
  const notify = useNotify();
  const launchChat = useChatLauncher();
  const [dashboard, setDashboard] = useState(null);

  const refresh = async () => {
    const data = await api.get("/api/apps/ghost-foreman/dashboard");
    setDashboard(data);
  };

  useEffect(() => {
    refresh();
  }, []);

  useAppEvents("slots", () => refresh());
  useAppEvents("onChatDone", () => refresh());

  if (!dashboard) {
    return React.createElement("div", { style: { padding: 24, color: "#e9d5ff" } }, "👻 Ghost Foreman 起動中...");
  }

  return React.createElement(
    "div",
    { style: { background: "#0d0b18", color: "#f3e8ff", minHeight: "100vh", padding: 24 } },
    React.createElement(PageHeader, {
      title: "👻 Ghost Foreman — 幽霊現場監督",
      subtitle: `Your agents work. You have a life. (${appInfo?.version || "0.2.0"} / ${dashboard.mode_state?.gateway_mode})`
    }),
    React.createElement(
      "div",
      { style: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 16 } },
      React.createElement(StatCard, { label: "管理スロット (Managed/MCP)", value: String(dashboard.slots.length) }),
      React.createElement(StatCard, {
        label: "人間判断待ち",
        value: String(dashboard.questions.filter((q) => q.status.startsWith("needs_human") || q.status.startsWith("held")).length)
      }),
      React.createElement(StatCard, {
        label: "幽霊の自動解決数",
        value: String(dashboard.questions.filter((q) => q.status === "auto_resolved").length)
      }),
      React.createElement(StatCard, { label: "選択的記憶 (Policies)", value: String(dashboard.policies.length) })
    ),
    React.createElement(
      Card,
      { style: { marginTop: 16 } },
      React.createElement(CardTitle, null, "Managed Slots & Direct Chat Hand-off"),
      dashboard.slots.slice(0, 6).map((slot) =>
        React.createElement(
          "div",
          {
            key: slot.id,
            style: { display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #2e1f47" }
          },
          React.createElement("span", null, `[${slot.id}] ${slot.name} — ${slot.current_task}`),
          React.createElement(
            "button",
            {
              onClick: () => {
                launchChat({ slotId: slot.id, agent: slot.backend });
                notify({ title: "Slot Opened", message: `${slot.name} へ直接接続しました` });
              }
            },
            "直接話す"
          )
        )
      )
    )
  );
}

export function mount(container) {
  return GhostForemanApp;
}
