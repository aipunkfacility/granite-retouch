import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Slider } from "./slider";

describe("Slider", () => {
  const defaultProps = {
    label: "Яркость",
    value: 50,
    min: 0,
    max: 100,
    step: 1,
    unit: "%",
    onChange: vi.fn(),
  };

  it("renders label and value", () => {
    render(<Slider {...defaultProps} />);
    expect(screen.getByText("Яркость")).toBeTruthy();
    expect(screen.getByText("50 %")).toBeTruthy();
  });

  it("renders slider-fill element with correct width style", () => {
    const { container } = render(<Slider {...defaultProps} value={75} />);
    const fill = container.querySelector(".slider-fill") as HTMLElement;
    expect(fill).toBeTruthy();
    expect(fill.style.width).toBe("75%");
  });

  it("renders reset icon when overridden=true and onReset provided", () => {
    const onReset = vi.fn();
    const { container } = render(
      <Slider {...defaultProps} overridden={true} onReset={onReset} />,
    );
    expect(container.querySelector(".ri-arrow-go-back-line")).toBeTruthy();
  });

  it("does not render reset icon when overridden=false", () => {
    const { container } = render(
      <Slider {...defaultProps} overridden={false} onReset={vi.fn()} />,
    );
    expect(container.querySelector(".ri-arrow-go-back-line")).toBeNull();
  });

  it("calls onReset when reset button is clicked", () => {
    const onReset = vi.fn();
    render(<Slider {...defaultProps} overridden={true} onReset={onReset} />);
    screen.getByRole("button", { name: /сбросить/i }).click();
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("has correct ARIA attributes on the slider input", () => {
    render(<Slider {...defaultProps} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuemin", "0");
    expect(slider).toHaveAttribute("aria-valuemax", "100");
    expect(slider).toHaveAttribute("aria-valuenow", "50");
  });

  it("calls onChange when slider value changes", () => {
    const onChange = vi.fn();
    render(<Slider {...defaultProps} onChange={onChange} />);
    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "80" } });
    expect(onChange).toHaveBeenCalledWith(80);
  });
});
