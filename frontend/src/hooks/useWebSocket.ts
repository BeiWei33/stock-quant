import { useEffect, useRef, useState, useCallback } from 'react';

export interface TaskProgress {
  task_id: string;
  action: string;
  status: 'PENDING' | 'RUNNING' | 'OK' | 'FAIL' | 'TIMEOUT';
  progress: number;
  total_steps: number;
  step_name: string;
  stdout_tail: string;
  stderr_tail: string;
  started_at: string;
  ended_at: string;
  return_code: number | null;
  timestamp: string;
}

type MessageHandler = (data: TaskProgress) => void;

export function useTaskWebSocket() {
  const [tasks, setTasks] = useState<Map<string, TaskProgress>>(new Map());
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    // Determine WebSocket URL - use same host for Vite proxy
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/tasks/ws`;

    console.log('Connecting WebSocket to:', wsUrl);

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data: TaskProgress = JSON.parse(event.data);
          setTasks((prev) => {
            const next = new Map(prev);
            next.set(data.task_id, data);
            return next;
          });
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        wsRef.current = null;

        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error', error);
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('Failed to create WebSocket', e);
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const getTask = useCallback(
    (taskId: string) => tasks.get(taskId),
    [tasks]
  );

  const getActiveTasks = useCallback(() => {
    return Array.from(tasks.values()).filter(
      (t) => t.status === 'PENDING' || t.status === 'RUNNING'
    );
  }, [tasks]);

  const getCompletedTasks = useCallback(() => {
    return Array.from(tasks.values()).filter(
      (t) => t.status === 'OK' || t.status === 'FAIL' || t.status === 'TIMEOUT'
    );
  }, [tasks]);

  return {
    tasks: Array.from(tasks.values()),
    connected,
    getTask,
    getActiveTasks,
    getCompletedTasks,
  };
}
