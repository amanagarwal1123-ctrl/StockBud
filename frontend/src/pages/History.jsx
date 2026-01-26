import { useEffect, useState } from 'react';
import axios from 'axios';
import { History as HistoryIcon, Calendar, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { format } from 'date-fns';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function History() {
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSnapshots();
  }, []);

  const fetchSnapshots = async () => {
    try {
      const response = await axios.get(`${API}/snapshots`);
      setSnapshots(response.data);
    } catch (error) {
      console.error('Error fetching snapshots:', error);
    } finally {
      setLoading(false);
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
    <div className="p-6 md:p-8 space-y-6" data-testid="history-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight" data-testid="history-title">
          Matching History
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          Historical inventory matching snapshots
        </p>
      </div>

      {snapshots.length === 0 ? (
        <Card className="border-border/40 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <HistoryIcon className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">No History Yet</h3>
            <p className="text-muted-foreground">
              Run inventory matching to create your first snapshot
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {snapshots.map((snapshot, idx) => (
            <Card
              key={snapshot.id}
              className="border-border/40 shadow-sm hover:shadow-md transition-shadow"
              data-testid={`snapshot-${idx}`}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-muted">
                      {snapshot.complete_match ? (
                        <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                      ) : (
                        <AlertTriangle className="h-6 w-6 text-amber-600" />
                      )}
                    </div>
                    <div>
                      <CardTitle className="text-xl flex items-center gap-2">
                        Match {snapshots.length - idx}
                        {snapshot.complete_match && (
                          <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">
                            Complete
                          </Badge>
                        )}
                      </CardTitle>
                      <CardDescription className="flex items-center gap-2 mt-1">
                        <Calendar className="h-4 w-4" />
                        {format(new Date(snapshot.date), 'PPpp')}
                      </CardDescription>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {snapshot.complete_match ? (
                  <p className="text-sm text-muted-foreground">
                    Perfect match - All items aligned between book and physical inventory.
                  </p>
                ) : (
                  <div className="space-y-3">
                    <div className="flex gap-6">
                      {snapshot.differences.length > 0 && (
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="font-mono">
                            {snapshot.differences.length}
                          </Badge>
                          <span className="text-sm text-muted-foreground">Differences</span>
                        </div>
                      )}
                      {snapshot.unmatched_items.length > 0 && (
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="font-mono">
                            {snapshot.unmatched_items.length}
                          </Badge>
                          <span className="text-sm text-muted-foreground">Unmatched Items</span>
                        </div>
                      )}
                    </div>
                    {snapshot.differences.length > 0 && (
                      <div className="mt-3 p-3 bg-muted/30 rounded-lg">
                        <p className="text-xs font-medium text-muted-foreground mb-2">Sample Differences:</p>
                        <div className="space-y-1">
                          {snapshot.differences.slice(0, 3).map((diff, i) => (
                            <p key={i} className="text-xs text-muted-foreground font-mono">
                              {diff.item_name}: {diff.gr_wt_diff > 0 ? '+' : ''}{diff.gr_wt_diff.toFixed(2)}g
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}