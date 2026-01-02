import { type LucideIcon } from 'lucide-react';
import {
    Card,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';

interface ConversationChoiceCardProps {
    icon: LucideIcon;
    title: string;
    description: string;
    onClick?: () => void;
    variant?: 'primary' | 'secondary';
    className?: string;
}

export function ConversationChoiceCard({
    icon: Icon,
    title,
    description,
    onClick,
    className = '',
}: ConversationChoiceCardProps) {

    return (
        <Card
            className={`border-2 transition-all ${isPrimary
                    ? 'cursor-pointer hover:border-primary hover:shadow-md'
                    : ''
                } ${className}`}
            onClick={onClick}
        >
            <CardHeader className="items-center py-6">
                <div className="flex items-center gap-3">
                    <div
                        className={`flex size-12 items-center justify-center rounded-full ${isPrimary
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-muted text-muted-foreground'
                            }`}
                    >
                        <Icon className="size-6" />
                    </div>
                    <div className="text-left">
                        <CardTitle className="text-lg">{title}</CardTitle>
                        <CardDescription>{description}</CardDescription>
                    </div>
                </div>
            </CardHeader>
        </Card>
    );
}

