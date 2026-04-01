import React, { useMemo } from 'react'
import { ChevronDown } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuGroup,
} from '../../../shared/components/ui/dropdown-menu'

/**
 * ModelSelector - Compact pill that opens a provider-grouped dropdown of models.
 *
 * Props:
 *   currentModel  - { id, name, provider } the currently selected model
 *   models        - Array<{ id, name, provider }> available models
 *   onModelChange - (model) => void, called when user picks a model
 *   disabled      - boolean, disables the trigger (e.g. during streaming)
 */
export default function ModelSelector({
  currentModel,
  models = [],
  onModelChange,
  disabled = false,
}) {
  // Group models by provider
  const grouped = useMemo(() => {
    const groups = new Map()
    for (const model of models) {
      const provider = model.provider || 'Other'
      if (!groups.has(provider)) {
        groups.set(provider, [])
      }
      groups.get(provider).push(model)
    }
    return groups
  }, [models])

  const providers = useMemo(() => Array.from(grouped.keys()), [grouped])

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="vc-model-trigger"
          disabled={disabled}
          type="button"
        >
          <span className="vc-model-provider-badge">{currentModel.provider}</span>
          <span className="vc-model-name">{currentModel.name}</span>
          <ChevronDown size={12} className="vc-model-chevron" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="vc-model-dropdown">
        {providers.map((provider, idx) => (
          <React.Fragment key={provider}>
            {idx > 0 && <DropdownMenuSeparator />}
            <DropdownMenuGroup>
              <DropdownMenuLabel>{provider}</DropdownMenuLabel>
              {grouped.get(provider).map((model) => (
                <DropdownMenuItem
                  key={model.id}
                  onSelect={() => onModelChange(model)}
                  className={model.id === currentModel.id ? 'vc-model-item-active' : ''}
                >
                  <span className="vc-model-item-name">{model.name}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
          </React.Fragment>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
