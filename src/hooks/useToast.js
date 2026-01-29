import { useContext } from 'react';
import { ToastContext } from '../context/ToastContext';

/**
 * useToast Hook
 * Provides easy access to toast notifications
 *
 * @returns {Object} Toast API
 *
 * @example
 * ```jsx
 * function MyComponent() {
 *   const toast = useToast();
 *
 *   const handleSave = async () => {
 *     try {
 *       await saveData();
 *       toast.success('Saved', 'Your changes have been saved');
 *     } catch (error) {
 *       toast.error('Error', error.message);
 *     }
 *   };
 *
 *   return <button onClick={handleSave}>Save</button>;
 * }
 * ```
 */
export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error(
      'useToast must be used within a ToastProvider. ' +
      'Make sure your component is wrapped with <ToastProvider>'
    );
  }

  return context;
}

export default useToast;
