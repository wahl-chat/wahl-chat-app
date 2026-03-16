import Footer from '@/components/footer';
import Header from '@/components/header';
import SkipLink from '@/components/skip-link';

type Props = {
  children: React.ReactNode;
};

function HomeLayout({ children }: Props) {
  return (
    <div className="relative flex w-full flex-col">
      <SkipLink href="#main-content">Zum Inhalt springen</SkipLink>
      <Header />
      <main
        id="main-content"
        className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-xl grow px-4 pb-8 md:px-0"
      >
        {children}
      </main>
      <Footer />
    </div>
  );
}

export default HomeLayout;
