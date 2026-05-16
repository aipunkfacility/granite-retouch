import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiagnosticsPanel } from "./diagnostics-panel";
import type { DiagnosticsData } from "../lib/api";

const mockDiagnostics: DiagnosticsData = {
  face_brightness_before: 150,
  face_brightness_after: 200,
  face_correction_factor: 1.3,
  glow_size: 12,
  glow_opacity: 0.5,
  black_ratio: 0.25,
  blue_ratio: 0.08,
  width: 880,
  height: 1288,
  numba_available: true,
};

describe("DiagnosticsPanel", () => {
  it("returns null when no diagnostics", () => {
    const { container } = render(<DiagnosticsPanel diagnostics={null} warnings={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders face brightness values", () => {
    render(<DiagnosticsPanel diagnostics={mockDiagnostics} warnings={[]} />);
    expect(screen.getByText(/150\.0/)).toBeTruthy();
    expect(screen.getByText(/200\.0/)).toBeTruthy();
  });

  it("renders glow info", () => {
    render(<DiagnosticsPanel diagnostics={mockDiagnostics} warnings={[]} />);
    expect(screen.getByText(/12px/)).toBeTruthy();
    expect(screen.getByText(/50%/)).toBeTruthy();
  });

  it("renders black ratio with color class", () => {
    const { container } = render(<DiagnosticsPanel diagnostics={mockDiagnostics} warnings={[]} />);
    // 25% is less than 30% → green
    const blackEl = container.querySelector(".text-accent-green");
    expect(blackEl).toBeTruthy();
  });

  it("renders dimensions", () => {
    render(<DiagnosticsPanel diagnostics={mockDiagnostics} warnings={[]} />);
    expect(screen.getByText("880×1288")).toBeTruthy();
  });

  it("renders warnings when present", () => {
    render(<DiagnosticsPanel diagnostics={mockDiagnostics} warnings={["Test warning"]} />);
    expect(screen.getByText("Test warning")).toBeTruthy();
  });

  it("renders without heading in compact mode", () => {
    render(<DiagnosticsPanel diagnostics={mockDiagnostics} warnings={[]} compact />);
    expect(screen.queryByText("Диагностика")).toBeNull();
  });

  it("renders heading in non-compact mode", () => {
    render(<DiagnosticsPanel diagnostics={mockDiagnostics} warnings={[]} />);
    expect(screen.getByText("Диагностика")).toBeTruthy();
  });
});
