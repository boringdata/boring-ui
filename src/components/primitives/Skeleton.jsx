import React from 'react';
import { clsx } from 'clsx';
import '../../styles/skeleton.css';

/**
 * Skeleton Component
 * Provides loading placeholders with shimmer animation
 *
 * @component
 * @example
 * ```jsx
 * <Skeleton variant="text" />
 * <Skeleton variant="circle" size={40} />
 * <Skeleton variant="box" width={200} height={100} />
 * ```
 */
const Skeleton = React.forwardRef(({
  variant = 'box',
  width = '100%',
  height = '1rem',
  size,
  rounded = 'md',
  className,
  ...props
}, ref) => {
  // For circle variant, size controls both width and height
  const finalWidth = variant === 'circle' && size ? `${size}px` : width;
  const finalHeight = variant === 'circle' && size ? `${size}px` : height;

  return (
    <div
      ref={ref}
      className={clsx(
        'skeleton',
        `skeleton-${variant}`,
        variant === 'circle' ? 'rounded-full' : `rounded-${rounded}`,
        className
      )}
      style={{
        width: finalWidth,
        height: finalHeight,
        ...props.style,
      }}
      {...props}
    />
  );
});

Skeleton.displayName = 'Skeleton';

export default Skeleton;
