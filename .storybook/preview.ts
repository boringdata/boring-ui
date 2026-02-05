import type { Preview } from '@storybook/react';
import { themes } from '@storybook/theming';
import { INITIAL_VIEWPORTS } from '@storybook/addon-viewport';
import '../src/front/styles.css';

const preview: Preview = {
  parameters: {
    // Dark mode setup
    darkMode: {
      dark: { ...themes.dark },
      light: { ...themes.light },
    },

    // Viewport settings
    viewport: {
      viewports: {
        ...INITIAL_VIEWPORTS,
        mobile: {
          name: 'Mobile',
          styles: {
            width: '375px',
            height: '667px',
          },
          type: 'mobile',
        },
        tablet: {
          name: 'Tablet',
          styles: {
            width: '768px',
            height: '1024px',
          },
          type: 'tablet',
        },
      },
    },

    // Accessibility testing
    a11y: {
      config: {
        rules: [
          {
            id: 'color-contrast',
            enabled: true,
          },
          {
            id: 'valid-aria-role',
            enabled: true,
          },
        ],
      },
    },

    // Actions
    actions: {
      argTypesRegex: '^on[A-Z].*',
    },

    // Controls
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },

    // Layout
    layout: 'centered',

    // Stories
    docs: {
      description: {
        component: 'Component documentation and examples',
      },
    },
  },

  // Global decorators
  decorators: [
    (Story) => (
      <div className="p-4">
        <Story />
      </div>
    ),
  ],
};

export default preview;
