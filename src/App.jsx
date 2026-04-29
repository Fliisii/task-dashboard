import { Button } from '@mui/material';
import { useEffect, useState } from 'react';
import { Bar, Pie } from 'react-chartjs-2';
import 'chart.js/auto';
import toast, { Toaster } from 'react-hot-toast';
import {
  Container,
  AppBar,
  Toolbar,
  Typography,
  Box,
  Paper,
  Grid,
  List,
  ListItem,
  ListItemText,
  Chip,
  Card,
  CardContent,
  LinearProgress,
  Skeleton,
  Alert,
  Zoom,
  Fade,
  IconButton,
  Switch,
  useMediaQuery,
  CssBaseline 
} from '@mui/material';
import {
  TaskAlt as TaskIcon,
  CheckCircle as DoneIcon,
  Pending as PendingIcon,
  Today as TodayIcon,
  BarChart as ChartIcon,
  PieChart as PieChartIcon,
  Brightness4 as DarkIcon,
  Brightness7 as LightIcon,
  Delete as DeleteIcon,
  Check as CheckIcon
} from '@mui/icons-material';
import { format, isToday, isTomorrow } from 'date-fns';
import { ru } from 'date-fns/locale';
import { createTheme, ThemeProvider } from '@mui/material/styles';

// ==================== КОМПОНЕНТЫ ====================

function StatCard({ title, value, icon, color, delay }) {
  return (
    <Zoom in={true} style={{ transitionDelay: `${delay}ms` }}>
      <Card sx={{ height: '100%', background: `linear-gradient(135deg, ${color} 0%, ${color}dd 100%)`, color: 'white' }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Box>
              <Typography variant="caption" sx={{ opacity: 0.8 }}>{title}</Typography>
              <Typography variant="h4" fontWeight="bold">{value}</Typography>
            </Box>
            {icon}
          </Box>
        </CardContent>
      </Card>
    </Zoom>
  );
}

function TaskItem({ task, onDone, onDelete, index }) {
  const getDateLabel = () => {
    const date = new Date(task.remind_at);
    if (isToday(date)) return 'Сегодня';
    if (isTomorrow(date)) return 'Завтра';
    return format(date, 'd MMMM, HH:mm', { locale: ru });
  };

  const getChipColor = () => {
    if (task.is_completed) return 'success';
    if (isToday(new Date(task.remind_at))) return 'warning';
    return 'default';
  };

  return (
    <Fade in={true} style={{ transitionDelay: `${index * 30}ms` }}>
      <ListItem
        sx={{
          borderRadius: 2,
          mb: 1,
          bgcolor: 'background.paper',
          boxShadow: 1,
          transition: '0.2s',
          '&:hover': { transform: 'translateX(4px)', bgcolor: 'action.hover' }
        }}
        secondaryAction={
          <Box>
            {!task.is_completed && (
              <IconButton edge="end" onClick={() => onDone(task.id)} color="success" sx={{ mr: 1 }}>
                <CheckIcon />
              </IconButton>
            )}
            <IconButton edge="end" onClick={() => onDelete(task.id)} color="error">
              <DeleteIcon />
            </IconButton>
          </Box>
        }
      >
        <ListItemText
          primary={
            <Typography
              sx={{
                textDecoration: task.is_completed ? 'line-through' : 'none',
                opacity: task.is_completed ? 0.6 : 1
              }}
            >
              {task.title}
            </Typography>
          }
          secondary={
            <Box display="flex" alignItems="center" gap={1} mt={0.5}>
              <TodayIcon fontSize="small" color="action" />
              <Typography variant="caption" color="text.secondary">
                {getDateLabel()}
              </Typography>
              <Chip
                label={task.is_completed ? 'Выполнено' : isToday(new Date(task.remind_at)) ? 'Срочно' : 'В плане'}
                size="small"
                color={getChipColor()}
              />
            </Box>
          }
        />
      </ListItem>
    </Fade>
  );
}

function LoadingSkeleton() {
  return (
    <Box>
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {[1, 2, 3, 4].map((i) => (
          <Grid item xs={12} sm={6} md={3} key={i}>
            <Skeleton variant="rounded" height={120} sx={{ borderRadius: 3 }} />
          </Grid>
        ))}
      </Grid>
      <Skeleton variant="rounded" height={80} sx={{ mb: 4, borderRadius: 3 }} />
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Skeleton variant="rounded" height={300} sx={{ borderRadius: 3 }} />
        </Grid>
        <Grid item xs={12} md={6}>
          <Skeleton variant="rounded" height={300} sx={{ borderRadius: 3 }} />
        </Grid>
      </Grid>
    </Box>
  );
}

function EmptyState() {
  return (
    <Box sx={{ textAlign: 'center', py: 8 }}>
      <Typography variant="h1" sx={{ fontSize: 64, mb: 2 }}>
        🎯
      </Typography>
      <Typography variant="h6" gutterBottom color="text.secondary">
        У тебя пока нет задач
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Добавь их через Telegram-бота или форму выше ✨
      </Typography>
    </Box>
  );
}

function getUserAvatar(userId) {
  const avatars = {
    'default': '👤',
    '1': '🚀',
    '2': '🎓',
    '3': '💼',
    '4': '🎨',
    '5': '⚡'
  };
  return avatars[userId] || avatars['default'];
}

// ==================== ОСНОВНОЙ КОМПОНЕНТ ====================

function App() {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskTime, setNewTaskTime] = useState('');
  const [darkMode, setDarkMode] = useState(false);
  
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');
  const user_id = new URLSearchParams(window.location.search).get('user_id');
  
  const avatar = getUserAvatar(user_id);
  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: { main: '#4e73df' }
    }
  });

  useEffect(() => {
    setDarkMode(prefersDarkMode);
  }, [prefersDarkMode]);

  useEffect(() => {
    if (!user_id) {
      setError('Не указан user_id. Добавьте ?user_id=ваш_id в URL');
      setLoading(false);
      return;
    }

    fetch(`https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode?user_id=${user_id}`)
      .then(res => res.json())
      .then(data => {
        setTasks(data.tasks || []);
        setStats(data.stats || { total: 0, completed: 0, pending: 0, due_today: 0 });
        setLoading(false);
      })
      .catch(() => {
        setError('Ошибка загрузки данных. Попробуйте позже.');
        setLoading(false);
      });
  }, [user_id]);

  const refreshData = async () => {
    const res = await fetch(`https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode?user_id=${user_id}`);
    const data = await res.json();
    setTasks(data.tasks || []);
    setStats(data.stats || { total: 0, completed: 0, pending: 0, due_today: 0 });
  };

  const handleAddTask = async (e) => {
    e.preventDefault();
    if (!newTaskTitle || !newTaskTime) {
      toast.error('Заполните название и время');
      return;
    }
    const formattedTime = newTaskTime.replace('T', ' ');
    const res = await fetch('https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, action: 'add', title: newTaskTitle, remind_at: formattedTime })
    });
    if (res.ok) {
      toast.success('Задача добавлена!');
      setNewTaskTitle('');
      setNewTaskTime('');
      await refreshData();
    } else {
      toast.error('Ошибка добавления');
    }
  };

  const handleDone = async (task_id) => {
    const res = await fetch('https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, action: 'done', task_id })
    });
    if (res.ok) {
      toast.success('✅ Молодец! Задача выполнена');
      await refreshData();
    }
  };

  const handleDelete = async (task_id) => {
    const res = await fetch('https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, action: 'delete', task_id })
    });
    if (res.ok) {
      toast.success('🗑 Задача удалена');
      await refreshData();
    }
  };

  const barData = {
    labels: ['Всего', 'Выполнено', 'В работе', 'На сегодня'],
    datasets: [{
      label: 'Задачи',
      data: [stats.total, stats.completed, stats.pending, stats.due_today],
      backgroundColor: ['#4e73df', '#1cc88a', '#f6c23e', '#e74a3b'],
      borderRadius: 8
    }]
  };

  const pieData = {
    labels: ['Выполнено', 'Осталось'],
    datasets: [{
      data: [stats.completed, stats.pending],
      backgroundColor: ['#1cc88a', '#858796'],
      borderWidth: 0
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { position: 'bottom' } }
  };

  const completionPercent = stats.total > 0 ? (stats.completed / stats.total * 100).toFixed(0) : 0;

  if (loading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline /> 
        <Container maxWidth="xl" sx={{ py: 4 }}>
          <LoadingSkeleton />
        </Container>
        <Toaster position="top-right" />
      </ThemeProvider>
    );
  }

  if (error) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline /> 
        <Container maxWidth="md" sx={{ mt: 4 }}>
          <Alert severity="error" sx={{ borderRadius: 2 }}>{error}</Alert>
        </Container>
        <Toaster position="top-right" />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Toaster position="top-right" toastOptions={{ duration: 2000 }} />
      
      <AppBar position="sticky" color="primary" elevation={3}>
        <Toolbar>
          <TaskIcon sx={{ mr: 2 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Планировщик задач {avatar}
          </Typography>
          <Box display="flex" alignItems="center" gap={2}>
            <Typography variant="body2" sx={{ opacity: 0.8 }}>
              {new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
            </Typography>
            <IconButton color="inherit" onClick={() => setDarkMode(!darkMode)}>
              {darkMode ? <LightIcon /> : <DarkIcon />}
            </IconButton>
          </Box>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        {/* Форма добавления */}
        <Box component="form" onSubmit={handleAddTask} sx={{ mb: 4, p: 3, bgcolor: 'background.paper', borderRadius: 3, boxShadow: 1 }}>
          <Typography variant="h6" gutterBottom>➕ Добавить задачу</Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={8}>
              <input
                type="text"
                placeholder="Что нужно сделать?"
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #ccc',
                  borderRadius: '8px',
                  fontSize: '16px',
                  background: theme.palette.mode === 'dark' ? '#333' : '#fff',
                  color: theme.palette.mode === 'dark' ? '#fff' : '#000'
                }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <input
                type="datetime-local"
                value={newTaskTime}
                onChange={(e) => setNewTaskTime(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #ccc',
                  borderRadius: '8px',
                  fontSize: '16px',
                  background: theme.palette.mode === 'dark' ? '#333' : '#fff',
                  color: theme.palette.mode === 'dark' ? '#fff' : '#000'
                }}
              />
            </Grid>
            <Grid item xs={12} md={1}>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              fullWidth
              sx={{ py: 1.5, fontWeight: 'bold' }}
            >
              + Добавить
            </Button>
            </Grid>
          </Grid>
        </Box>

        {/* Карточки статистики */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}><StatCard title="Всего задач" value={stats.total} icon={<TaskIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#4e73df" delay={0} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard title="Выполнено" value={stats.completed} icon={<DoneIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#1cc88a" delay={100} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard title="В работе" value={stats.pending} icon={<PendingIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#f6c23e" delay={200} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard title="На сегодня" value={stats.due_today} icon={<TodayIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#e74a3b" delay={300} /></Grid>
        </Grid>

        {/* Прогресс-бар */}
        <Paper sx={{ p: 3, mb: 4, borderRadius: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>📊 Общий прогресс</Typography>
          <Box display="flex" alignItems="center" gap={2}>
            <LinearProgress variant="determinate" value={completionPercent} sx={{ flexGrow: 1, height: 10, borderRadius: 5 }} />
            <Typography variant="h6" fontWeight="bold">{completionPercent}%</Typography>
          </Box>
        </Paper>

        {/* Графики */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, borderRadius: 3 }}>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <ChartIcon color="primary" />
                <Typography variant="h6">Общая статистика</Typography>
              </Box>
              <Bar data={barData} options={chartOptions} />
            </Paper>
          </Grid>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, borderRadius: 3 }}>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <PieChartIcon color="primary" />
                <Typography variant="h6">Прогресс выполнения</Typography>
              </Box>
              <Pie data={pieData} options={chartOptions} />
            </Paper>
          </Grid>
        </Grid>

        {/* Список задач */}
        <Paper sx={{ borderRadius: 3, overflow: 'hidden' }}>
          <Box sx={{ bgcolor: '#4e73df', p: 2 }}>
            <Typography variant="h6" color="white">📋 Список задач</Typography>
          </Box>
          {tasks.length === 0 ? (
            <EmptyState />
          ) : (
            <List sx={{ p: 2 }}>
              {tasks.map((task, idx) => (
                <TaskItem key={task.id} task={task} onDone={handleDone} onDelete={handleDelete} index={idx} />
              ))}
            </List>
          )}
        </Paper>

        {/* Футер */}
        <Box sx={{ textAlign: 'center', mt: 4, py: 3, color: 'text.secondary' }}>
          <Typography variant="body2">
            🔗 <strong>@Miroslav_Scheduler_bot</strong> — работает в паре с сайтом
          </Typography>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;