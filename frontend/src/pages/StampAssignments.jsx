import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Users, Save, Trash2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function StampAssignments() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [assignments, setAssignments] = useState([]);
  const [users, setUsers] = useState([]);
  const [stamps, setStamps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editStamp, setEditStamp] = useState('');
  const [editUser, setEditUser] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      const [aRes, uRes, mRes] = await Promise.all([
        axios.get(`${API}/stamp-assignments`),
        axios.get(`${API}/users/list`, { headers }),
        axios.get(`${API}/master-items`)
      ]);
      setAssignments(aRes.data.assignments || []);
      setUsers(uRes.data || []);
      const stampSet = new Set(mRes.data.map(i => i.stamp).filter(Boolean));
      // Natural sort: STAMP 1, STAMP 2, ... STAMP 10, STAMP 11
      setStamps(Array.from(stampSet).sort((a, b) => {
        const numA = parseInt((a.match(/\d+/) || [0])[0]);
        const numB = parseInt((b.match(/\d+/) || [0])[0]);
        return numA - numB;
      }));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!editStamp || !editUser) {
      toast.error('Select both stamp and user');
      return;
    }
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/stamp-assignments`, { stamp: editStamp, assigned_user: editUser }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${editUser} assigned to ${editStamp}`);
      setEditStamp('');
      setEditUser('');
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  const handleDelete = async (stamp) => {
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API}/stamp-assignments/${encodeURIComponent(stamp)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`Assignment removed for ${stamp}`);
      fetchData();
    } catch (e) {
      toast.error('Failed to remove');
    }
  };

  const assignmentMap = {};
  assignments.forEach(a => { assignmentMap[a.stamp] = a.assigned_user; });

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-muted-foreground">Loading...</div></div>;

  return (
    <div className="p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6" data-testid="stamp-assignments-page">
      <div>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">Stamp Assignments</h1>
        <p className="text-sm text-muted-foreground mt-1">Assign users to stamps for stock deficit/excess notifications</p>
      </div>

      {/* Add Assignment */}
      {isAdmin && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Assign User to Stamp</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row gap-3 items-end">
              <div className="flex-1">
                <Select value={editStamp} onValueChange={setEditStamp}>
                  <SelectTrigger data-testid="assign-stamp-select"><SelectValue placeholder="Select Stamp" /></SelectTrigger>
                  <SelectContent>
                    {stamps.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex-1">
                <Select value={editUser} onValueChange={setEditUser}>
                  <SelectTrigger data-testid="assign-user-select"><SelectValue placeholder="Select User" /></SelectTrigger>
                  <SelectContent>
                    {users.map(u => <SelectItem key={u.username} value={u.username}>{u.username} ({u.role})</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleSave} data-testid="assign-save-btn"><Save className="h-4 w-4 mr-2" />Assign</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Assignments Table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2"><Users className="h-5 w-5" />Current Assignments</CardTitle>
          <CardDescription>{stamps.length} stamps, {assignments.length} assigned</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stamp</TableHead>
                <TableHead>Assigned User</TableHead>
                <TableHead>Status</TableHead>
                {isAdmin && <TableHead className="text-right">Action</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {stamps.map(stamp => (
                <TableRow key={stamp} data-testid={`assignment-row-${stamp}`}>
                  <TableCell className="font-medium cursor-pointer hover:text-blue-600 hover:underline"
                    onClick={() => navigate(`/stamp/${encodeURIComponent(stamp)}`)}
                    data-testid={`stamp-link-${stamp}`}>{stamp}</TableCell>
                  <TableCell>
                    {assignmentMap[stamp] ? (
                      <Badge variant="outline">{assignmentMap[stamp]}</Badge>
                    ) : (
                      <span className="text-muted-foreground text-sm">Unassigned</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {assignmentMap[stamp] ? (
                      <Badge className="bg-emerald-100 text-emerald-700 text-xs">Active</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">No user</Badge>
                    )}
                  </TableCell>
                  {isAdmin && (
                    <TableCell className="text-right">
                      {assignmentMap[stamp] && (
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(stamp)}>
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
