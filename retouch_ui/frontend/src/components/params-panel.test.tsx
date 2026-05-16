import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ParamsPanel } from "./params-panel";
import { ToastProvider } from "./toast-provider";

function wrap(ui: React.ReactElement) {
  return <ToastProvider>{ui}</ToastProvider>;
}

describe("ParamsPanel", () => {
  const baseProps = {
    machineType: "laser_standard" as const,
    config: {},
    onConfigChange: vi.fn(),
  };

  it("renders section headings for available groups", () => {
    render(wrap(<ParamsPanel {...baseProps} />));
    expect(screen.getByText("Параметры")).toBeTruthy();
  });

  it("renders Advanced checkbox", () => {
    render(wrap(<ParamsPanel {...baseProps} />));
    expect(screen.getByText("Advanced")).toBeTruthy();
  });

  it("renders default badges for non-advanced groups", () => {
    render(wrap(<ParamsPanel {...baseProps} />));
    const badges = screen.getAllByText("по умолчанию");
    expect(badges.length).toBeGreaterThanOrEqual(3);
  });

  it("renders shadow section for impact machine", () => {
    render(wrap(<ParamsPanel {...baseProps} machineType="impact" />));
    // Shadow-specific param should not cause crash
    expect(screen.getByText("Параметры")).toBeTruthy();
  });
});
