'use client';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import { type UserDetails, getUserDetailsFromUser } from '@/lib/utils';
import { UserIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';

type Props = {
  details?: UserDetails;
};

function UserAvatar({ details }: Props) {
  const t = useTranslations('auth');
  const { user } = useAnonymousAuth();

  const userDetails = user ? getUserDetailsFromUser(user) : details;

  return (
    <div className="flex aspect-square size-9 items-center justify-center rounded-full border border-border hover:bg-muted">
      {userDetails?.photoURL ? (
        <img
          src={userDetails.photoURL}
          alt={t('avatarAlt')}
          className="size-full rounded-full object-cover"
        />
      ) : (
        <UserIcon className="size-4" />
      )}
    </div>
  );
}

export default UserAvatar;
