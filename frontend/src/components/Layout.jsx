import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Upload, Package, Users, TrendingUp, History, RotateCcw, Power, Tag, Scale, Link2, GitBranch, Receipt, LogOut, User, CheckCircle2, Activity, Box, BarChart3, ShoppingCart, Layers, UserCog, ChevronDown, ChevronRight, FileUp, Combine } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '../context/AuthContext';
import { useUpload } from '../context/UploadContext';
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
  { id: 'master_stock', label: 'Master Stock', desc: 'Zeros out all item quantities & opening stock (keeps items, stamps, mappings intact)' },
];

export default function Layout({ children }) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { uploads } = useUpload();
  const [resetPassword, setResetPassword] = useState('');
  const [resetCategories, setResetCategories] = useState([]);
  const [showUndoDialog, setShowUndoDialog] = useState(false);
  const [recentUploads, setRecentUploads] = useState([]);
  const [expandedGroups, setExpandedGroups] = useState({ inventory: true, verification: true, analytics: true, settings: true });
  
  const { user, logout, isAdmin, isManager } = useAuth();

  const toggleGroup = (group) => {
    setExpandedGroups(prev => ({ ...prev, [group]: !prev[group] }));
  };

  // Grouped navigation structure
  const navGroups = [
    {
      id: 'main',
      items: [
        { name: 'Dashboard', href: '/', icon: LayoutDashboard, roles: ['admin'] },
        { name: 'Stock Entry', href: '/executive-entry', icon: Package, roles: ['executive'] },
        { name: 'Polythene Entry', href: '/polythene-entry', icon: Box, roles: ['polythene_executive'] },
        { name: 'Notifications', href: '/notifications', icon: Receipt, roles: ['manager', 'admin', 'executive'] },
      ]
    },
    {
      id: 'inventory',
      label: 'Inventory',
      icon: Package,
      roles: ['admin'],
      items: [
        { name: 'Upload Files', href: '/upload', icon: Upload, roles: ['admin'] },
        { name: 'Historical Upload', href: '/historical-upload', icon: FileUp, roles: ['admin'] },
        { name: 'Current Stock', href: '/current-stock', icon: Package, roles: ['admin'] },
        { name: 'Item Mapping', href: '/item-mapping', icon: Link2, roles: ['admin'] },
        { name: 'Manage Mappings', href: '/mapping-management', icon: GitBranch, roles: ['admin'] },
        { name: 'Purchase Rates', href: '/purchase-rates', icon: Receipt, roles: ['admin'] },
        { name: 'Polythene Mgmt', href: '/polythene-management', icon: Box, roles: ['admin'] },
      ]
    },
    {
      id: 'verification',
      label: 'Verification',
      icon: CheckCircle2,
      roles: ['manager', 'admin'],
      items: [
        { name: 'Physical vs Book', href: '/physical-vs-book', icon: Scale, roles: ['manager', 'admin'] },
        { name: 'Approvals', href: '/approvals', icon: CheckCircle2, roles: ['manager', 'admin'] },
        { name: 'Stamp Mgmt', href: '/stamps', icon: Tag, roles: ['admin'] },
        { name: 'Stamp Assign', href: '/stamp-assignments', icon: UserCog, roles: ['admin'] },
      ]
    },
    {
      id: 'analytics',
      label: 'Analytics & AI',
      icon: BarChart3,
      roles: ['admin'],
      items: [
        { name: 'Visualization', href: '/visualization', icon: BarChart3, roles: ['admin'] },
        { name: 'Item Buffers', href: '/item-buffers', icon: Layers, roles: ['admin'] },
        { name: 'Item Groups', href: '/item-groups', icon: Combine, roles: ['admin'] },
        { name: 'Orders', href: '/orders', icon: ShoppingCart, roles: ['admin', 'executive'] },
        { name: 'Party Analytics', href: '/party-analytics', icon: Users, roles: ['admin'] },
        { name: 'Profit Analysis', href: '/profit', icon: TrendingUp, roles: ['admin'] },
      ]
    },
    {
      id: 'settings',
      label: 'Admin',
      icon: User,
      roles: ['admin'],
      items: [
        { name: 'User Mgmt', href: '/users', icon: User, roles: ['admin'] },
        { name: 'History', href: '/history', icon: History, roles: ['admin'] },
        { name: 'Activity Log', href: '/activity-log', icon: Activity, roles: ['admin'] },
      ]
    },
  ];

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
    if (resetCategories.length === 0) {
      toast.error('Please select at least one category to reset');
      return;
    }
    
    try {
      const response = await axios.post(`${API}/system/reset`, { 
        password: resetPassword,
        categories: resetCategories
      });
      toast.success(response.data.message || 'Reset complete!');
      setResetPassword('');
      setResetCategories([]);
      window.location.reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Reset failed');
    }
  };

  const handleFixDates = async () => {
    try {
      const response = await axios.post(`${API}/system/fix-dates`);
      const data = response.data;
      if (data.fixed_count > 0) {
        toast.success(`Fixed ${data.fixed_count} transactions: ${data.fixes.join(', ')}`);
      } else {
        toast.info('No date issues found — all dates look correct.');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fix dates failed');
    }
  };

  const toggleCategory = (catId) => {
    setResetCategories(prev => 
      prev.includes(catId) ? prev.filter(c => c !== catId) : [...prev, catId]
    );
  };

  const toggleAllCategories = () => {
    if (resetCategories.length === RESET_CATEGORIES.length) {
      setResetCategories([]);
    } else {
      setResetCategories(RESET_CATEGORIES.map(c => c.id));
    }
  };

  const NavLinks = ({ mobile = false }) => (
    <nav className="space-y-1">
      {navGroups.map((group) => {
        // Filter items by user role
        const visibleItems = group.items.filter(item => user && item.roles.includes(user.role));
        if (visibleItems.length === 0) return null;

        // Ungrouped items (main group)
        if (!group.label) {
          return visibleItems.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link key={item.name} to={item.href} onClick={() => mobile && setMobileOpen(false)}
                data-testid={`nav-link-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                  isActive ? 'bg-primary text-primary-foreground shadow-sm' : 'text-foreground hover:bg-muted'
                }`}>
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            );
          });
        }

        // Check if group is visible for this role
        if (group.roles && !group.roles.includes(user?.role)) return null;

        const isExpanded = expandedGroups[group.id];
        const hasActiveChild = visibleItems.some(item => location.pathname === item.href);

        return (
          <div key={group.id} className="pt-2">
            <button
              onClick={() => toggleGroup(group.id)}
              className={`flex items-center justify-between w-full rounded-lg px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
                hasActiveChild ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
              }`}
              data-testid={`nav-group-${group.id}`}
            >
              <div className="flex items-center gap-2">
                <group.icon className="h-3.5 w-3.5" />
                {group.label}
              </div>
              {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            </button>
            {isExpanded && (
              <div className="mt-0.5 space-y-0.5 ml-2 border-l border-border/40 pl-2">
                {visibleItems.map((item) => {
                  const isActive = location.pathname === item.href;
                  return (
                    <Link key={item.name} to={item.href} onClick={() => mobile && setMobileOpen(false)}
                      data-testid={`nav-link-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                      className={`flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition-all ${
                        isActive ? 'bg-primary text-primary-foreground shadow-sm font-medium' : 'text-foreground hover:bg-muted'
                      }`}>
                      <item.icon className="h-3.5 w-3.5" />
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
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
              <AlertDialog onOpenChange={() => { setResetPassword(''); setResetCategories([]); }}>
              <AlertDialogTrigger asChild>
                <Button 
                  variant="destructive" 
                  size="sm" 
                  className="w-full justify-start text-xs"
                  data-testid="reset-button"
                >
                  <Power className="h-3.5 w-3.5 mr-2" />
                  Reset Data
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent className="max-w-md">
                <AlertDialogHeader>
                  <AlertDialogTitle>Reset Data</AlertDialogTitle>
                  <AlertDialogDescription>
                    Select what to clear. Users are never deleted.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="max-h-[50vh] overflow-y-auto py-2 space-y-3">
                  <div className="flex items-center gap-2 pb-2 border-b">
                    <Checkbox 
                      id="select-all"
                      checked={resetCategories.length === RESET_CATEGORIES.length}
                      onCheckedChange={toggleAllCategories}
                      data-testid="reset-select-all"
                    />
                    <Label htmlFor="select-all" className="text-sm font-semibold cursor-pointer">Select All</Label>
                  </div>
                  {RESET_CATEGORIES.map(cat => (
                    <div key={cat.id} className="flex items-start gap-2">
                      <Checkbox 
                        id={`reset-${cat.id}`}
                        checked={resetCategories.includes(cat.id)}
                        onCheckedChange={() => toggleCategory(cat.id)}
                        data-testid={`reset-check-${cat.id}`}
                      />
                      <div className="leading-tight">
                        <Label htmlFor={`reset-${cat.id}`} className="text-sm font-medium cursor-pointer">{cat.label}</Label>
                        <p className="text-xs text-muted-foreground">{cat.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="pt-3 border-t">
                  <Label htmlFor="reset-password" className="text-sm">Password</Label>
                  <Input
                      id="reset-password"
                      type="password"
                      placeholder="Type CLOSE to confirm"
                      value={resetPassword}
                      onChange={(e) => setResetPassword(e.target.value)}
                    className="mt-1"
                    data-testid="reset-password-input"
                  />
                </div>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction 
                    onClick={handleReset} 
                    className="bg-destructive text-destructive-foreground"
                    disabled={resetCategories.length === 0}
                    data-testid="reset-confirm-button"
                  >
                    Reset ({resetCategories.length}) Selected
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
        {/* Global Upload Progress */}
        {uploads.length > 0 && (
          <div className="sticky top-0 z-40 bg-background border-b px-4 py-2 space-y-1.5" data-testid="global-upload-bar">
            {uploads.map(u => (
              <div key={u.id} className="flex items-center gap-3">
                <div className={`h-2 w-2 rounded-full flex-shrink-0 ${u.status === 'done' ? 'bg-emerald-500' : u.status === 'error' ? 'bg-red-500' : 'bg-blue-500 animate-pulse'}`} />
                <span className="text-xs font-medium truncate min-w-0">{u.label}: {u.fileName}</span>
                <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-300 ${u.status === 'error' ? 'bg-red-500' : u.status === 'done' ? 'bg-emerald-500' : 'bg-blue-500'}`} style={{ width: `${u.percent}%` }} />
                </div>
                <span className="text-xs text-muted-foreground flex-shrink-0">{u.message}</span>
              </div>
            ))}
          </div>
        )}
        {children}
      </main>
    </div>
  );
}