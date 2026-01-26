import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Upload, Package, GitCompare, TrendingUp, History, Menu } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';

export default function Layout({ children }) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Upload Files', href: '/upload', icon: Upload },
    { name: 'Book Inventory', href: '/book-inventory', icon: Package },
    { name: 'Matching', href: '/matching', icon: GitCompare },
    { name: 'Analytics', href: '/analytics', icon: TrendingUp },
    { name: 'History', href: '/history', icon: History },
  ];

  const NavLinks = ({ mobile = false }) => (
    <nav className="space-y-1">
      {navigation.map((item) => {
        const isActive = location.pathname === item.href;
        return (
          <Link
            key={item.name}
            to={item.href}
            onClick={() => mobile && setMobileOpen(false)}
            data-testid={`nav-link-${item.name.toLowerCase().replace(' ', '-')}`}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
              isActive
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
            }`}
          >
            <item.icon className="h-5 w-5" />
            {item.name}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 border-r border-border/40 bg-card lg:block">
        <div className="flex h-full flex-col">
          <div className="flex h-16 items-center border-b border-border/40 px-6">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 text-2xl font-bold tracking-tight">
                <span className="text-primary">Stock</span>
                <span className="text-secondary">Bud</span>
              </div>
              <div className="h-2 w-2 rounded-full bg-accent animate-pulse"></div>
            </div>
          </div>
          <div className="flex-1 overflow-auto p-4">
            <NavLinks />
          </div>
          <div className="border-t border-border/40 p-4">
            <div className="rounded-lg bg-muted/50 p-4 text-xs text-muted-foreground">
              <p className="font-medium">Inventory Management</p>
              <p className="mt-1">Powered by JewelVault OS</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 flex h-16 items-center gap-4 border-b border-border/40 bg-card px-4">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" data-testid="mobile-menu-button">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <div className="flex h-full flex-col">
              <div className="flex h-16 items-center px-6">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 text-2xl font-bold tracking-tight">
                    <span className="text-primary">Stock</span>
                    <span className="text-secondary">Bud</span>
                  </div>
                  <div className="h-2 w-2 rounded-full bg-accent animate-pulse"></div>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-4">
                <NavLinks mobile />
              </div>
            </div>
          </SheetContent>
        </Sheet>
        <h1 className="text-xl font-bold tracking-tight">JewelVault</h1>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-auto lg:pl-0 pt-16 lg:pt-0">
        {children}
      </main>
    </div>
  );
}