"use client";

import type { ReactNode } from "react";
import { Component } from "react";

export class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="notice">
          Something went wrong in this panel. Please refresh the page.
        </div>
      );
    }

    return this.props.children;
  }
}
