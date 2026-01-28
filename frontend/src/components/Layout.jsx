import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Upload, Package, Users, TrendingUp, History, RotateCcw, Power, Tag, Scale, Link2, GitBranch } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Layout({ children }) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [resetPassword, setResetPassword] = useState('');

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Upload Files', href: '/upload', icon: Upload },
    { name: 'Current Stock', href: '/current-stock', icon: Package },
    { name: 'Physical vs Book', href: '/physical-vs-book', icon: Scale },
    { name: 'Item Mapping', href: '/item-mapping', icon: Link2 },
    { name: 'Manage Mappings', href: '/mapping-management', icon: GitBranch },
    { name: 'Stamp Management', href: '/stamps', icon: Tag },
    { name: 'Party Analytics', href: '/party-analytics', icon: Users },
    { name: 'Profit Analysis', href: '/profit', icon: TrendingUp },
    { name: 'History', href: '/history', icon: History },
  ];

  const handleUndo = async () => {
    // First, get the last action to show user what will be undone
    try {
      const historyResponse = await axios.get(`${API}/history/actions?limit=1`);
      const lastAction = historyResponse.data[0];
      
      if (!lastAction) {
        toast.error('No action to undo');
        return;
      }

      // Ask for confirmation
      const confirmed = window.confirm(
        `Are you sure you want to undo this action?\n\n` +
        `Action: ${lastAction.description}\n` +
        `Time: ${new Date(lastAction.timestamp).toLocaleString()}\n\n` +
        `Note: This will mark the action as undone but won't restore the data.`
      );

      if (!confirmed) return;

      const response = await axios.post(`${API}/history/undo`);
      toast.success(response.data.message);
      window.location.reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'No action to undo');
    }
  };

  const handleReset = async () => {
    if (!resetPassword) {
      toast.error('Please enter password');
      return;
    }
    
    try {
      await axios.post(`${API}/system/reset`, { password: resetPassword });
      toast.success('System reset successfully!');
      setResetPassword('');
      window.location.reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Reset failed');
    }
  };

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
                : 'text-foreground hover:bg-muted hover:text-foreground'
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
          <div className="border-t border-border/40 p-4 space-y-2">
            <Button 
              variant="outline" 
              size="sm" 
              className="w-full justify-start text-xs"
              onClick={handleUndo}
              data-testid="undo-button"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-2" />
              Undo Last Action
            </Button>
            
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button 
                  variant="destructive" 
                  size="sm" 
                  className="w-full justify-start text-xs"
                  data-testid="reset-button"
                >
                  <Power className="h-3.5 w-3.5 mr-2" />
                  Reset System
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reset System</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will delete all data. Enter password to confirm.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="py-4">
                  <Label htmlFor="reset-password">Password</Label>
                  <Input
                    id="reset-password"
                    type="password"
                    placeholder="Enter CLOSE to reset"
                    value={resetPassword}
                    onChange={(e) => setResetPassword(e.target.value)}
                    data-testid="reset-password-input"
                  />
                </div>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleReset} className="bg-destructive text-destructive-foreground">
                    Reset System
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            
            <div className="mt-3 rounded-lg bg-gradient-to-r from-primary/10 via-secondary/10 to-accent/10 p-3 text-xs">
              <p className="font-medium text-foreground">StockBud v2.0</p>
              <p className="text-muted-foreground mt-1">Intelligent Inventory</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 flex h-16 items-center gap-4 border-b border-border/40 bg-card px-4">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="icon" data-testid="mobile-menu-button">
              <LayoutDashboard className="h-5 w-5" />
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
        <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
          <span className="text-primary">Stock</span>
          <span className="text-secondary">Bud</span>
        </h1>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-auto lg:pl-0 pt-16 lg:pt-0">
        {children}
      </main>
    </div>
  );
}