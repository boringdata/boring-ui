import type { Meta, StoryObj } from '@storybook/react';
import Alert from './Alert';

const meta = {
  title: 'Primitives/Alert',
  component: Alert,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A flexible alert component for displaying notifications and messages.',
      },
    },
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['success', 'warning', 'error', 'info'],
      description: 'Alert type',
    },
    title: {
      control: 'text',
      description: 'Alert title',
    },
    description: {
      control: 'text',
      description: 'Alert description',
    },
    dismissible: {
      control: 'boolean',
      description: 'Show close button',
    },
  },
} satisfies Meta<typeof Alert>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Success alert for positive messages
 */
export const Success: Story = {
  args: {
    variant: 'success',
    title: 'Success',
    description: 'Your action was completed successfully.',
  },
};

/**
 * Warning alert for caution messages
 */
export const Warning: Story = {
  args: {
    variant: 'warning',
    title: 'Warning',
    description: 'Please review this information carefully.',
  },
};

/**
 * Error alert for error messages
 */
export const Error: Story = {
  args: {
    variant: 'error',
    title: 'Error',
    description: 'Something went wrong. Please try again.',
  },
};

/**
 * Info alert for informational messages
 */
export const Info: Story = {
  args: {
    variant: 'info',
    title: 'Information',
    description: 'Here is some helpful information.',
  },
};

/**
 * Alert with long description
 */
export const LongDescription: Story = {
  args: {
    variant: 'info',
    title: 'Update Available',
    description:
      'A new version is available. Please update your application to get the latest features, improvements, and security patches.',
  },
};

/**
 * Dismissible alert
 */
export const Dismissible: Story = {
  args: {
    variant: 'success',
    title: 'Success',
    description: 'Click the X button to dismiss this alert.',
    dismissible: true,
  },
};

/**
 * Alert with title only
 */
export const TitleOnly: Story = {
  args: {
    variant: 'warning',
    title: 'Warning',
    dismissible: true,
  },
};

/**
 * Alert with custom content
 */
export const CustomContent: Story = {
  args: {
    variant: 'info',
    title: 'Custom Content',
    children: (
      <div>
        <p>You can pass custom React components as children.</p>
        <ul className="list-disc list-inside mt-2">
          <li>Feature one</li>
          <li>Feature two</li>
          <li>Feature three</li>
        </ul>
      </div>
    ),
  },
};

/**
 * All alert types
 */
export const AllTypes: Story = {
  render: () => (
    <div className="w-full max-w-md space-y-4">
      <Alert variant="success" title="Success" description="Operation completed." />
      <Alert variant="warning" title="Warning" description="Please be careful." />
      <Alert variant="error" title="Error" description="Something failed." />
      <Alert variant="info" title="Info" description="Here is some information." />
    </div>
  ),
};

/**
 * Accessibility best practices
 */
export const Accessibility: Story = {
  args: {
    variant: 'warning',
    title: 'Accessibility First',
    description: 'Alerts use role="alert" and semantic HTML for screen readers.',
  },
  parameters: {
    docs: {
      description: {
        story: 'Alerts automatically have role="alert" to announce to assistive technologies.',
      },
    },
    a11y: {
      config: {
        rules: [
          {
            id: 'color-contrast',
            enabled: true,
          },
        ],
      },
    },
  },
};

/**
 * Do's and Don'ts
 */
export const BestPractices: Story = {
  render: () => (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold mb-2">✓ Do</h3>
        <Alert variant="success" title="Clear and concise" description="Keep messages short and actionable." dismissible />
      </div>
      <div>
        <h3 className="font-semibold mb-2">✗ Don't</h3>
        <Alert
          variant="error"
          title="Don't use multiple alerts"
          description="Too many alerts can overwhelm the user. Use them sparingly."
          dismissible
        />
      </div>
    </div>
  ),
};
