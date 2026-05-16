import { describe, it, expect } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { BeforeImage } from "./before-image";

describe("BeforeImage", () => {
  it("renders placeholder when no image", () => {
    render(<BeforeImage originalUrl={null} />);
    expect(screen.getByText("Нет изображения")).toBeTruthy();
  });

  it("renders image when url provided", () => {
    render(<BeforeImage originalUrl="data:image/png;base64,test" />);
    const img = screen.getByAltText("Original") as HTMLImageElement;
    expect(img).toBeTruthy();
    expect(img.src).toContain("data:image/png;base64,test");
  });

  it("renders heading", () => {
    render(<BeforeImage originalUrl={null} />);
    expect(screen.getByText("До")).toBeTruthy();
  });

  it("shows size badge after image loads", () => {
    render(<BeforeImage originalUrl="data:image/png;base64,test" />);
    const img = screen.getByAltText("Original");
    act(() => {
      Object.defineProperty(img, "naturalWidth", { value: 880 });
      Object.defineProperty(img, "naturalHeight", { value: 1288 });
      fireEvent.load(img);
    });
    expect(screen.getByText("880 × 1288")).toBeTruthy();
  });

  it("does not show size badge before image loads", () => {
    render(<BeforeImage originalUrl="data:image/png;base64,test" />);
    expect(screen.queryByText(/×/)).toBeNull();
  });
});
