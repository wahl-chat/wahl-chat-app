import Footer from '@/components/footer';
import Header from '@/components/header';

/** Header + footer shell like (with-header), wide enough for two-column feeds. */
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex w-full flex-col">
      <Header />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-5xl grow px-4 pb-8 md:px-6">
        {children}
      </main>
      <Footer />
    </div>
  );
}

export default Layout;
