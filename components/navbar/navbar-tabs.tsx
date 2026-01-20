'use client';

import { isProlificStudy } from '@/lib/study/prolific-params';
import { useEffect, useState } from 'react';
import type { NavbarItemDetails } from './navbar-item';
import NavbarItem from './navbar-item';

type Props = {
  tabs: NavbarItemDetails[];
  mobileClose?: () => void;
};

function NavbarTabs({ tabs, mobileClose }: Props) {
  const [isProlific, setIsProlific] = useState(false);

  useEffect(() => {
    setIsProlific(isProlificStudy());
  }, []);

  if (isProlific) {
    return null;
  }

  return (
    <>
      {tabs.map((tab) => (
        <NavbarItem key={tab.href} details={tab} mobileClose={mobileClose} />
      ))}
    </>
  );
}

export default NavbarTabs;
