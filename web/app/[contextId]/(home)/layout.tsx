import Footer from '@/components/footer';
import Header from '@/components/header';

type Props = {
  children: React.ReactNode;
};

function HomeLayout({ children }: Props) {
  return (
    <div className="relative flex w-full flex-col">
      <Header />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-xl grow px-4 pb-8 md:px-0">
        {children}
      </main>
      <Footer />
    </div>
  );
}

export default HomeLayout;
