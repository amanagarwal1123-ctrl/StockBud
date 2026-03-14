import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const CHUNK_SIZE = 200 * 1024;

const UploadContext = createContext(null);

export function UploadProvider({ children }) {
  const [uploads, setUploads] = useState([]);
  const processingRef = useRef(false);
  const queueRef = useRef([]);

  const updateUpload = useCallback((id, updates) => {
    setUploads(prev => prev.map(u => u.id === id ? { ...u, ...updates } : u));
  }, []);

  const removeUpload = useCallback((id) => {
    setUploads(prev => prev.filter(u => u.id !== id));
  }, []);

  // Safety: auto-clear stuck uploads > 10 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      setUploads(prev => {
        const now = Date.now();
        return prev.filter(u => {
          if (u.status === 'uploading' && u._startTime && (now - u._startTime > 600000)) {
            return false;
          }
          return true;
        });
      });
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const pollUploadStatus = async (uploadId, trackId) => {
    for (let attempt = 0; attempt < 180; attempt++) {
      await new Promise(r => setTimeout(r, 5000));
      try {
        const res = await axios.get(`${API}/upload/status/${uploadId}`, { timeout: 10000 });
        if (res.data.status === 'complete') return res;
        if (res.data.status === 'error') throw new Error(res.data.detail || 'Processing failed');
        updateUpload(trackId, { message: res.data.message || `Processing... (${(attempt + 1) * 5}s)` });
      } catch (pollErr) {
        if (pollErr.message?.includes('Processing failed')) throw pollErr;
      }
    }
    throw new Error('Processing timed out after 15 minutes');
  };

  const uploadChunkWithRetry = async (url, formData, chunkIdx, totalChunks, trackId, maxRetries = 3) => {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await axios.post(url, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 60000,
        });
      } catch (err) {
        if (attempt === maxRetries) {
          throw new Error(`Chunk ${chunkIdx + 1}/${totalChunks} failed`);
        }
        updateUpload(trackId, { message: `Chunk ${chunkIdx + 1} retry ${attempt}...` });
        await new Promise(r => setTimeout(r, 2000 * attempt));
      }
    }
  };

  // Execute a single upload job
  const executeUpload = async (job) => {
    const { trackId, fileType, file, dateRanges } = job;
    const fileTypeLabels = {
      purchase: 'Purchase', sale: 'Sale', opening_stock: 'Opening Stock',
      physical_stock: 'Physical Stock', master_stock: 'Master Stock',
      branch_transfer: 'Branch Transfer',
    };

    updateUpload(trackId, { status: 'uploading', _startTime: Date.now() });

    try {
      let response;
      const useChunked = file.size > CHUNK_SIZE && fileType !== 'master_stock' && fileType !== 'physical_stock';

      if (useChunked) {
        const range = dateRanges[fileType] || {};
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
        updateUpload(trackId, { message: `Initializing (${totalChunks} chunks)...` });

        const initRes = await axios.post(`${API}/upload/init`, {
          file_type: fileType,
          start_date: range.start || null,
          end_date: range.end || null,
          verification_date: fileType === 'physical_stock' ? dateRanges.physical_stock?.date : null,
          total_chunks: totalChunks,
        }, { timeout: 30000 });
        const uploadId = initRes.data.upload_id;

        for (let i = 0; i < totalChunks; i++) {
          const pct = Math.round(((i + 1) / totalChunks) * 100);
          updateUpload(trackId, { percent: pct, message: `Uploading chunk ${i + 1}/${totalChunks}` });
          const start = i * CHUNK_SIZE;
          const end = Math.min(start + CHUNK_SIZE, file.size);
          const chunk = file.slice(start, end);
          const fd = new FormData();
          fd.append('file', chunk, `chunk_${i}`);
          await uploadChunkWithRetry(`${API}/upload/chunk/${uploadId}?chunk_index=${i}`, fd, i, totalChunks, trackId);
        }

        updateUpload(trackId, { percent: 100, message: 'Server processing...', status: 'processing' });
        await axios.post(`${API}/upload/finalize/${uploadId}`, {}, { timeout: 30000 });
        response = await pollUploadStatus(uploadId, trackId);
      } else {
        updateUpload(trackId, { message: 'Uploading...' });
        const formData = new FormData();
        formData.append('file', file);
        const range = dateRanges[fileType] || {};
        let endpoint;
        if (fileType === 'opening_stock') endpoint = `${API}/opening-stock/upload`;
        else if (fileType === 'physical_stock') endpoint = `${API}/physical-stock/upload?verification_date=${dateRanges.physical_stock?.date}`;
        else if (fileType === 'master_stock') endpoint = `${API}/master-stock/upload`;
        else endpoint = `${API}/transactions/upload/${fileType}?start_date=${range.start}&end_date=${range.end}`;

        response = await axios.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 600000,
          onUploadProgress: (p) => {
            if (p.total) {
              const pct = Math.round((p.loaded * 100) / p.total);
              updateUpload(trackId, { percent: pct, message: pct < 100 ? `Uploading: ${pct}%` : 'Processing...' });
            }
          },
        });
      }

      updateUpload(trackId, { status: 'done', percent: 100, message: 'Complete' });
      toast.success(response?.data?.message || `${fileTypeLabels[fileType]} uploaded!`);
      setTimeout(() => removeUpload(trackId), 5000);
      return response;
    } catch (error) {
      const msg = error.message || error.response?.data?.detail || 'Upload failed';
      updateUpload(trackId, { status: 'error', message: msg });
      toast.error(msg);
      setTimeout(() => removeUpload(trackId), 10000);
      throw error;
    }
  };

  // Process queue one at a time
  const processQueue = useCallback(async () => {
    if (processingRef.current) return;
    processingRef.current = true;

    while (queueRef.current.length > 0) {
      const job = queueRef.current.shift();
      try {
        await executeUpload(job);
      } catch {
        // Error already handled in executeUpload
      }
    }

    processingRef.current = false;
  }, []);

  // Enqueue a new upload — deterministic, never blocked
  const enqueueUpload = useCallback((fileType, file, dateRanges = {}) => {
    const trackId = `${fileType}-${Date.now()}`;
    const fileTypeLabels = {
      purchase: 'Purchase', sale: 'Sale', opening_stock: 'Opening Stock',
      physical_stock: 'Physical Stock', master_stock: 'Master Stock',
      branch_transfer: 'Branch Transfer',
    };

    // Add to UI state immediately as queued
    setUploads(prev => [...prev, {
      id: trackId, fileType, fileName: file.name,
      label: fileTypeLabels[fileType] || fileType,
      percent: 0, message: 'Queued...', status: 'queued',
      _startTime: Date.now(),
    }]);

    // Add to processing queue
    queueRef.current.push({ trackId, fileType, file, dateRanges });

    // Trigger processing
    processQueue();

    return trackId;
  }, [processQueue]);

  return (
    <UploadContext.Provider value={{ uploads, enqueueUpload, removeUpload }}>
      {children}
    </UploadContext.Provider>
  );
}

export const useUpload = () => useContext(UploadContext);
