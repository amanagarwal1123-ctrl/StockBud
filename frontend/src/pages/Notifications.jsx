import { useEffect, useState } from 'react';
import axios from 'axios';
import { Bell, Check, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNotifications();
    // Poll every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchNotifications = async () => {
    try {
      const response = await axios.get(`${API}/notifications/my`);
      setNotifications(response.data);
    } catch (error) {
      console.error('Error fetching notifications:', error);
    } finally {
      setLoading(false);
    }
  };

  const getIcon = (type) => {
    switch(type) {
      case 'stock_entry': return <Info className="h-5 w-5 text-blue-600" />;
      case 'stamp_approval': return <CheckCircle2 className="h-5 w-5 text-green-600" />;
      case 'stamp_verification': return <AlertTriangle className="h-5 w-5 text-orange-600" />;
      case 'full_stock_match': return <CheckCircle2 className="h-5 w-5 text-green-600" />;
      default: return <Bell className="h-5 w-5" />;
    }
  };

  const getSeverityColor = (severity) => {
    switch(severity) {
      case 'success': return 'border-green-500/50 bg-green-500/10';
      case 'warning': return 'border-orange-500/50 bg-orange-500/10';
      case 'info': return 'border-blue-500/50 bg-blue-500/10';
      default: return 'border-border/40';
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Notifications
        </h1>
        <p className="text-lg text-muted-foreground mt-2">
          System alerts and user activity notifications
        </p>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {notifications.filter(n => !n.read).length} unread notifications
        </p>
        <Button variant="outline" size="sm" onClick={fetchNotifications}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading notifications...</div>
        </div>
      ) : notifications.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Bell className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">No Notifications</h3>
            <p className="text-muted-foreground">You're all caught up!</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {notifications.map((notif, idx) => (
            <Alert key={idx} className={getSeverityColor(notif.severity)}>
              {getIcon(notif.type)}
              <AlertDescription className="ml-2">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium">{notif.message}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(notif.created_at).toLocaleString()}
                    </p>
                  </div>
                  {!notif.read && (
                    <Badge variant="default" className="ml-4">New</Badge>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          ))}
        </div>
      )}
    </div>
  );
}
