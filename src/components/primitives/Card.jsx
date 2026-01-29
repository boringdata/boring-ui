import React from 'react'
import { clsx } from 'clsx'

const elevationVariants = {
  none: 'border border-border',
  sm: 'shadow-sm border border-border',
  md: 'shadow-md border border-border',
  lg: 'shadow-lg border border-border/50',
  xl: 'shadow-xl border border-border/30',
}

const paddingVariants = {
  none: 'p-0',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
  xl: 'p-8',
}

/**
 * Card - Container component with elevation and padding options
 * @component
 * @param {string} elevation - Shadow depth: none, sm, md, lg, xl
 * @param {string} padding - Padding size: none, sm, md, lg, xl
 * @param {boolean} interactive - Add hover effects
 * @param {React.ReactNode} children - Card content
 */
const Card = React.forwardRef(({
  elevation = 'md',
  padding = 'md',
  interactive = false,
  children,
  className,
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
      className={clsx(
        'bg-bg-primary rounded-lg',
        elevationVariants[elevation],
        paddingVariants[padding],
        interactive && 'cursor-pointer hover:shadow-lg transition-all duration-normal',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
})

Card.displayName = 'Card'

/**
 * Card.Header - Header section with bordered bottom
 */
const CardHeader = React.forwardRef(({ children, className, ...props }, ref) => (
  <div
    ref={ref}
    className={clsx('border-b border-border pb-3 mb-3', className)}
    {...props}
  >
    {children}
  </div>
))
CardHeader.displayName = 'CardHeader'

/**
 * Card.Body - Main content section
 */
const CardBody = React.forwardRef(({ children, className, ...props }, ref) => (
  <div
    ref={ref}
    className={clsx('', className)}
    {...props}
  >
    {children}
  </div>
))
CardBody.displayName = 'CardBody'

/**
 * Card.Footer - Footer section with bordered top
 */
const CardFooter = React.forwardRef(({ children, className, ...props }, ref) => (
  <div
    ref={ref}
    className={clsx('border-t border-border pt-3 mt-3', className)}
    {...props}
  >
    {children}
  </div>
))
CardFooter.displayName = 'CardFooter'

Card.Header = CardHeader
Card.Body = CardBody
Card.Footer = CardFooter

export default Card
