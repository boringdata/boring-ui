import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Skeleton from '../../components/primitives/Skeleton';
import Spinner from '../../components/primitives/Spinner';
import ProgressBar from '../../components/primitives/ProgressBar';
import LoadingPlaceholder from '../../components/LoadingPlaceholder';

describe('Skeleton Component', () => {
  it('renders skeleton element', () => {
    const { container } = render(<Skeleton />);
    expect(container.querySelector('.skeleton')).toBeInTheDocument();
  });

  it('renders text variant', () => {
    const { container } = render(<Skeleton variant="text" />);
    expect(container.querySelector('.skeleton-text')).toBeInTheDocument();
  });

  it('renders circle variant', () => {
    const { container } = render(<Skeleton variant="circle" size={40} />);
    const element = container.querySelector('.skeleton-circle');
    expect(element).toBeInTheDocument();
    expect(element).toHaveStyle('width: 40px');
    expect(element).toHaveStyle('height: 40px');
  });

  it('renders box variant', () => {
    const { container } = render(<Skeleton variant="box" />);
    expect(container.querySelector('.skeleton-box')).toBeInTheDocument();
  });

  it('accepts custom width and height', () => {
    const { container } = render(
      <Skeleton width="200px" height="100px" />
    );
    const element = container.querySelector('.skeleton');
    expect(element).toHaveStyle('width: 200px');
    expect(element).toHaveStyle('height: 100px');
  });

  it('accepts custom className', () => {
    const { container } = render(
      <Skeleton className="custom-class" />
    );
    expect(container.querySelector('.skeleton')).toHaveClass('custom-class');
  });
});

describe('Spinner Component', () => {
  it('renders spinner element', () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector('.spinner')).toBeInTheDocument();
  });

  it('renders with correct size classes', () => {
    const { container: containerSm } = render(<Spinner size="sm" />);
    expect(containerSm.querySelector('.spinner')).toHaveClass('w-4', 'h-4');

    const { container: containerMd } = render(<Spinner size="md" />);
    expect(containerMd.querySelector('.spinner')).toHaveClass('w-6', 'h-6');

    const { container: containerLg } = render(<Spinner size="lg" />);
    expect(containerLg.querySelector('.spinner')).toHaveClass('w-8', 'h-8');
  });

  it('renders with correct color classes', () => {
    const { container } = render(<Spinner color="success" />);
    expect(container.querySelector('.spinner')).toHaveClass('text-success');
  });

  it('has proper accessibility role and label', () => {
    render(<Spinner label="Loading data" />);
    const spinner = screen.getByRole('status');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveAttribute('aria-label', 'Loading data');
  });

  it('renders SVG spinner', () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('accepts custom className', () => {
    const { container } = render(
      <Spinner className="custom-class" />
    );
    expect(container.querySelector('.spinner')).toHaveClass('custom-class');
  });
});

describe('ProgressBar Component', () => {
  it('renders progress bar', () => {
    const { container } = render(<ProgressBar />);
    expect(container.querySelector('.progress-bar-container')).toBeInTheDocument();
  });

  it('calculates percentage correctly', () => {
    const { container } = render(<ProgressBar value={50} max={100} />);
    const fill = container.querySelector('.progress-bar-fill');
    expect(fill).toHaveStyle('width: 50%');
  });

  it('handles different max values', () => {
    const { container } = render(<ProgressBar value={75} max={150} />);
    const fill = container.querySelector('.progress-bar-fill');
    expect(fill).toHaveStyle('width: 50%');
  });

  it('clamps value between 0 and max', () => {
    const { container: containerNeg } = render(<ProgressBar value={-10} max={100} />);
    expect(containerNeg.querySelector('.progress-bar-fill')).toHaveStyle('width: 0%');

    const { container: containerOver } = render(<ProgressBar value={150} max={100} />);
    expect(containerOver.querySelector('.progress-bar-fill')).toHaveStyle('width: 100%');
  });

  it('renders indeterminate state', () => {
    const { container } = render(<ProgressBar indeterminate />);
    expect(container.querySelector('.progress-bar-indeterminate')).toBeInTheDocument();
  });

  it('has proper accessibility attributes', () => {
    render(<ProgressBar value={65} max={100} />);
    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '65');
    expect(progressBar).toHaveAttribute('aria-valuemin', '0');
    expect(progressBar).toHaveAttribute('aria-valuemax', '100');
  });

  it('renders with different sizes', () => {
    const { container: containerSm } = render(<ProgressBar size="sm" />);
    expect(containerSm.querySelector('.progress-bar-container')).toHaveClass('h-1');

    const { container: containerMd } = render(<ProgressBar size="md" />);
    expect(containerMd.querySelector('.progress-bar-container')).toHaveClass('h-2');

    const { container: containerLg } = render(<ProgressBar size="lg" />);
    expect(containerLg.querySelector('.progress-bar-container')).toHaveClass('h-3');
  });

  it('renders with different colors', () => {
    const { container } = render(<ProgressBar color="success" />);
    expect(container.querySelector('.progress-bar-fill')).toHaveClass('bg-success');
  });
});

describe('LoadingPlaceholder', () => {
  it('renders ProfilePlaceholder', () => {
    const { container } = render(<LoadingPlaceholder.Profile />);
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders CardPlaceholder', () => {
    const { container } = render(<LoadingPlaceholder.Card />);
    expect(container.querySelector('.skeleton')).toBeInTheDocument();
  });

  it('renders ListPlaceholder with default count', () => {
    const { container } = render(<LoadingPlaceholder.List />);
    const items = container.querySelectorAll('[class*="flex"]');
    expect(items.length).toBeGreaterThan(0);
  });

  it('renders ListPlaceholder with custom count', () => {
    const { container } = render(<LoadingPlaceholder.List count={5} />);
    const skeletons = container.querySelectorAll('.skeleton');
    // Each item has 2 skeletons (avatar + text lines)
    expect(skeletons.length).toBeGreaterThanOrEqual(10);
  });

  it('renders TablePlaceholder', () => {
    const { container } = render(<LoadingPlaceholder.Table rows={3} cols={3} />);
    const skeletons = container.querySelectorAll('.skeleton');
    // Header (3) + rows (3 * 3) = 12 skeletons
    expect(skeletons.length).toBeGreaterThanOrEqual(12);
  });

  it('renders ImagePlaceholder', () => {
    const { container } = render(
      <LoadingPlaceholder.Image width="300px" height="150px" />
    );
    const skeleton = container.querySelector('.skeleton');
    expect(skeleton).toHaveStyle('width: 300px');
    expect(skeleton).toHaveStyle('height: 150px');
  });

  it('renders CustomPlaceholder', () => {
    const { container } = render(
      <LoadingPlaceholder.Custom>
        <Skeleton />
        <Skeleton />
      </LoadingPlaceholder.Custom>
    );
    const skeletons = container.querySelectorAll('.skeleton');
    expect(skeletons.length).toBe(2);
  });
});
