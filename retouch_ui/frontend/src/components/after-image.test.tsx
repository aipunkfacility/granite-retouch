import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AfterImage } from "./after-image";

describe("AfterImage", () => {
  const baseProps = {
    imageUrl: null,
    stepLabel: "final",
    vignetteOverlayEnabled: false,
    faceOvalOverlayEnabled: false,
    faceOval: null,
    onFaceOvalChange: vi.fn(),
    imageWidth: 0,
    imageHeight: 0,
    vignetteParams: {
      vertical_offset: 0,
      vertical_diameter: 0.5,
      blur_radius: 60,
      headroom: 0.5,
      horizontal_oversize: 0.2,
    },
    onVignetteParamChange: vi.fn(),
  };

  it("renders placeholder when no image", () => {
    render(<AfterImage {...baseProps} />);
    expect(screen.getByText("Нет данных")).toBeTruthy();
  });

  it("renders heading with step label", () => {
    render(<AfterImage {...baseProps} stepLabel="face_corrected" />);
    expect(screen.getByText(/После:/)).toBeTruthy();
    expect(screen.getByText(/face_corrected/)).toBeTruthy();
  });

  it("renders image when url provided", () => {
    render(<AfterImage {...baseProps} imageUrl="data:image/png;base64,test" stepLabel="final" />);
    const img = screen.getByAltText("Step: final") as HTMLImageElement;
    expect(img).toBeTruthy();
    expect(img.src).toContain("data:image/png;base64,test");
  });

  it("does not render vignette overlay when disabled", () => {
    const { container } = render(
      <AfterImage {...baseProps} imageWidth={800} imageHeight={600} vignetteOverlayEnabled={false} />,
    );
    expect(container.querySelector("svg")).toBeNull();
  });

  it("does not render face oval overlay when disabled", () => {
    const { container } = render(
      <AfterImage
        {...baseProps}
        imageWidth={800}
        imageHeight={600}
        faceOvalOverlayEnabled={false}
        faceOval={{ cx: 0.5, cy: 0.5, rx: 0.3, ry: 0.4, source: "manual" }}
      />,
    );
    expect(container.querySelector("svg")).toBeNull();
  });
});
