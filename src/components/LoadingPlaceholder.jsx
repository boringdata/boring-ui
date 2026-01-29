import React from 'react';
import { clsx } from 'clsx';
import Skeleton from './primitives/Skeleton';

/**
 * LoadingPlaceholder Component
 * Composable loading placeholder builder
 *
 * @component
 * @example
 * ```jsx
 * <LoadingPlaceholder.Card />
 * <LoadingPlaceholder.List count={3} />
 * <LoadingPlaceholder.Profile />
 * ```
 */

// Profile placeholder
export const ProfilePlaceholder = ({ className }) => (
  <div className={clsx('space-y-4', className)}>
    <Skeleton variant="circle" size={60} />
    <Skeleton variant="text" width="70%" height="1.25rem" />
    <Skeleton variant="text" width="50%" height="1rem" />
  </div>
);

// Card placeholder
export const CardPlaceholder = ({ className }) => (
  <div className={clsx('space-y-4 p-4 border rounded-lg', className)}>
    <Skeleton variant="text" width="60%" height="1.25rem" />
    <div className="space-y-2">
      <Skeleton variant="text" width="100%" height="0.875rem" />
      <Skeleton variant="text" width="100%" height="0.875rem" />
      <Skeleton variant="text" width="80%" height="0.875rem" />
    </div>
  </div>
);

// List placeholder
export const ListPlaceholder = ({ count = 3, className }) => (
  <div className={clsx('space-y-3', className)}>
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className="flex gap-3">
        <Skeleton variant="circle" size={40} />
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" width="60%" height="0.875rem" />
          <Skeleton variant="text" width="80%" height="0.75rem" />
        </div>
      </div>
    ))}
  </div>
);

// Table placeholder
export const TablePlaceholder = ({ rows = 4, cols = 3, className }) => (
  <div className={clsx('space-y-2 border rounded-lg overflow-hidden', className)}>
    {/* Header */}
    <div className="grid gap-4 p-4 border-b" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={`header-${i}`} variant="text" width="100%" height="0.875rem" />
      ))}
    </div>
    {/* Body rows */}
    {Array.from({ length: rows }).map((_, rowIndex) => (
      <div key={rowIndex} className="grid gap-4 p-4 border-b last:border-b-0" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: cols }).map((_, colIndex) => (
          <Skeleton key={`${rowIndex}-${colIndex}`} variant="text" width="100%" height="0.875rem" />
        ))}
      </div>
    ))}
  </div>
);

// Image placeholder
export const ImagePlaceholder = ({ width = '100%', height = '200px', className }) => (
  <Skeleton
    variant="box"
    width={width}
    height={height}
    rounded="lg"
    className={className}
  />
);

// Custom placeholder builder
export const CustomPlaceholder = ({ children, className }) => (
  <div className={clsx('space-y-3 animate-pulse', className)}>
    {children}
  </div>
);

// Composite namespace
const LoadingPlaceholder = {
  Profile: ProfilePlaceholder,
  Card: CardPlaceholder,
  List: ListPlaceholder,
  Table: TablePlaceholder,
  Image: ImagePlaceholder,
  Custom: CustomPlaceholder,
};

export default LoadingPlaceholder;
