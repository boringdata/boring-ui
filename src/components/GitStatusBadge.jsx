import React from 'react';
import PropTypes from 'prop-types';
import { useGitStatus, getFileStatus, getStatusConfig, STATUS_CONFIG } from '../hooks/useGitStatus';

/**
 * Small badge component showing git status for a file
 *
 * @param {object} props
 * @param {string} [props.path] - File path to show status for (required if not using statusCode)
 * @param {string} [props.statusCode] - Direct status code to display (bypasses hook)
 * @param {boolean} [props.showLabel] - Whether to show the status label
 * @param {'small' | 'medium'} [props.size] - Badge size
 * @param {string} [props.className] - Additional CSS class
 * @param {object} [props.style] - Additional inline styles
 *
 * @example
 * ```jsx
 * // With automatic status fetching
 * <GitStatusBadge path="src/App.jsx" />
 *
 * // With direct status code
 * <GitStatusBadge statusCode="M" />
 *
 * // With label
 * <GitStatusBadge statusCode="A" showLabel />
 *
 * // Small size (default)
 * <GitStatusBadge statusCode="M" size="small" />
 * ```
 */
export default function GitStatusBadge({
  path,
  statusCode: directStatusCode,
  showLabel = false,
  size = 'small',
  className = '',
  style = {},
}) {
  // Only use the hook if we need to fetch status for a path
  const { status, loading } = useGitStatus({
    path,
    polling: !directStatusCode && !!path, // Only poll if using path-based status
  });

  // Determine the status code to display
  let statusCode = directStatusCode;
  if (!statusCode && path && status) {
    statusCode = getFileStatus(status, path);
  }

  // Get config for the status
  const config = getStatusConfig(statusCode);

  // Don't render if no status or loading with no fallback
  if (!config) {
    if (loading && path && !directStatusCode) {
      return (
        <span
          className={`git-status-badge git-status-badge-loading ${className}`}
          style={{
            ...baseStyles,
            ...sizeStyles[size],
            backgroundColor: 'var(--git-status-loading-bg, #3a3f4b)',
            color: 'var(--git-status-loading-color, #6b7280)',
            ...style,
          }}
        >
          ...
        </span>
      );
    }
    return null;
  }

  return (
    <span
      className={`git-status-badge ${config.className} git-status-badge-${size} ${className}`}
      title={config.label}
      style={{
        ...baseStyles,
        ...sizeStyles[size],
        backgroundColor: `${config.color}20`,
        color: config.color,
        borderColor: `${config.color}40`,
        ...style,
      }}
    >
      <span className="git-status-badge-code">{statusCode}</span>
      {showLabel && (
        <span className="git-status-badge-label">{config.label}</span>
      )}
    </span>
  );
}

// Base styles for the badge
const baseStyles = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontFamily: 'var(--font-mono, monospace)',
  fontWeight: 600,
  borderRadius: '3px',
  border: '1px solid',
  gap: '4px',
  lineHeight: 1,
  whiteSpace: 'nowrap',
};

// Size variants
const sizeStyles = {
  small: {
    fontSize: '10px',
    padding: '1px 4px',
    minWidth: '16px',
    height: '16px',
  },
  medium: {
    fontSize: '12px',
    padding: '2px 6px',
    minWidth: '20px',
    height: '20px',
  },
};

GitStatusBadge.propTypes = {
  path: PropTypes.string,
  statusCode: PropTypes.oneOf(['M', 'A', 'D', 'U', '?', 'R', 'C']),
  showLabel: PropTypes.bool,
  size: PropTypes.oneOf(['small', 'medium']),
  className: PropTypes.string,
  style: PropTypes.object,
};

/**
 * Inline status indicator (just the letter, minimal styling)
 * Useful for file tree items where space is limited
 */
export function GitStatusIndicator({ statusCode, className = '', style = {} }) {
  const config = getStatusConfig(statusCode);
  if (!config) return null;

  return (
    <span
      className={`git-status-indicator ${config.className} ${className}`}
      title={config.label}
      style={{
        color: config.color,
        fontFamily: 'var(--font-mono, monospace)',
        fontSize: '10px',
        fontWeight: 600,
        marginLeft: '4px',
        ...style,
      }}
    >
      {statusCode}
    </span>
  );
}

GitStatusIndicator.propTypes = {
  statusCode: PropTypes.oneOf(['M', 'A', 'D', 'U', '?', 'R', 'C']).isRequired,
  className: PropTypes.string,
  style: PropTypes.object,
};

/**
 * Export STATUS_CONFIG for consumers who need it
 */
export { STATUS_CONFIG };
