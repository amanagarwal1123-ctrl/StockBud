import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Activity, Filter, Download } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { exportToCSV } from '@/utils/exportCSV';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function ActivityLog() {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterUser, setFilterUser] = useState('all');
  const [filterAction, setFilterAction] = useState('all');
  const [users, setUsers] = useState([]);
  
  const { isAdmin } = useAuth();

  useEffect(() => {
    if (isAdmin) {
      fetchActivities();
      fetchUsers();
    }
  }, [isAdmin]);

  const fetchActivities = async () => {
    try {
      const response = await axios.get(`${API}/activity-log`);
      setActivities(response.data);
    } catch (error) {
      console.error('Error fetching activities:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/users/list`);
      setUsers(response.data);
    } catch (error) {
      console.error('Error fetching users:', error);
    }
  };

  const filteredActivities = activities.filter(activity => {
    const matchesUser = filterUser === 'all' || activity.user === filterUser;
    const matchesAction = filterAction === 'all' || activity.action_type === filterAction;
    return matchesUser && matchesAction;
  });

  const handleExport = () => {
    const exportData = filteredActivities.map(activity => ({
      'Date': new Date(activity.timestamp).toLocaleString(),
      'User': activity.user,
      'Role': activity.user_role,
      'Action': activity.action_type,
      'Description': activity.description,
      'Details': JSON.stringify(activity.details)
    }));
    exportToCSV(exportData, 'activity_log');
  };

  if (!isAdmin) {
    return (
      <div className="p-3 sm:p-6 md:p-8">
        <Card className="border-destructive/50">
          <CardContent className="pt-6">
            <p className="text-center text-destructive">Access Denied. Admin privileges required.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          Activity Log
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          Complete audit trail of all user actions
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Filter Activities</CardTitle>
            <Button onClick={handleExport} variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <Label className="text-sm mb-2">Filter by User</Label>
              <Select value={filterUser} onValueChange={setFilterUser}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Users</SelectItem>
                  {users.map(u => (
                    <SelectItem key={u.username} value={u.username}>
                      {u.full_name} ({u.role})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm mb-2">Filter by Action</Label>
              <Select value={filterAction} onValueChange={setFilterAction}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Actions</SelectItem>
                  <SelectItem value="stock_entry">Stock Entry</SelectItem>
                  <SelectItem value="polythene_adjustment">Polythene Adjustment</SelectItem>
                  <SelectItem value="stamp_verification">Stamp Verification</SelectItem>
                  <SelectItem value="stamp_approval">Stamp Approval</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            Activity Log ({filteredActivities.length} entries)
          </CardTitle>
          <CardDescription>Who did what and when</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Date & Time</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredActivities.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No activities found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredActivities.map((activity, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-mono text-sm">
                        {new Date(activity.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell className="font-medium">{activity.user}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{activity.user_role}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge>{activity.action_type.replace(/_/g, ' ')}</Badge>
                      </TableCell>
                      <TableCell className="max-w-md truncate">{activity.description}</TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-xs truncate">
                        {JSON.stringify(activity.details)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
