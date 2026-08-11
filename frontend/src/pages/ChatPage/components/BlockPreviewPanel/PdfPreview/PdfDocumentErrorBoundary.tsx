import React from "react";

export interface PdfDocumentErrorBoundaryProps {
  children: React.ReactNode;
  fallback: React.ReactNode;
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

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

export default PdfDocumentErrorBoundary;
