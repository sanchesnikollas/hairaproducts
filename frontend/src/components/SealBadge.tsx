import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface SealBadgeProps {
  seal: string;
  className?: string;
}

const sealLabels: Record<string, string> = {
  sulfate_free: 'Sulfate Free',
  paraben_free: 'Paraben Free',
  silicone_free: 'Silicone Free',
  petrolatum_free: 'Petrolatum Free',
  dye_free: 'Dye Free',
  vegan: 'Vegan',
  natural: 'Natural',
  organic: 'Organic',
  cruelty_free: 'Cruelty Free',
  low_poo: 'Low Poo',
  no_poo: 'No Poo',
  thermal_protection: 'Thermal Protection',
  dermatologically_tested: 'Dermatologically Tested',
};

function getSealLabel(seal: string): string {
  if (sealLabels[seal]) return sealLabels[seal];
  return seal
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

const greenSeals = new Set([
  'sulfate_free',
  'paraben_free',
  'silicone_free',
  'petrolatum_free',
  'dye_free',
]);

const blueSeals = new Set(['vegan', 'natural', 'organic', 'cruelty_free']);
const amberSeals = new Set(['low_poo', 'no_poo']);

function getSealClassName(seal: string): string {
  if (greenSeals.has(seal)) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (blueSeals.has(seal)) {
    return 'border-blue-200 bg-blue-50 text-blue-700';
  }
  if (amberSeals.has(seal)) {
    return 'border-amber-200 bg-amber-50 text-amber-700';
  }
  if (seal === 'thermal_protection') {
    return 'border-orange-200 bg-orange-50 text-orange-700';
  }
  if (seal === 'dermatologically_tested') {
    return 'border-violet-200 bg-violet-50 text-violet-700';
  }
  return 'border-gray-200 bg-gray-50 text-gray-600';
}

export default function SealBadge({ seal, className }: SealBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(
        'text-[11px] h-auto px-2 py-0.5 font-medium tracking-wide',
        getSealClassName(seal),
        className
      )}
    >
      {getSealLabel(seal)}
    </Badge>
  );
}
