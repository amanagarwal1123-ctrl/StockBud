import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Upload, Package, Users, TrendingUp, History, RotateCcw, Power, Tag, Scale, Link2, GitBranch, Receipt, LogOut, User, CheckCircle2, Activity, Box } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '../context/AuthContext';
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
import { Checkbox } from '@/components/ui/checkbox';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const RESET_CATEGORIES = [
  { id: 'sales', label: 'Sales Transactions', desc: 'All sale & sale return records' },
  { id: 'purchases', label: 'Purchase Transactions', desc: 'All purchase & purchase return records' },
  { id: 'issues', label: 'Issue / Receive', desc: 'Branch transfer records' },
  { id: 'polythene', label: 'Polythene Adjustments', desc: 'All polythene weight entries' },
  { id: 'mappings', label: 'Item Mappings', desc: 'Transaction-to-master name mappings' },
  { id: 'physical_stock', label: 'Physical Stock', desc: 'Physical inventory & stock entries' },
  { id: 'purchase_ledger', label: 'Purchase Ledger', desc: 'Cumulative purchase rates' },
  { id: 'notifications', label: 'Notifications & Logs', desc: 'Notifications and activity log' },
  { id: 'history', label: 'Action History', desc: 'Upload history & undo records' },
];

export default function Layout({ children }) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [resetPassword, setResetPassword] = useState('');
  const [resetCategories, setResetCategories] = useState([]);
  const [showUndoDialog, setShowUndoDialog] = useState(false);
  const [recentUploads, setRecentUploads] = useState([]);
  
  const { user, logout, isAdmin, isManager } = useAuth();

  // Base navigation for all users
  const baseNavigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard, roles: ['admin'] },
  ];

  // Executive-specific (ONLY Stock Entry)
  const executiveNavigation = [
    { name: 'Stock Entry', href: '/executive-entry', icon: Package, roles: ['executive'] },
  ];

  // Polythene Executive-specific
  const polytheneNavigation = [
    { name: 'Polythene Adjustment', href: '/polythene-entry', icon: Box, roles: ['polythene_executive'] },
  ];

  // Manager-specific  
  const managerNavigation = [
    { name: 'Physical vs Book', href: '/physical-vs-book', icon: Scale, roles: ['manager', 'admin'] },
    { name: 'Approvals', href: '/approvals', icon: CheckCircle2, roles: ['manager', 'admin'] },
    { name: 'Notifications', href: '/notifications', icon: Receipt, roles: ['manager', 'admin'] },
  ];

  // Admin-only navigation
  const adminNavigation = [
    { name: 'Upload Files', href: '/upload', icon: Upload, roles: ['admin'] },
    { name: 'Current Stock', href: '/current-stock', icon: Package, roles: ['admin'] },
    { name: 'Item Mapping', href: '/item-mapping', icon: Link2, roles: ['admin'] },
    { name: 'Manage Mappings', href: '/mapping-management', icon: GitBranch, roles: ['admin'] },
    { name: 'Purchase Rates', href: '/purchase-rates', icon: Receipt, roles: ['admin'] },
    { name: 'Polythene Management', href: '/polythene-management', icon: Box, roles: ['admin'] },
    { name: 'Stamp Management', href: '/stamps', icon: Tag, roles: ['admin'] },
    { name: 'Party Analytics', href: '/party-analytics', icon: Users, roles: ['admin'] },
    { name: 'Profit Analysis', href: '/profit', icon: TrendingUp, roles: ['admin'] },
    { name: 'History', href: '/history', icon: History, roles: ['admin'] },
    { name: 'User Management', href: '/users', icon: User, roles: ['admin'] },
    { name: 'Activity Log', href: '/activity-log', icon: Activity, roles: ['admin'] },
  ];

  // Combine and filter based on user role
  const allNavigationItems = [...baseNavigation, ...executiveNavigation, ...polytheneNavigation, ...managerNavigation, ...adminNavigation];
  const allNavigation = allNavigationItems.filter(item => 
    !user || item.roles.includes(user.role)
  );

  const handleUndo = async () => {
    // Fetch recent uploads
    try {
      const response = await axios.get(`${API}/history/recent-uploads`);
      setRecentUploads(response.data);
      setShowUndoDialog(true);
    } catch (error) {
      toast.error('No uploads to undo');
    }
  };

  const handleNormalizeStamps = async () => {
    const confirmed = window.confirm(
      'Normalize all stamp names to CAPS format (STAMP 1, STAMP 2, etc.)?\n\n' +
      'This will fix any inconsistencies like "Stamp 1" vs "STAMP 1".\n\n' +
      'This is safe to run and will consolidate duplicate stamps.'
    );
    
    if (!confirmed) return;
    
    try {
      toast.info('Normalizing stamps... Please wait.');
      const response = await axios.post(`${API}/admin/normalize-stamps`);
      toast.success(response.data.message);
      
      // Show details
      if (response.data.update_log && response.data.update_log.length > 0) {
        console.log('Stamp normalization log:', response.data.update_log);
        toast.info(`Updated ${response.data.total_documents} documents across ${response.data.stamps_updated} stamp variations`);
      }
      
      // Refresh page after normalization
      setTimeout(() => window.location.reload(), 2000);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Normalization failed');
    }
  };

  const undoUpload = async (batchId, description) => {
    const confirmed = window.confirm(`Undo this upload?\n\n${description}\n\nThis will delete all transactions from this file.`);
    if (!confirmed) return;

    try {
      const response = await axios.post(`${API}/history/undo-upload`, null, {
        params: { batch_id: batchId }
      });
      toast.success(response.data.message);
      setShowUndoDialog(false);
      window.location.reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to undo upload');
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
      {allNavigation.map((item) => {
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
            {/* User Info */}
            {user && (
              <div className="mb-3 p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <p className="text-sm font-medium">{user.full_name}</p>
                </div>
                <p className="text-xs text-muted-foreground">{user.username}</p>
                <Badge variant="outline" className="mt-2 text-xs">
                  {user.role.toUpperCase()}
                </Badge>
              </div>
            )}

            {/* Admin-only Undo Upload */}
            {isAdmin && (
              <>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="w-full justify-start text-xs"
                  onClick={handleUndo}
                  data-testid="undo-button"
                >
                  <RotateCcw className="h-3.5 w-3.5 mr-2" />
                  Undo Upload
                </Button>

                {/* Undo Dialog */}
                <AlertDialog open={showUndoDialog} onOpenChange={setShowUndoDialog}>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Undo File Upload</AlertDialogTitle>
                  <AlertDialogDescription>
                    Select which upload to undo. This will delete all transactions from that file.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="py-4 space-y-2 max-h-80 overflow-y-auto">
                  {recentUploads.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">No recent uploads found</p>
                  ) : (
                    recentUploads.map((upload, idx) => (
                      <div
                        key={idx}
                        className="border rounded-lg p-3 hover:bg-muted/50 cursor-pointer transition-colors"
                        onClick={() => undoUpload(upload.data_snapshot?.batch_id, upload.description)}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="font-medium text-sm">{upload.description}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {new Date(upload.timestamp).toLocaleString()}
                            </p>
                            {upload.data_snapshot?.file_name && (
                              <p className="text-xs text-muted-foreground">
                                File: {upload.data_snapshot.file_name}
                              </p>
                            )}
                          </div>
                          {upload.can_undo ? (
                            <Badge variant="outline" className="text-green-600">Active</Badge>
                          ) : (
                            <Badge variant="outline" className="text-muted-foreground">Undone</Badge>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
              </>
            )}
            
            {/* Logout Button - All users */}
            <Button 
              variant="outline" 
              size="sm" 
              onClick={logout}
              className="w-full justify-start text-xs text-orange-600 border-orange-600/20 hover:bg-orange-600/10"
            >
              <LogOut className="h-3.5 w-3.5 mr-2" />
              Logout
            </Button>
            
            {/* Reset - Admin only */}
            {isAdmin && (
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
            )}
            
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
              
              {/* Mobile Footer with User Info and Logout */}
              <div className="border-t border-border/40 p-4 space-y-2">
                {/* User Info */}
                {user && (
                  <div className="mb-3 p-3 bg-muted/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-1">
                      <User className="h-4 w-4 text-muted-foreground" />
                      <p className="text-sm font-medium">{user.full_name}</p>
                    </div>
                    <p className="text-xs text-muted-foreground">{user.username}</p>
                    <Badge variant="outline" className="mt-2 text-xs">
                      {user.role.toUpperCase()}
                    </Badge>
                  </div>
                )}
                
                {/* Logout Button */}
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => {
                    logout();
                    setMobileOpen(false);
                  }}
                  className="w-full justify-start text-xs text-orange-600 border-orange-600/20 hover:bg-orange-600/10"
                >
                  <LogOut className="h-3.5 w-3.5 mr-2" />
                  Logout
                </Button>
                
                <div className="mt-3 rounded-lg bg-gradient-to-r from-primary/10 via-secondary/10 to-accent/10 p-3 text-xs">
                  <p className="font-medium text-foreground">StockBud v2.0</p>
                  <p className="text-muted-foreground mt-1">Intelligent Inventory</p>
                </div>
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