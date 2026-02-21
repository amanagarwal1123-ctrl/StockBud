import { useEffect, useState } from 'react';
import axios from 'axios';
import { GitBranch, Trash2, Edit } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function MappingManagement() {
  const [mappings, setMappings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMappings();
  }, []);

  const fetchMappings = async () => {
    try {
      const response = await axios.get(`${API}/mappings/all`);
      setMappings(response.data);
    } catch (error) {
      console.error('Error fetching mappings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (transactionName) => {
    const confirmed = window.confirm(`Delete mapping for "${transactionName}"?`);
    if (!confirmed) return;

    try {
      await axios.delete(`${API}/mappings/${encodeURIComponent(transactionName)}`);
      toast.success('Mapping deleted');
      fetchMappings();
    } catch (error) {
      toast.error('Failed to delete mapping');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl sm:text-4xl md:text-5xl font-bold tracking-tight">
          Item Mapping Management
        </h1>
        <p className="text-xs sm:text-base md:text-lg text-muted-foreground mt-2">
          View and manage all item name mappings
        </p>
      </div>

      <Card className="border-border/40 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-primary" />
            All Mappings ({mappings.length})
          </CardTitle>
          <CardDescription>
            Transaction names mapped to master stock items
          </CardDescription>
        </CardHeader>
        <CardContent>
          {mappings.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              No mappings created yet
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction Name</TableHead>
                  <TableHead className="text-center">→</TableHead>
                  <TableHead>Master Item (STOCK 2026)</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.map((mapping, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-mono text-orange-600">
                      {mapping.transaction_name}
                    </TableCell>
                    <TableCell className="text-center text-muted-foreground">
                      →
                    </TableCell>
                    <TableCell className="font-semibold text-primary">
                      {mapping.master_name}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        onClick={() => handleDelete(mapping.transaction_name)}
                        variant="ghost"
                        size="sm"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
