'use client';

import dynamic from 'next/dynamic';
const PDFView = dynamic(() => import('@/components/pdf-view'), {
  ssr: false,
});

function Page() {
  return <PDFView />;
}

export default Page;
