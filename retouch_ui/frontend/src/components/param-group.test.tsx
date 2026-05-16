import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ParamGroup } from "./param-group";
import type { ParamSection } from "../lib/config-schema";

const mainSection: ParamSection = {
  key: "main",
  label: "Основные",
  icon: "ri-settings-3-line",
  params: ["stone_gamma", "glow_style", "export_mode"],
};

describe("ParamGroup", () => {
  const baseProps = {
    section: mainSection,
    config: {},
    machineType: "laser_standard" as const,
    onConfigChange: vi.fn(),
  };

  it("renders section label", () => {
    render(<ParamGroup {...baseProps} />);
    expect(screen.getByText("Основные")).toBeTruthy();
  });

  it("shows 'по умолчанию' badge when nothing overridden", () => {
    render(<ParamGroup {...baseProps} />);
    expect(screen.getByText("по умолчанию")).toBeTruthy();
  });

  it("shows overridden count when keys are overridden", () => {
    render(
      <ParamGroup
        {...baseProps}
        overriddenKeys={new Set(["processing.laser_standard.stone_gamma"])}
      />,
    );
    expect(screen.getByText(/1 изменены/)).toBeTruthy();
  });

  it("renders param sliders when expanded", () => {
    render(<ParamGroup {...baseProps} defaultCollapsed={false} />);
    expect(screen.getByText("Гамма камня")).toBeTruthy();
    expect(screen.getByText("Стиль Glow")).toBeTruthy();
  });

  it("collapses content by default", () => {
    const { container } = render(<ParamGroup {...baseProps} />);
    const content = container.querySelector(".max-h-0");
    expect(content).toBeTruthy();
  });

  it("expands content when defaultCollapsed is false", () => {
    const { container } = render(<ParamGroup {...baseProps} defaultCollapsed={false} />);
    const content = container.querySelector(".opacity-100");
    expect(content).toBeTruthy();
  });
});
