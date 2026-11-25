import React from "react";

export default class ErrorBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div role="alert" className="p-8 text-rose-300">
        This view could not be displayed.{" "}
        <button className="underline" onClick={() => window.location.reload()}>
          Reload and retry
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
