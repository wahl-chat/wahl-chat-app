'use client';

import type { Tenant } from '@/lib/firebase/firebase.types';
import { createContext, useContext, useEffect, useState } from 'react';

type Props = {
  tenant?: Tenant;
  children: React.ReactNode;
};

const TenantContext = createContext<Tenant | undefined>(undefined);

function TenantProvider({ children, tenant: initialTenant }: Props) {
  const [tenant, setTenant] = useState<Tenant | undefined>(initialTenant);

  useEffect(() => {
    // only change tenant if it's not the same as the initial tenant and not undefined
    // to persist the tenant across re-renders
    if (initialTenant && initialTenant.id !== tenant?.id) {
      setTenant(initialTenant);
    }
  }, [initialTenant, tenant]);

  return (
    <TenantContext.Provider value={tenant}>{children}</TenantContext.Provider>
  );
}

export function useTenant() {
  return useContext(TenantContext);
}

export default TenantProvider;
