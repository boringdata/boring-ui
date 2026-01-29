/**
 * DockLayout - Declarative wrapper for dockview-react
 *
 * Provides a simplified, declarative API for creating dock layouts with:
 * - Panel configuration via props
 * - Automatic layout persistence
 * - Sensible defaults for common layouts
 * - Layout API exposure via ref or callback
 */

import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState, forwardRef } from 'react';
import { DockviewReact } from 'dockview-react';
import 'dockview-react/dist/styles/dockview.css';

import { useConfig } from '../config/ConfigProvider';
import { getJSON, setJSON, getStorageKey } from '../utils/storage';

/**
 * Default panel positions for common layouts
 */
const DEFAULT_POSITIONS = {
  left: { direction: 'left' },
  right: { direction: 'right' },
  top: { direction: 'above' },
  bottom: { direction: 'below' },
  center: {}, // Default position (will be placed in center)
};

/**
 * Layout version - increment to force reset on breaking changes
 */
const LAYOUT_VERSION = 1;

/**
 * Validate saved layout structure
 * @param {object} layout - Saved layout object
 * @param {string[]} requiredPanels - Array of panel IDs that must exist
 * @returns {boolean} True if layout is valid
 */
function validateLayout(layout, requiredPanels = []) {
  if (!layout?.grid || !layout?.panels) return false;

  const panelIds = Object.keys(layout.panels);

  // Check all required panels exist
  for (const requiredId of requiredPanels) {
    if (!panelIds.includes(requiredId)) {
      console.warn(`[DockLayout] Missing required panel: ${requiredId}`);
      return false;
    }
  }

  return true;
}

/**
 * Load layout from localStorage
 * @param {string} storageKey - Full storage key
 * @param {string[]} requiredPanels - Panels that must exist in saved layout
 * @returns {object|null} Saved layout or null
 */
function loadLayout(storageKey, requiredPanels) {
  try {
    const saved = getJSON(storageKey, null);
    if (!saved) return null;

    // Check version
    if (!saved.version || saved.version < LAYOUT_VERSION) {
      console.info('[DockLayout] Layout version outdated, resetting');
      return null;
    }

    // Validate structure
    if (!validateLayout(saved, requiredPanels)) {
      console.info('[DockLayout] Layout validation failed, resetting');
      return null;
    }

    return saved;
  } catch (e) {
    console.warn('[DockLayout] Failed to load layout:', e);
    return null;
  }
}

/**
 * Save layout to localStorage
 * @param {string} storageKey - Full storage key
 * @param {object} layout - Layout to save
 */
function saveLayout(storageKey, layout) {
  try {
    const layoutWithVersion = { ...layout, version: LAYOUT_VERSION };
    setJSON(storageKey, layoutWithVersion);
  } catch (e) {
    console.warn('[DockLayout] Failed to save layout:', e);
  }
}

/**
 * Create initial panels from configuration
 * @param {object} api - Dockview API
 * @param {Array} panels - Panel configurations
 * @param {object} components - Available components map
 */
function createPanelsFromConfig(api, panels, components) {
  if (!panels?.length) return;

  const createdPanels = new Map();

  // First pass: create panels that don't reference others
  const deferredPanels = [];

  for (const panelConfig of panels) {
    const {
      id,
      component,
      title,
      position = 'center',
      params = {},
      tabComponent,
      locked = false,
      hideHeader = false,
    } = panelConfig;

    // Skip if component doesn't exist
    if (!components[component]) {
      console.warn(`[DockLayout] Unknown component: ${component}`);
      continue;
    }

    // Check if position references another panel
    const positionConfig = typeof position === 'string'
      ? DEFAULT_POSITIONS[position] || {}
      : position;

    const referencesPanel = positionConfig.referencePanel && !createdPanels.has(positionConfig.referencePanel);
    const referencesGroup = positionConfig.referenceGroup;

    if (referencesPanel || referencesGroup) {
      deferredPanels.push(panelConfig);
      continue;
    }

    // Create the panel
    const panel = api.addPanel({
      id,
      component,
      title: title || id,
      position: positionConfig,
      params,
      tabComponent,
    });

    if (panel) {
      createdPanels.set(id, panel);

      // Apply group settings
      if (panel.group) {
        if (locked) {
          panel.group.locked = true;
        }
        if (hideHeader) {
          panel.group.header.hidden = true;
        }
      }
    }
  }

  // Second pass: create deferred panels
  for (const panelConfig of deferredPanels) {
    const {
      id,
      component,
      title,
      position,
      params = {},
      tabComponent,
      locked = false,
      hideHeader = false,
    } = panelConfig;

    let positionConfig = typeof position === 'string'
      ? DEFAULT_POSITIONS[position] || {}
      : { ...position };

    // Resolve panel reference
    if (positionConfig.referencePanel) {
      const refPanel = createdPanels.get(positionConfig.referencePanel) || api.getPanel(positionConfig.referencePanel);
      if (!refPanel) {
        console.warn(`[DockLayout] Reference panel not found: ${positionConfig.referencePanel}`);
        positionConfig = {};
      }
    }

    // Resolve group reference
    if (positionConfig.referenceGroup && typeof positionConfig.referenceGroup === 'string') {
      const refPanel = createdPanels.get(positionConfig.referenceGroup) || api.getPanel(positionConfig.referenceGroup);
      if (refPanel?.group) {
        positionConfig.referenceGroup = refPanel.group;
      } else {
        console.warn(`[DockLayout] Reference group not found: ${positionConfig.referenceGroup}`);
        delete positionConfig.referenceGroup;
      }
    }

    const panel = api.addPanel({
      id,
      component,
      title: title || id,
      position: positionConfig,
      params,
      tabComponent,
    });

    if (panel) {
      createdPanels.set(id, panel);

      if (panel.group) {
        if (locked) {
          panel.group.locked = true;
        }
        if (hideHeader) {
          panel.group.header.hidden = true;
        }
      }
    }
  }

  return createdPanels;
}

/**
 * DockLayout Component
 *
 * @param {object} props
 * @param {Array} props.panels - Array of panel configurations
 * @param {object} [props.components] - Map of component names to React components
 * @param {object} [props.tabComponents] - Map of tab component names to React components
 * @param {object} [props.defaultLayout] - Default layout to use if no saved layout exists
 * @param {function} [props.onLayoutChange] - Callback when layout changes
 * @param {function} [props.onReady] - Callback when dockview is ready, receives the API
 * @param {string} [props.storageKey='layout'] - Storage key suffix for persistence
 * @param {string} [props.className] - Additional CSS classes
 * @param {boolean} [props.persistLayout=true] - Whether to persist layout to storage
 * @param {React.Component} [props.rightHeaderActionsComponent] - Component for right header actions
 * @param {function} [props.showDndOverlay] - Function to determine if DnD overlay should show
 * @param {function} [props.onDidDrop] - Callback when something is dropped on the layout
 * @param {object} ref - Forwarded ref exposing layout API
 */
const DockLayout = forwardRef(function DockLayout(
  {
    panels = [],
    components = {},
    tabComponents = {},
    defaultLayout,
    onLayoutChange,
    onReady,
    storageKey = 'layout',
    className = '',
    persistLayout = true,
    rightHeaderActionsComponent,
    showDndOverlay,
    onDidDrop,
  },
  ref
) {
  const [api, setApi] = useState(null);
  const isInitialized = useRef(false);
  const layoutRestored = useRef(false);
  const panelsRef = useRef(panels);
  const onLayoutChangeRef = useRef(onLayoutChange);

  // Get storage prefix from config
  let storagePrefix;
  try {
    const config = useConfig();
    storagePrefix = config?.storage?.prefix || 'myapp';
  } catch {
    // If not in ConfigProvider context, use default
    storagePrefix = 'myapp';
  }

  // Full storage key with prefix
  const fullStorageKey = useMemo(
    () => `${storagePrefix}-${storageKey}`,
    [storagePrefix, storageKey]
  );

  // Update refs when props change
  useEffect(() => {
    panelsRef.current = panels;
  }, [panels]);

  useEffect(() => {
    onLayoutChangeRef.current = onLayoutChange;
  }, [onLayoutChange]);

  // Required panel IDs for validation
  const requiredPanelIds = useMemo(
    () => panels.filter((p) => p.required).map((p) => p.id),
    [panels]
  );

  // Expose API via ref
  useImperativeHandle(
    ref,
    () => ({
      /**
       * Get the underlying dockview API
       */
      getApi: () => api,

      /**
       * Add a panel dynamically
       */
      addPanel: (panelConfig) => {
        if (!api) return null;

        const {
          id,
          component,
          title,
          position = 'center',
          params = {},
          tabComponent,
        } = panelConfig;

        const positionConfig = typeof position === 'string'
          ? DEFAULT_POSITIONS[position] || {}
          : position;

        return api.addPanel({
          id,
          component,
          title: title || id,
          position: positionConfig,
          params,
          tabComponent,
        });
      },

      /**
       * Remove a panel by ID
       */
      removePanel: (panelId) => {
        if (!api) return false;
        const panel = api.getPanel(panelId);
        if (panel) {
          panel.api.close();
          return true;
        }
        return false;
      },

      /**
       * Get a panel by ID
       */
      getPanel: (panelId) => {
        return api?.getPanel(panelId);
      },

      /**
       * Get all panels
       */
      getPanels: () => {
        return api?.panels || [];
      },

      /**
       * Get the active panel
       */
      getActivePanel: () => {
        return api?.activePanel;
      },

      /**
       * Set a panel as active
       */
      setActivePanel: (panelId) => {
        const panel = api?.getPanel(panelId);
        if (panel) {
          panel.api.setActive();
          return true;
        }
        return false;
      },

      /**
       * Update panel parameters
       */
      updatePanelParams: (panelId, params) => {
        const panel = api?.getPanel(panelId);
        if (panel) {
          panel.api.updateParameters(params);
          return true;
        }
        return false;
      },

      /**
       * Get current layout as JSON
       */
      toJSON: () => {
        return api?.toJSON();
      },

      /**
       * Restore layout from JSON
       */
      fromJSON: (layout) => {
        if (api && typeof api.fromJSON === 'function') {
          api.fromJSON(layout);
          return true;
        }
        return false;
      },

      /**
       * Reset layout to default
       */
      resetLayout: () => {
        if (!api) return false;

        // Clear all panels
        const allPanels = [...(api.panels || [])];
        allPanels.forEach((panel) => {
          try {
            panel.api.close();
          } catch {
            // Ignore errors when closing panels
          }
        });

        // Recreate from config
        createPanelsFromConfig(api, panelsRef.current, components);
        return true;
      },

      /**
       * Clear saved layout from storage
       */
      clearSavedLayout: () => {
        if (persistLayout) {
          try {
            localStorage.removeItem(getStorageKey(fullStorageKey));
          } catch {
            // Ignore storage errors
          }
        }
      },
    }),
    [api, components, persistLayout, fullStorageKey]
  );

  // Handle dockview ready
  const handleReady = useCallback(
    (event) => {
      const dockApi = event.api;
      setApi(dockApi);

      // Check for saved layout
      let hasSavedLayout = false;
      if (persistLayout) {
        const savedLayout = loadLayout(fullStorageKey, requiredPanelIds);
        if (savedLayout) {
          hasSavedLayout = true;
          try {
            dockApi.fromJSON(savedLayout);
            layoutRestored.current = true;
          } catch (e) {
            console.warn('[DockLayout] Failed to restore layout:', e);
            hasSavedLayout = false;
          }
        }
      }

      // If no saved layout, use default or create from config
      if (!hasSavedLayout) {
        if (defaultLayout) {
          try {
            dockApi.fromJSON(defaultLayout);
            layoutRestored.current = true;
          } catch (e) {
            console.warn('[DockLayout] Failed to apply default layout:', e);
          }
        }

        // Create panels from config if not restored from layout
        if (!layoutRestored.current) {
          createPanelsFromConfig(dockApi, panels, components);
        }
      }

      // Set up layout persistence
      if (persistLayout && typeof dockApi.onDidLayoutChange === 'function') {
        dockApi.onDidLayoutChange(() => {
          if (typeof dockApi.toJSON === 'function') {
            saveLayout(fullStorageKey, dockApi.toJSON());
          }

          // Call user's onLayoutChange callback
          if (onLayoutChangeRef.current && typeof dockApi.toJSON === 'function') {
            onLayoutChangeRef.current(dockApi.toJSON());
          }
        });
      }

      // Save on page unload
      if (persistLayout) {
        const handleBeforeUnload = () => {
          if (typeof dockApi.toJSON === 'function') {
            saveLayout(fullStorageKey, dockApi.toJSON());
          }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
      }

      isInitialized.current = true;

      // Call user's onReady callback
      if (onReady) {
        onReady(dockApi);
      }
    },
    [
      panels,
      components,
      defaultLayout,
      onReady,
      persistLayout,
      fullStorageKey,
      requiredPanelIds,
    ]
  );

  // Build className
  const dockClassName = ['dockview-theme-abyss', className].filter(Boolean).join(' ');

  return (
    <DockviewReact
      className={dockClassName}
      components={components}
      tabComponents={tabComponents}
      rightHeaderActionsComponent={rightHeaderActionsComponent}
      onReady={handleReady}
      showDndOverlay={showDndOverlay}
      onDidDrop={onDidDrop}
    />
  );
});

export default DockLayout;

/**
 * Common layout presets
 */
export const LayoutPresets = {
  /**
   * Three-column layout with left sidebar, center content, and right sidebar
   */
  threeColumn: (leftPanel, centerPanel, rightPanel) => [
    { ...leftPanel, position: 'left' },
    { ...centerPanel, position: 'center' },
    { ...rightPanel, position: { direction: 'right', referencePanel: centerPanel.id } },
  ],

  /**
   * Two-column layout with sidebar and main content
   */
  sidebarMain: (sidebarPanel, mainPanel, sidebarPosition = 'left') => [
    { ...sidebarPanel, position: sidebarPosition },
    { ...mainPanel, position: sidebarPosition === 'left' ? 'right' : 'left' },
  ],

  /**
   * IDE-like layout with file tree, editor, and terminal
   */
  ide: (fileTreeComponent, editorComponent, terminalComponent) => [
    {
      id: 'filetree',
      component: fileTreeComponent,
      title: 'Files',
      position: 'left',
      locked: true,
      hideHeader: true,
    },
    {
      id: 'editor',
      component: editorComponent,
      title: '',
      position: { direction: 'right', referencePanel: 'filetree' },
    },
    {
      id: 'terminal',
      component: terminalComponent,
      title: 'Terminal',
      position: { direction: 'below', referencePanel: 'editor' },
    },
  ],
};
