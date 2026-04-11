import Navbar from './Navbar';

interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-stone-50">
      <Navbar />
      <div className="pt-12">{children}</div>
    </div>
  );
}
