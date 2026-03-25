import { useEffect, useState } from 'react';
import axios from 'axios';
import { History as HistoryIcon, Calendar, Download, FileUp, FileDown, CheckCircle2, Scale } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { exportToCSV } from '@/utils/exportCSV';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function History() {
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API}/history/actions?limit=100`);
      setActions(response.data);
    } catch (error) {
      console.error('Error fetching history:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    const exportData = actions.map((action, idx) => ({
      'No.': actions.length - idx,
      'Action': action.action_type,
      'Description': action.description,
      'Date': new Date(action.timestamp).toLocaleString(),
      'Can Undo': action.can_undo ? 'Yes' : 'No'
    }));
    exportToCSV(exportData, 'action_history');
  };

  const getActionIcon = (type) => {
    switch(type) {
      case 'upload_purchase': return <FileUp className="h-4 w-4 text-green-600" />;
      case 'upload_sale': return <FileDown className="h-4 w-4 text-red-600" />;
      case 'upload_opening_stock': return <FileUp className="h-4 w-4 text-blue-600" />;
      case 'stamp_verification': return <Scale className="h-4 w-4 text-purple-600" />;
      case 'item_mapping': return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      default: return <HistoryIcon className="h-4 w-4" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading history...</div>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          Action History
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          All system actions and user activities
        </p>
      </div>

      {actions.length === 0 ? (
        <Card className="border-border/40 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <HistoryIcon className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">No History Yet</h3>
            <p className="text-muted-foreground">
              Upload files or perform actions to see history
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-border/40 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Actions ({actions.length})</CardTitle>
                <CardDescription>All user activities and system events</CardDescription>
              </div>
              <Button onClick={handleExport} variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Date & Time</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {actions.map((action, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-mono text-muted-foreground">
                      {actions.length - idx}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getActionIcon(action.action_type)}
                        <span className="font-medium capitalize">
                          {action.action_type.replace(/_/g, ' ')}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="max-w-md">
                      {action.description}
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {new Date(action.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      {action.can_undo ? (
                        <Badge variant="outline" className="text-green-600">Active</Badge>
                      ) : (
                        <Badge variant="outline" className="text-muted-foreground">Undone</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}