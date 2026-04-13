import { useEffect, useState } from 'react';
import axios from 'axios';
import { Users, UserPlus, Trash2, Shield, Edit } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { formatDate } from '../utils/dateFormat';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    full_name: '',
    role: 'executive',
    is_active: true
  });

  const { isAdmin } = useAuth();

  useEffect(() => {
    if (isAdmin) {
      fetchUsers();
    }
  }, [isAdmin]);

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/users/list`);
      setUsers(response.data);
    } catch (error) {
      console.error('Error fetching users:', error);
      toast.error('Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    
    try {
      const response = await axios.post(`${API}/users/create`, formData);
      toast.success(response.data.message);
      
      setFormData({ username: '', password: '', full_name: '', role: 'executive', is_active: true });
      setShowCreateForm(false);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleEditUser = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      password: '',
      full_name: user.full_name,
      role: user.role,
      is_active: user.is_active
    });
    setShowCreateForm(true);
  };

  const handleUpdateUser = async (e) => {
    e.preventDefault();
    
    try {
      const updateData = {
        full_name: formData.full_name,
        role: formData.role,
        is_active: formData.is_active
      };
      
      // Only include password if it's been changed
      if (formData.password) {
        updateData.password = formData.password;
      }
      
      // Include new username if it's different
      if (formData.username !== editingUser.username) {
        updateData.new_username = formData.username;
      }
      
      const response = await axios.put(`${API}/users/${editingUser.username}`, updateData);
      toast.success(response.data.message);
      
      setFormData({ username: '', password: '', full_name: '', role: 'executive', is_active: true });
      setShowCreateForm(false);
      setEditingUser(null);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleCancelEdit = () => {
    setEditingUser(null);
    setShowCreateForm(false);
    setFormData({ username: '', password: '', full_name: '', role: 'executive', is_active: true });
  };

  const handleDeleteUser = async (username) => {
    const confirmed = window.confirm(`Delete user "${username}"? This action cannot be undone.`);
    if (!confirmed) return;

    try {
      await axios.delete(`${API}/users/${username}`);
      toast.success(`User ${username} deleted`);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete user');
    }
  };

  const getRoleBadge = (role) => {
    const colors = {
      admin: 'bg-red-100 text-red-800 border-red-200',
      manager: 'bg-blue-100 text-blue-800 border-blue-200',
      executive: 'bg-green-100 text-green-800 border-green-200'
    };
    return colors[role] || 'bg-gray-100 text-gray-800';
  };

  if (!isAdmin) {
    return (
      <div className="p-3 sm:p-6 md:p-8">
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-center text-destructive">
              Access Denied. Admin privileges required.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
            User Management
          </h1>
          <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
            Manage user accounts and permissions
          </p>
        </div>
        <Button onClick={() => {
          setEditingUser(null);
          setFormData({ username: '', password: '', full_name: '', role: 'executive', is_active: true });
          setShowCreateForm(!showCreateForm);
        }}>
          <UserPlus className="h-4 w-4 mr-2" />
          {showCreateForm ? 'Cancel' : 'Create User'}
        </Button>
      </div>

      {/* Create/Edit User Form */}
      {showCreateForm && (
        <Card className="border-primary/20">
          <CardHeader>
            <CardTitle>{editingUser ? 'Edit User' : 'Create New User'}</CardTitle>
            <CardDescription>
              {editingUser ? 'Update user details, role, or password' : 'Add a new executive, manager, or admin'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser} className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="username">Username *</Label>
                  <Input
                    id="username"
                    value={formData.username}
                    onChange={(e) => setFormData({...formData, username: e.target.value})}
                    required
                    disabled={editingUser && formData.username === editingUser.username}
                  />
                  {editingUser && (
                    <p className="text-xs text-muted-foreground mt-1">Change username to rename user</p>
                  )}
                </div>
                <div>
                  <Label htmlFor="full_name">Full Name *</Label>
                  <Input
                    id="full_name"
                    value={formData.full_name}
                    onChange={(e) => setFormData({...formData, full_name: e.target.value})}
                    required
                  />
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="password">Password {editingUser ? '(leave blank to keep unchanged)' : '*'}</Label>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required={!editingUser}
                    placeholder={editingUser ? 'Enter new password to change' : ''}
                  />
                </div>
                <div>
                  <Label htmlFor="role">Role *</Label>
                  <Select value={formData.role} onValueChange={(val) => setFormData({...formData, role: val})}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="executive">Stock Entry Executive</SelectItem>
                      <SelectItem value="polythene_executive">Polythene Entry Executive</SelectItem>
                      <SelectItem value="manager">Manager</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {editingUser && (
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="is_active" className="cursor-pointer">
                    Active (uncheck to deactivate user)
                  </Label>
                </div>
              )}

              <div className="flex gap-2">
                <Button type="submit">{editingUser ? 'Update User' : 'Create User'}</Button>
                <Button type="button" variant="outline" onClick={handleCancelEdit}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Users List */}
      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5 text-primary" />
            All Users ({users.length})
          </CardTitle>
          <CardDescription>Manage user accounts and permissions</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead>Username</TableHead>
                <TableHead>Full Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.username}>
                  <TableCell className="font-mono font-medium">{user.username}</TableCell>
                  <TableCell>{user.full_name}</TableCell>
                  <TableCell>
                    <Badge className={getRoleBadge(user.role)}>
                      {user.role.toUpperCase()}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? "outline" : "destructive"}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditUser(user)}
                        title="Edit user"
                      >
                        <Edit className="h-4 w-4 text-primary" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteUser(user.username)}
                        title="Delete user"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
