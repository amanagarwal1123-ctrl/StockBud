import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { XSquare } from 'lucide-react';

export default function RejectDialog({ stamp, onReject }) {
  const [message, setMessage] = useState('');
  const [open, setOpen] = useState(false);

  const handleReject = () => {
    onReject(stamp, message);
    setMessage('');
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm">
          <XSquare className="h-4 w-4 mr-1" />
          Reject
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject {stamp}</DialogTitle>
          <DialogDescription>
            Add a message for the executive explaining what needs to be corrected
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div>
            <Label>Rejection Message (Optional)</Label>
            <Textarea
              placeholder="E.g., Item 84-18 weight seems incorrect, please recheck..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
            />
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleReject}>Reject & Send Message</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
