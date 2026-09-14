import { socialMediaConfig } from '@/lib/contact-config';
import { cn } from '@/lib/utils';
import { MailIcon } from 'lucide-react';
import Link from 'next/link';
import InstagramIcon from './instagram-icon';
import LinkedInIcon from './linkedin-icon';
import XIcon from './x-icon';

type Props = {
  type: keyof typeof socialMediaConfig;
  /** Overrides the default size-9, e.g. for the compact footer row. */
  className?: string;
};

function HomeSocialMediaIcon({ type, className }: Props) {
  let Icon: React.ElementType;

  switch (type) {
    case 'instagram':
      Icon = InstagramIcon;
      break;
    case 'linkedin':
      Icon = LinkedInIcon;
      break;
    case 'x':
      Icon = XIcon;
      break;
    case 'email':
      Icon = MailIcon;
      break;
  }

  return (
    <Link
      href={socialMediaConfig[type]}
      target="_blank"
      className="transition-transform duration-200 ease-out hover:scale-110"
    >
      <Icon className={cn('size-9', className)} />
    </Link>
  );
}

export default HomeSocialMediaIcon;
