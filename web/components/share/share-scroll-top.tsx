'use client';

import { useEffect } from 'react';

function ShareScrollTop() {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return null;
}

export default ShareScrollTop;
