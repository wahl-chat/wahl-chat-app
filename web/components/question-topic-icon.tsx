import {
  BriefcaseBusiness,
  Building2,
  Globe2,
  GraduationCap,
  HeartPulse,
  House,
  Landmark,
  Leaf,
  type LucideIcon,
  MessageCircle,
  Monitor,
  Scale,
  ShieldCheck,
  TrainFront,
  UsersRound,
  Wallet,
  Wind,
} from 'lucide-react';

const TOPIC_ICONS: Record<string, LucideIcon> = {
  Wirtschaft: BriefcaseBusiness,
  Löhne: Wallet,
  Lebenshaltung: Wallet,
  Haushalt: Wallet,
  Rente: Wallet,
  Migration: Globe2,
  Internationales: Globe2,
  Energie: Wind,
  Bildung: GraduationCap,
  Wohnen: House,
  Sicherheit: ShieldCheck,
  Katastrophenschutz: ShieldCheck,
  Verwaltung: Landmark,
  Wahl: Landmark,
  Kommunalpolitik: Building2,
  Verkehr: TrainFront,
  Infrastruktur: TrainFront,
  Digitalisierung: Monitor,
  Klima: Leaf,
  Umwelt: Leaf,
  Gesundheit: HeartPulse,
  Soziales: UsersRound,
  Personen: UsersRound,
  Vergleich: Scale,
};

function QuestionTopicIcon({
  topic,
  className,
}: { topic?: string; className?: string }) {
  const Icon = (topic && TOPIC_ICONS[topic]) || MessageCircle;
  return <Icon className={className} aria-hidden="true" strokeWidth={1.7} />;
}

export default QuestionTopicIcon;
