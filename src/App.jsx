import { useEffect, useState } from 'react';
import { Bar, Pie } from 'react-chartjs-2';
import 'chart.js/auto';
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
  CircularProgress,
  Alert,
  Fade,
  Zoom
} from '@mui/material';
import {
  TaskAlt as TaskIcon,
  CheckCircle as DoneIcon,
  Pending as PendingIcon,
  Today as TodayIcon,
  BarChart as ChartIcon,
  PieChart as PieChartIcon
} from '@mui/icons-material';
import { format, isToday, isTomorrow } from 'date-fns';
import { ru } from 'date-fns/locale';

function StatCard({ title, value, icon, color }) {
  return (
    <Zoom in={true} style={{ transitionDelay: '100ms' }}>
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

function TaskItem({ task, onDone, onDelete }) {
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
    <Fade in={true}>
      <ListItem sx={{ borderRadius: 2, mb: 1, bgcolor: '#f8f9fc' }}>
        <ListItemText
          primary={
            <Typography sx={{ textDecoration: task.is_completed ? 'line-through' : 'none', opacity: task.is_completed ? 0.6 : 1 }}>
              {task.title}
            </Typography>
          }
          secondary={
            <Box display="flex" alignItems="center" gap={1} mt={0.5}>
              <TodayIcon fontSize="small" color="action" />
              <Typography variant="caption" color="text.secondary">
                {getDateLabel()}
              </Typography>
              <Chip label={task.is_completed ? 'Выполнено' : (isToday(new Date(task.remind_at)) ? 'Срочно' : 'В плане')} size="small" color={getChipColor()} />
            </Box>
          }
        />
        <Box display="flex" gap={1}>
          {!task.is_completed && (
            <button
              onClick={() => onDone(task.id)}
              style={{
                padding: '6px 12px',
                bgcolor: '#1cc88a',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              ✓ Готово
            </button>
          )}
          <button
            onClick={() => onDelete(task.id)}
            style={{
              padding: '6px 12px',
              bgcolor: '#e74a3b',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            🗑 Удалить
          </button>
        </Box>
      </ListItem>
    </Fade>
  );
}

function App() {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskTime, setNewTaskTime] = useState('');

  const user_id = new URLSearchParams(window.location.search).get('user_id');

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
      .catch(err => {
        console.error(err);
        setError('Ошибка загрузки данных. Попробуйте позже.');
        setLoading(false);
      });
  }, [user_id]);

  const handleAddTask = async (e) => {
    e.preventDefault();
    if (!newTaskTitle || !newTaskTime) {
      alert('Заполните название и время');
      return;
    }
    const formattedTime = newTaskTime.replace('T', ' ');
    await fetch('https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        user_id, 
        action: 'add', 
        title: newTaskTitle, 
        remind_at: formattedTime 
      })
    });
    setNewTaskTitle('');
    setNewTaskTime('');
    window.location.reload();
  };

  const handleDone = async (task_id) => {
    await fetch('https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, action: 'done', task_id })
    });
    window.location.reload();
  };

  const handleDelete = async (task_id) => {
    await fetch('https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, action: 'delete', task_id })
    });
    window.location.reload();
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

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { position: 'bottom' } }
  };

  const completionPercent = stats.total > 0 ? (stats.completed / stats.total * 100).toFixed(0) : 0;

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress size={60} thickness={4} />
      </Box>
    );
  }

  if (error) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Alert severity="error" sx={{ borderRadius: 2 }}>
          {error}
        </Alert>
      </Container>
    );
  }

  return (
    <>
      <AppBar position="sticky" sx={{ bgcolor: '#4e73df' }}>
        <Toolbar>
          <TaskIcon sx={{ mr: 2 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Планировщик задач
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.8 }}>
            {new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        {/* Форма добавления */}
        <Box component="form" onSubmit={handleAddTask} sx={{ mb: 4, p: 3, bgcolor: '#f8f9fc', borderRadius: 3 }}>
          <Typography variant="h6" gutterBottom>Добавить задачу</Typography>
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
                  fontSize: '16px'
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
                  fontSize: '16px'
                }}
              />
            </Grid>
            <Grid item xs={12} md={1}>
              <button
                type="submit"
                style={{
                  width: '100%',
                  padding: '12px',
                  bgcolor: '#4e73df',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                + Добавить
              </button>
            </Grid>
          </Grid>
        </Box>

        {/* Статистика */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard title="Всего задач" value={stats.total} icon={<TaskIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#4e73df" />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard title="Выполнено" value={stats.completed} icon={<DoneIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#1cc88a" />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard title="В работе" value={stats.pending} icon={<PendingIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#f6c23e" />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard title="На сегодня" value={stats.due_today} icon={<TodayIcon sx={{ fontSize: 40, opacity: 0.8 }} />} color="#e74a3b" />
          </Grid>
        </Grid>

        {/* Прогресс-бар */}
        <Paper sx={{ p: 3, mb: 4, borderRadius: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>Общий прогресс</Typography>
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
              <Bar data={barData} options={options} />
            </Paper>
          </Grid>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, borderRadius: 3 }}>
              <Box display="flex" alignItems="center" gap={1} mb={2}>
                <PieChartIcon color="primary" />
                <Typography variant="h6">Прогресс выполнения</Typography>
              </Box>
              <Pie data={pieData} options={options} />
            </Paper>
          </Grid>
        </Grid>

        {/* Список задач */}
        <Paper sx={{ borderRadius: 3, overflow: 'hidden' }}>
          <Box sx={{ bgcolor: '#4e73df', p: 2 }}>
            <Typography variant="h6" color="white">📋 Список задач</Typography>
          </Box>
          {tasks.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary">✨ У тебя пока нет задач. Добавь их через Telegram-бота!</Typography>
            </Box>
          ) : (
            <List sx={{ p: 2 }}>
              {tasks.map(task => (
                <TaskItem key={task.id} task={task} onDone={handleDone} onDelete={handleDelete} />
              ))}
            </List>
          )}
        </Paper>

        <Box sx={{ textAlign: 'center', mt: 4, py: 3, color: 'text.secondary' }}>
          <Typography variant="body2">
            🔗 <strong>@Miroslav_Scheduler_bot</strong> — работает в паре с сайтом
          </Typography>
        </Box>
      </Container>
    </>
  );
}

export default App;