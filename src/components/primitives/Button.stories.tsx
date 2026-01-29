import type { Meta, StoryObj } from '@storybook/react';
import { Heart, Share2, Download } from 'lucide-react';
import Button from './Button';
import type { ButtonExtendedProps } from './Button';

const meta = {
  title: 'Primitives/Button',
  component: Button,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A versatile button component with multiple variants and sizes.',
      },
    },
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'secondary', 'tertiary', 'danger'],
      description: 'Visual style variant',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Button size',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable the button',
    },
    loading: {
      control: 'boolean',
      description: 'Show loading state',
    },
    children: {
      control: 'text',
      description: 'Button label',
    },
  },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Primary button is the main call-to-action
 */
export const Primary: Story = {
  args: {
    variant: 'primary',
    children: 'Click me',
  },
};

/**
 * Secondary button is for secondary actions
 */
export const Secondary: Story = {
  args: {
    variant: 'secondary',
    children: 'Secondary Action',
  },
};

/**
 * Tertiary button is for less prominent actions
 */
export const Tertiary: Story = {
  args: {
    variant: 'tertiary',
    children: 'Tertiary Action',
  },
};

/**
 * Danger button indicates destructive actions
 */
export const Danger: Story = {
  args: {
    variant: 'danger',
    children: 'Delete',
  },
};

/**
 * Small button for compact layouts
 */
export const Small: Story = {
  args: {
    size: 'sm',
    children: 'Small',
  },
};

/**
 * Medium button (default)
 */
export const Medium: Story = {
  args: {
    size: 'md',
    children: 'Medium',
  },
};

/**
 * Large button for prominent actions
 */
export const Large: Story = {
  args: {
    size: 'lg',
    children: 'Large',
  },
};

/**
 * Loading state with spinner
 */
export const Loading: Story = {
  args: {
    loading: true,
    children: 'Loading...',
  },
};

/**
 * Disabled button
 */
export const Disabled: Story = {
  args: {
    disabled: true,
    children: 'Disabled',
  },
};

/**
 * Button with icon on the left
 */
export const WithIconLeft: Story = {
  args: {
    children: 'Like',
    icon: <Heart size={20} />,
  },
};

/**
 * Button with icon on the right
 */
export const WithIconRight: Story = {
  args: {
    children: 'Share',
    icon: <Share2 size={20} />,
    iconRight: true,
  },
};

/**
 * Icon-only button
 */
export const IconOnly: Story = {
  args: {
    icon: <Download size={20} />,
    ariaLabel: 'Download',
  },
};

/**
 * All variants in a row
 */
export const AllVariants: Story = {
  render: () => (
    <div className="flex gap-4 flex-wrap justify-center">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="tertiary">Tertiary</Button>
      <Button variant="danger">Danger</Button>
    </div>
  ),
};

/**
 * All sizes in a row
 */
export const AllSizes: Story = {
  render: () => (
    <div className="flex gap-4 flex-wrap justify-center items-center">
      <Button size="sm">Small</Button>
      <Button size="md">Medium</Button>
      <Button size="lg">Large</Button>
    </div>
  ),
};

/**
 * Accessibility: Focus visible
 */
export const FocusVisible: Story = {
  args: {
    children: 'Focus on me with Tab key',
  },
  parameters: {
    docs: {
      description: {
        story: 'Press Tab to see the focus ring. Buttons support keyboard navigation.',
      },
    },
  },
};

/**
 * Best practices for buttons
 */
export const BestPractices: Story = {
  render: () => (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold mb-2">✓ Do</h3>
        <div className="space-y-2">
          <Button>Clear, descriptive text</Button>
          <Button icon={<Heart size={20} />}>Icon + label</Button>
        </div>
      </div>
      <div>
        <h3 className="font-semibold mb-2">✗ Don't</h3>
        <div className="space-y-2">
          <Button disabled>All caps buttons</Button>
          <Button>Too much padding and text</Button>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Always use clear, action-oriented labels. Provide icons when helpful but not required.',
      },
    },
  },
};
