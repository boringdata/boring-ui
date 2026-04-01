import { Sun, Moon } from 'lucide-react'
import { useTheme } from '../hooks/useTheme'
import { Button } from './ui/button'

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
      className="theme-toggle"
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? (
        <Sun size={16} />
      ) : (
        <Moon size={16} />
      )}
    </Button>
  )
}
