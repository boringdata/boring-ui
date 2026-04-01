import React, { useCallback } from 'react'
import {
  ChevronRight,
  BarChart3,
  FileCode,
  FileText,
  Table2,
  Image,
  Globe,
  Code2,
  File,
} from 'lucide-react'

/**
 * Icon registry for artifact kinds.
 */
const KIND_ICONS = {
  chart: BarChart3,
  code: Code2,
  document: FileText,
  table: Table2,
  image: Image,
  web: Globe,
  file: FileCode,
  default: File,
}

function resolveArtifactIconName(iconName, kind) {
  if (KIND_ICONS[iconName]) return iconName
  if (KIND_ICONS[kind]) return kind
  return 'default'
}

function ArtifactGlyph({ iconName, kind }) {
  switch (resolveArtifactIconName(iconName, kind)) {
    case 'chart':
      return <BarChart3 size={16} />
    case 'code':
      return <Code2 size={16} />
    case 'document':
      return <FileText size={16} />
    case 'table':
      return <Table2 size={16} />
    case 'image':
      return <Image size={16} />
    case 'web':
      return <Globe size={16} />
    case 'file':
      return <FileCode size={16} />
    default:
      return <File size={16} />
  }
}

/**
 * ArtifactCard - Clickable card representing an artifact in the chat timeline.
 * Three visual states: default, open, active.
 *
 * Props:
 *   artifact - { title, kind, icon }
 *   state    - 'default' | 'open' | 'active'
 *   onOpen   - (artifact) => void
 */
export default function ArtifactCard({ artifact, state = 'default', onOpen }) {
  const handleClick = useCallback(() => {
    if (onOpen) {
      onOpen(artifact)
    }
  }, [onOpen, artifact])

  const stateClass =
    state === 'active' ? ' active' : state === 'open' ? ' open' : ''

  return (
    <button
      className={`vc-artifact-card${stateClass}`}
      data-testid="artifact-card"
      onClick={handleClick}
      type="button"
    >
      <div className="vc-artifact-card-icon">
        <ArtifactGlyph iconName={artifact.icon} kind={artifact.kind} />
      </div>
      <div className="vc-artifact-card-info">
        <span className="vc-artifact-card-title">{artifact.title}</span>
        <span className="vc-artifact-card-kind">{artifact.kind}</span>
      </div>
      <div className="vc-artifact-card-spacer" />
      <div className="vc-artifact-card-chevron" data-testid="artifact-chevron">
        <ChevronRight size={14} />
      </div>
    </button>
  )
}
