'use client';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import { type UserDetails, getUserDetailsFromUser } from '@/lib/utils';
import { UserIcon } from 'lucide-react';

type Props = {
  details?: UserDetails;
};

function UserAvatar({ details }: Props) {
  const { user } = useAnonymousAuth();

  const userDetails = user ? getUserDetailsFromUser(user) : details;

  return (
    <div className="flex aspect-square size-9 items-center justify-center rounded-full border border-border hover:bg-muted">
      {userDetails?.photoURL ? (
        <img
          src={userDetails.photoURL}
          alt="User avatar"
          className="size-full rounded-full object-cover"
        />
      ) : (
        <UserIcon className="size-4" />
      )}
    </div>
  );
}

export default UserAvatar;
