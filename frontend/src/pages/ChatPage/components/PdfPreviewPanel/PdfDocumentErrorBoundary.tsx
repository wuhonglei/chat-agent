import React from "react";

export interface PdfDocumentErrorBoundaryProps {
  children: React.ReactNode;
  fallback: React.ReactNode;
  resetKey: string;
  onError: (error: Error) => void;
}

interface PdfDocumentErrorBoundaryState {
  hasError: boolean;
}

class PdfDocumentErrorBoundary extends React.Component<PdfDocumentErrorBoundaryProps, PdfDocumentErrorBoundaryState> {
  state: PdfDocumentErrorBoundaryState = {
    hasError: false,
  };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    this.props.onError(error);
  }

  componentDidUpdate(prevProps: Readonly<PdfDocumentErrorBoundaryProps>) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

export default PdfDocumentErrorBoundary;
