import { socialMediaConfig } from '@/lib/contact-config';
import { MailIcon } from 'lucide-react';
import Link from 'next/link';
import InstagramIcon from './instagram-icon';
import LinkedInIcon from './linkedin-icon';
import XIcon from './x-icon';

type Props = {
  type: keyof typeof socialMediaConfig;
};

function HomeSocialMediaIcon({ type }: Props) {
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
      <Icon className="size-9" />
    </Link>
  );
}

export default HomeSocialMediaIcon;
