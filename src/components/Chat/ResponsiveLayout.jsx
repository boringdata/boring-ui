import { useCallback, useState } from 'react'
import { useResponsive } from '../../hooks/useResponsive'

/**
 * ResponsiveLayout - Mobile-first responsive chat layout
 *
 * Features:
 * - Mobile-first design (optimized for 375px phones)
 * - Collapsible sidebar on mobile (hamburger menu)
 * - Stacked layout for message threads on mobile
 * - Touch-optimized spacing and button sizes
 * - Safe area support for notches/safe zones
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Layout content
 * @param {React.ReactNode} props.sidebar - Sidebar content (hidden on mobile)
 * @param {boolean} props.showSidebar - Whether sidebar is visible
 * @param {Function} props.onSidebarToggle - Callback when hamburger is clicked
 * @param {string} props.className - Additional CSS classes
 * @returns {React.ReactElement}
 *
 * @example
 * ```jsx
 * function App() {
 *   const [showSidebar, setShowSidebar] = useState(false);
 *
 *   return (
 *     <ResponsiveLayout
 *       sidebar={<SidebarContent />}
 *       showSidebar={showSidebar}
 *       onSidebarToggle={() => setShowSidebar(!showSidebar)}
 *     >
 *       <ChatContent />
 *     </ResponsiveLayout>
 *   );
 * }
 * ```
 */
export function ResponsiveLayout({
  children,
  sidebar,
  showSidebar = false,
  onSidebarToggle,
  className = '',
}) {
  const { isMobile, isTablet, currentBreakpoint } = useResponsive()

  return (
    <div
      className={`responsive-layout ${className}`}
      style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        backgroundColor: 'var(--color-bg-primary)',
      }}
    >
      {/* Sidebar - Hidden on mobile, always visible on tablet+ */}
      {sidebar && (
        <>
          {/* Mobile hamburger overlay */}
          {isMobile && showSidebar && (
            <div
              className="sidebar-overlay"
              onClick={onSidebarToggle}
              style={{
                position: 'fixed',
                inset: 0,
                backgroundColor: 'var(--color-overlay)',
                zIndex: 29, // Below mobile sidebar
                animation: 'fadeIn 150ms ease-out',
              }}
            />
          )}

          {/* Sidebar */}
          <aside
            className="responsive-sidebar"
            style={{
              display: isMobile && !showSidebar ? 'none' : 'flex',
              flexDirection: 'column',
              width: isMobile ? '100%' : 'var(--sidebar-width, 280px)',
              height: isMobile ? '100%' : undefined,
              maxHeight: isMobile ? undefined : '100%',
              overflow: 'auto',
              backgroundColor: 'var(--color-bg-secondary)',
              borderRight: !isMobile ? '1px solid var(--color-border)' : 'none',
              borderBottom: isMobile ? '1px solid var(--color-border)' : 'none',
              position: isMobile ? 'fixed' : 'relative',
              top: isMobile ? 0 : undefined,
              left: isMobile ? 0 : undefined,
              right: isMobile ? 0 : undefined,
              zIndex: isMobile ? 30 : 'auto',
              animation: isMobile && showSidebar ? 'slideInLeft 200ms ease-out' : undefined,
              paddingTop: isMobile ? 'max(var(--safe-area-inset-top, 0px), 12px)' : 0,
              paddingLeft: 'max(var(--safe-area-inset-left, 0px), 0px)',
              paddingRight: 'max(var(--safe-area-inset-right, 0px), 0px)',
              paddingBottom: isMobile ? 'max(var(--safe-area-inset-bottom, 0px), 12px)' : 0,
            }}
          >
            {sidebar}
          </aside>
        </>
      )}

      {/* Main content */}
      <main
        className="responsive-main"
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minWidth: 0, // Allow flex to shrink below content size
          minHeight: isMobile ? 0 : '100%',
          overflow: 'hidden',
          paddingTop: isMobile ? 'max(var(--safe-area-inset-top, 0px), 0px)' : 0,
          paddingLeft: 'max(var(--safe-area-inset-left, 0px), 0px)',
          paddingRight: 'max(var(--safe-area-inset-right, 0px), 0px)',
          paddingBottom: isMobile ? 'max(var(--safe-area-inset-bottom, 0px), 0px)' : 0,
        }}
      >
        {/* Mobile header with hamburger */}
        {isMobile && sidebar && (
          <div
            className="mobile-header"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--space-3) var(--space-4)',
              minHeight: '52px',
              backgroundColor: 'var(--color-bg-secondary)',
              borderBottom: '1px solid var(--color-border)',
              gap: 'var(--space-2)',
            }}
          >
            <HamburgerButton
              isOpen={showSidebar}
              onClick={onSidebarToggle}
              aria-label={showSidebar ? 'Close navigation' : 'Open navigation'}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <span style={{
                fontSize: 'var(--text-sm)',
                fontWeight: 'var(--font-semibold)',
                color: 'var(--color-text-primary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                Chat
              </span>
            </div>
          </div>
        )}

        {/* Main content area */}
        <div
          className="responsive-content"
          style={{
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          {children}
        </div>
      </main>
    </div>
  )
}

/**
 * HamburgerButton - Touch-friendly hamburger menu button
 * Minimum 48px touch target (WCAG AAA)
 */
function HamburgerButton({ isOpen = false, onClick, ...props }) {
  return (
    <button
      className="hamburger-button"
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '48px',
        height: '48px',
        minWidth: '48px',
        minHeight: '48px',
        padding: 0,
        backgroundColor: 'transparent',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--color-text-primary)',
        transition: 'background-color 150ms ease, color 150ms ease',
        borderRadius: 'var(--radius-md)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = 'var(--color-bg-tertiary)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent'
      }}
      {...props}
    >
      <HamburgerIcon isOpen={isOpen} />
    </button>
  )
}

/**
 * HamburgerIcon - Animated hamburger/X icon
 */
function HamburgerIcon({ isOpen = false }) {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transition: 'transform 200ms ease',
        transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
      }}
    >
      {isOpen ? (
        <>
          {/* X icon */}
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </>
      ) : (
        <>
          {/* Hamburger icon */}
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </>
      )}
    </svg>
  )
}

/**
 * ResponsiveMessageThread - Responsive wrapper for message threads
 * Stacks messages in single column on mobile, with proper spacing
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Messages to display
 * @param {string} props.className - Additional CSS classes
 * @returns {React.ReactElement}
 */
export function ResponsiveMessageThread({ children, className = '' }) {
  const { isMobile } = useResponsive()

  return (
    <div
      className={`responsive-message-thread ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: isMobile ? 'var(--space-3)' : 'var(--space-4)',
        padding: isMobile ? 'var(--space-3)' : 'var(--space-4)',
        overflowY: 'auto',
        flex: 1,
      }}
    >
      {children}
    </div>
  )
}

/**
 * ResponsiveMessage - Responsive message bubble
 * Adjusts width and alignment based on device
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Message content
 * @param {'user' | 'assistant'} props.role - Message role
 * @param {string} props.className - Additional CSS classes
 * @returns {React.ReactElement}
 */
export function ResponsiveMessage({
  children,
  role = 'assistant',
  className = '',
}) {
  const { isMobile } = useResponsive()
  const isUser = role === 'user'

  return (
    <div
      className={`responsive-message responsive-message-${role} ${className}`}
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 'var(--space-2)',
      }}
    >
      <div
        style={{
          maxWidth: isMobile ? '90%' : '70%',
          padding: 'var(--space-3) var(--space-4)',
          borderRadius: 'var(--radius-lg)',
          backgroundColor: isUser
            ? 'var(--color-accent)'
            : 'var(--color-bg-tertiary)',
          color: isUser ? 'white' : 'var(--color-text-primary)',
          wordBreak: 'break-word',
          overflowWrap: 'break-word',
        }}
      >
        {children}
      </div>
    </div>
  )
}

/**
 * ResponsiveInputArea - Responsive input section with touch-friendly sizing
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Input content
 * @param {string} props.className - Additional CSS classes
 * @returns {React.ReactElement}
 */
export function ResponsiveInputArea({ children, className = '' }) {
  const { isMobile } = useResponsive()

  return (
    <div
      className={`responsive-input-area ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: isMobile ? 'var(--space-2)' : 'var(--space-3)',
        padding: `var(--space-3) var(--space-4) max(var(--safe-area-inset-bottom, 0px), var(--space-3)) var(--space-4)`,
        backgroundColor: 'var(--color-bg-secondary)',
        borderTop: '1px solid var(--color-border)',
        minHeight: isMobile ? '80px' : '100px',
      }}
    >
      {children}
    </div>
  )
}

/**
 * ResponsiveButton - Touch-friendly button with minimum 48px size
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Button content
 * @param {string} props.className - Additional CSS classes
 * @param {Function} props.onClick - Click handler
 * @param {string} props.variant - Button style variant
 * @returns {React.ReactElement}
 */
export function ResponsiveButton({
  children,
  className = '',
  onClick,
  variant = 'primary',
  ...props
}) {
  const variants = {
    primary: {
      backgroundColor: 'var(--color-accent)',
      color: 'white',
    },
    secondary: {
      backgroundColor: 'var(--color-bg-tertiary)',
      color: 'var(--color-text-primary)',
      border: '1px solid var(--color-border)',
    },
  }

  return (
    <button
      className={`responsive-button responsive-button-${variant} ${className}`}
      onClick={onClick}
      style={{
        minWidth: '48px',
        minHeight: '48px',
        padding: 'var(--space-3) var(--space-4)',
        borderRadius: 'var(--radius-md)',
        border: 'none',
        fontSize: 'var(--text-sm)',
        fontWeight: 'var(--font-medium)',
        cursor: 'pointer',
        transition: 'opacity 150ms ease, background-color 150ms ease',
        ...variants[variant],
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.opacity = '0.9'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.opacity = '1'
      }}
      {...props}
    >
      {children}
    </button>
  )
}

export default ResponsiveLayout
