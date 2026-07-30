import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error?: Error;
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = {};

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Mission Control render failure", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="fatal-error">
          <p className="eyebrow">MISSION CONTROL / UI RECOVERY</p>
          <h1>The interface encountered a rendering error.</h1>
          <p>{this.state.error.message}</p>
          <button onClick={() => window.location.reload()}>
            Reload Mission Control
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
