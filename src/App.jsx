import { useEffect, useState } from 'react';
import { Bar, Pie } from 'react-chartjs-2';
import 'chart.js/auto';
import './App.css';

function App() {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const user_id = urlParams.get('user_id');
    if (!user_id) {
      alert('Не указан user_id');
      return;
    }

    fetch(`https://functions.yandexcloud.net/d4evd5vtkc77qo0ksode?user_id=${user_id}`)
      .then(res => res.json())
      .then(data => {
        setTasks(data.tasks);
        setStats(data.stats);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        alert('Ошибка загрузки');
      });
  }, []);

  const barData = {
    labels: ['Всего', 'Выполнено', 'В работе', 'На сегодня'],
    datasets: [{
      label: 'Задачи',
      data: [stats.total, stats.completed, stats.pending, stats.due_today],
      backgroundColor: ['#4e73df', '#1cc88a', '#f6c23e', '#e74a3b']
    }]
  };

  const pieData = {
    labels: ['Выполнено', 'Осталось'],
    datasets: [{
      data: [stats.completed, stats.pending],
      backgroundColor: ['#1cc88a', '#858796']
    }]
  };

  if (loading) return <div className="loading">Загрузка...</div>;

  return (
    <div className="app">
      <header>
        <h1>📊 Панель задач</h1>
        <p>Ваши задачи в одном месте</p>
      </header>

      <div className="charts">
        <div className="chart">
          <h2>📈 Общая статистика</h2>
          <Bar data={barData} />
        </div>

        <div className="chart">
          <h2>📊 Прогресс</h2>
          <Pie data={pieData} />
        </div>
      </div>

      <div className="tasks">
        <h2>📋 Задачи</h2>
        {tasks.length === 0 ? (
          <p>Нет задач</p>
        ) : (
          <ul>
            {tasks.map(task => (
              <li key={task.id} className={task.is_completed ? 'done' : ''}>
                <strong>{task.title}</strong>
                <div className="meta">
                  ⏰ {task.remind_at} | {task.is_today ? 'Сегодня' : 'Позже'}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <footer>
        <p>Powered by YDB & Telegram Bot</p>
      </footer>
    </div>
  );
}

export default App;