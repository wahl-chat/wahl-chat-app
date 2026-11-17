import Logo from '@/components/chat/logo';
import Link from 'next/link';
import NavBar from './navbar/navbar';

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background px-4 py-2 md:px-0">
      <div className="relative mx-auto flex max-w-xl items-center justify-between gap-2 md:flex-row">
        <Link href="/">
          <Logo className="size-10 md:size-16" />
        </Link>

        <NavBar />
      </div>
    </header>
  );
}

export default Header;
