import fs from 'node:fs'
import path from 'node:path'
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { cn } from '../lib/utils'
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar'
import { Badge, badgeVariants } from '../components/ui/badge'
import { Button, buttonVariants } from '../components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select'
import { Separator } from '../components/ui/separator'
import { Switch } from '../components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import { Textarea } from '../components/ui/textarea'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip'

const repoRoot = path.resolve(__dirname, '../../..')
const readRepoFile = (relativePath) => fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')

describe('Shadcn Foundation Contract', () => {
  it('keeps the initial primitive import surface available', () => {
    const primitives = [
      Button,
      buttonVariants,
      Badge,
      badgeVariants,
      Dialog,
      DialogTrigger,
      DialogContent,
      DialogHeader,
      DialogFooter,
      DialogTitle,
      DialogDescription,
      DropdownMenu,
      DropdownMenuTrigger,
      DropdownMenuContent,
      DropdownMenuItem,
      DropdownMenuCheckboxItem,
      DropdownMenuRadioGroup,
      DropdownMenuRadioItem,
      DropdownMenuLabel,
      DropdownMenuSeparator,
      DropdownMenuSub,
      DropdownMenuSubTrigger,
      DropdownMenuSubContent,
      Input,
      Textarea,
      Select,
      SelectTrigger,
      SelectContent,
      SelectItem,
      SelectValue,
      Label,
      Switch,
      Tooltip,
      TooltipTrigger,
      TooltipContent,
      TooltipProvider,
      Avatar,
      AvatarImage,
      AvatarFallback,
      Tabs,
      TabsList,
      TabsTrigger,
      TabsContent,
      Separator,
    ]

    primitives.forEach((primitive) => {
      expect(primitive).toBeDefined()
    })
  })

  it('keeps cn() class composition behavior deterministic', () => {
    const merged = cn('p-2 text-sm', 'p-4', null)
    expect(merged).toContain('p-4')
    expect(merged).not.toContain('p-2')
    expect(merged).toContain('text-sm')
  })

  it('keeps shadcn button variant behavior and asChild wrapper behavior', () => {
    const { rerender } = render(<Button variant="destructive">Delete</Button>)
    const button = screen.getByRole('button', { name: 'Delete' })
    expect(button.className).toContain('bg-destructive')

    rerender(
      <Button asChild>
        <a href="/docs">Docs</a>
      </Button>
    )
    const link = screen.getByRole('link', { name: 'Docs' })
    expect(link.className).toContain('inline-flex')
  })

  it('keeps token and tailwind semantic bridges for shadcn primitives', () => {
    const tokens = readRepoFile('src/front/styles/tokens.css')
    const tailwindConfig = readRepoFile('tailwind.config.js')

    const requiredTokenVars = [
      '--background',
      '--foreground',
      '--primary',
      '--primary-foreground',
      '--secondary',
      '--secondary-foreground',
      '--muted',
      '--muted-foreground',
      '--accent',
      '--accent-foreground',
      '--destructive',
      '--destructive-foreground',
      '--border',
      '--input',
      '--ring',
      '--radius',
    ]

    requiredTokenVars.forEach((tokenVar) => {
      expect(tokens).toContain(tokenVar)
    })

    const requiredTailwindMappings = [
      "background: 'var(--background)'",
      "foreground: 'var(--foreground)'",
      "primary: 'var(--primary)'",
      "'primary-foreground': 'var(--primary-foreground)'",
      "secondary: 'var(--secondary)'",
      "'secondary-foreground': 'var(--secondary-foreground)'",
      "muted: 'var(--muted)'",
      "'muted-foreground': 'var(--muted-foreground)'",
      "accent: 'var(--accent)'",
      "'accent-foreground': 'var(--accent-foreground)'",
      "destructive: 'var(--destructive)'",
      "'destructive-foreground': 'var(--destructive-foreground)'",
      "border: 'var(--border)'",
      "input: 'var(--input)'",
      "ring: 'var(--ring)'",
    ]

    requiredTailwindMappings.forEach((mapping) => {
      expect(tailwindConfig).toContain(mapping)
    })
  })
})
