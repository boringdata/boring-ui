import type { Meta, StoryObj } from '@storybook/react';
import Spinner from './Spinner';

const meta = {
  title: 'Primitives/Spinner',
  component: Spinner,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A loading spinner component with multiple sizes and colors.',
      },
    },
  },
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Spinner size',
    },
    color: {
      control: 'select',
      options: ['primary', 'success', 'warning', 'error', 'info', 'muted'],
      description: 'Spinner color',
    },
    label: {
      control: 'text',
      description: 'Accessibility label',
    },
  },
} satisfies Meta<typeof Spinner>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Small spinner
 */
export const Small: Story = {
  args: {
    size: 'sm',
    label: 'Loading',
  },
};

/**
 * Medium spinner (default)
 */
export const Medium: Story = {
  args: {
    size: 'md',
    label: 'Loading',
  },
};

/**
 * Large spinner
 */
export const Large: Story = {
  args: {
    size: 'lg',
    label: 'Loading',
  },
};

/**
 * Primary color
 */
export const Primary: Story = {
  args: {
    color: 'primary',
    label: 'Loading',
  },
};

/**
 * Success color
 */
export const Success: Story = {
  args: {
    color: 'success',
    label: 'Processing',
  },
};

/**
 * Warning color
 */
export const Warning: Story = {
  args: {
    color: 'warning',
    label: 'Loading',
  },
};

/**
 * Error color
 */
export const Error: Story = {
  args: {
    color: 'error',
    label: 'Error',
  },
};

/**
 * Info color
 */
export const Info: Story = {
  args: {
    color: 'info',
    label: 'Loading',
  },
};

/**
 * Muted color for secondary loading states
 */
export const Muted: Story = {
  args: {
    color: 'muted',
    label: 'Loading',
  },
};

/**
 * All sizes comparison
 */
export const AllSizes: Story = {
  render: () => (
    <div className="flex gap-8 items-center">
      <Spinner size="sm" label="Small" />
      <Spinner size="md" label="Medium" />
      <Spinner size="lg" label="Large" />
    </div>
  ),
};

/**
 * All colors comparison
 */
export const AllColors: Story = {
  render: () => (
    <div className="flex gap-8 items-center flex-wrap">
      <Spinner color="primary" label="Primary" />
      <Spinner color="success" label="Success" />
      <Spinner color="warning" label="Warning" />
      <Spinner color="error" label="Error" />
      <Spinner color="info" label="Info" />
      <Spinner color="muted" label="Muted" />
    </div>
  ),
};

/**
 * Loading overlay pattern
 */
export const LoadingOverlay: Story = {
  render: () => (
    <div className="relative w-64 h-40 border-2 border-dashed border-foreground/20 rounded-lg">
      <div className="absolute inset-0 bg-background/50 flex items-center justify-center rounded-lg">
        <div className="text-center">
          <Spinner size="md" label="Loading data" />
          <p className="text-sm text-foreground/60 mt-2">Loading...</p>
        </div>
      </div>
    </div>
  ),
};

/**
 * Accessibility
 */
export const Accessibility: Story = {
  args: {
    label: 'Please wait while we load your data',
  },
  parameters: {
    docs: {
      description: {
        story: 'Spinners have role="status" and aria-label for screen reader support.',
      },
    },
  },
};

/**
 * Best practices
 */
export const BestPractices: Story = {
  render: () => (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold mb-2">✓ Do</h3>
        <div className="space-y-2">
          <div>
            <Spinner size="md" />
            <p className="text-sm text-foreground/60 mt-2">Provide context text</p>
          </div>
          <div>
            <Spinner color="primary" size="md" />
            <p className="text-sm text-foreground/60 mt-2">Use appropriate color</p>
          </div>
        </div>
      </div>
      <div>
        <h3 className="font-semibold mb-2">✗ Don't</h3>
        <div className="space-y-2">
          <div>
            <Spinner color="muted" size="sm" />
            <p className="text-sm text-foreground/60 mt-2">Don't make spinners too small</p>
          </div>
        </div>
      </div>
    </div>
  ),
};
