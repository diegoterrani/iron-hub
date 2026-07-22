import {
  Shield,
  Search,
  Crosshair,
  Eye,
  FileSearch,
  Server,
  Film,
  Gamepad2,
  Terminal,
  Monitor,
  Globe,
  type LucideIcon,
} from 'lucide-react';
import type { ServiceCategory } from '../data/services';

const ICONS: Record<ServiceCategory, LucideIcon> = {
  osint: Search,
  'threat-intel': Eye,
  redteam: Crosshair,
  blue: Shield,
  csirt: FileSearch,
  infra: Server,
  content: Film,
  igaming: Gamepad2,
};

export function CategoryIcon({ category, size = 14 }: { category: ServiceCategory; size?: number }) {
  const Icon = ICONS[category] ?? Globe;
  return <Icon size={size} strokeWidth={1.5} />;
}

export function TypeIcon({ type, size = 12 }: { type: string; size?: number }) {
  if (type === 'cli') return <Terminal size={size} strokeWidth={1.5} />;
  if (type === 'desktop') return <Monitor size={size} strokeWidth={1.5} />;
  return <Globe size={size} strokeWidth={1.5} />;
}
